"""
Crawling a FHIR server and storing what the validation rules report.
The rules themselves live in app.services.rules.
"""

import asyncio
import logging
from datetime import datetime, timezone
import random
from typing import Any, AsyncIterator
from time import monotonic
from uuid import UUID

from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert


from app.models.invalid_resource import InvalidResource, InvalidResourceIssue
from app.models.validation_run import ValidationRun
from app.services.config_service import get_config_for_run
from app.services.rules import RESOURCE_TYPES, active_rules, evaluate
from app.services.url_policy import same_origin
from app.api.v1.endpoints.websocket import broadcast_progress

logger = logging.getLogger(__name__)


class FhirServerUnresponsiveError(Exception):
    """The FHIR server did not answer a request after exhausting all retries.

    Distinguished from other failures so the frontend can tell the user this
    is a server-side responsiveness issue, not an application bug.
    """


async def run_cancel_requested(run_id: UUID, db: AsyncSession) -> bool:
    """True if cooperative cancellation was requested for this run.
    Fresh scalar SELECT so it sees the commit from the cancel endpoint's
    separate session (READ COMMITTED)."""
    val = (
        await db.execute(
            select(ValidationRun.cancel_requested).where(ValidationRun.id == run_id)
        )
    ).scalar_one_or_none()
    return bool(val)


class BaseValidator:
    """Base class for all resource validators."""

    PAGE_SIZE = 1000
    MAX_RETRIES = 5
    RETRYABLE_STATUS = {429, 502, 503, 504}
    CHECKPOINT_EVERY_N_PAGES = 25
    MAX_REANCHORS = 5
    REANCHOR_STATUS = {404, 408, 410, 429, 500, 502, 503, 504}

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth_config: dict = None,
        server_id: UUID = None,
    ):
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.auth_config = auth_config or {}
        self.server_id = server_id
        self.filter_params: dict = {}
        self._page_rule_counts: dict[tuple[str, str], int] = {}
        self.cancelled = False
        self._foreign_next_logged = False

    def _merge_params(self, base: dict) -> dict:
        """Merge the configured filter params into a search param dict.

        _lastUpdated needs special handling: the crawl watermark (ge<wm>) is the
        resume lower bound and must replace the filter's lower bound, while the
        filter's upper bound (le..) is always preserved. All other filter params
        (profile, tag) are added as-is.
        """
        if not self.filter_params:
            return base

        merged = dict(base)
        filt = self.filter_params

        if "_lastUpdated" in filt:
            filter_lu = filt["_lastUpdated"]
            filter_lu = filter_lu if isinstance(filter_lu, list) else [filter_lu]
            upper = [v for v in filter_lu if v.startswith("le")]
            lower = [v for v in filter_lu if v.startswith("ge")]

            if "_lastUpdated" in base:
                # base already carries the watermark ge<wm>; keep it as lower
                # bound, add only the filter's upper bound.
                base_lu = base["_lastUpdated"]
                base_lu = base_lu if isinstance(base_lu, list) else [base_lu]
                merged["_lastUpdated"] = base_lu + upper
            else:
                # no watermark yet (fresh crawl): use the full filter range.
                merged["_lastUpdated"] = lower + upper

        for key, value in filt.items():
            if key == "_lastUpdated":
                continue
            merged[key] = value

        return merged

    async def fetch_bundle(self, url: str, params: dict | None = None) -> dict:
        """Fetch a FHIR bundle with retry logic."""

        headers = {"Accept": "application/fhir+json"}

        # Fetching the FHIR Bundle
        last_exc = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = await self.client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in self.RETRYABLE_STATUS or attempt == self.MAX_RETRIES:
                    logger.error(
                        "HTTP %s at %s (attempt %s/%s)",
                        status,
                        url,
                        attempt,
                        self.MAX_RETRIES,
                    )
                    raise
                last_exc = exc
                retry_after = exc.response.headers.get("Retry-After", "")
                wait = (
                    float(retry_after)
                    if retry_after.isdigit()
                    else min(2**attempt, 60) + random.uniform(0, 1)
                )
                logger.warning(
                    "HTTP %s at %s, retry %s/%s in %.1fs",
                    status,
                    url,
                    attempt,
                    self.MAX_RETRIES,
                    wait,
                )
                await asyncio.sleep(wait)
            except (
                httpx.ReadError,
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.RemoteProtocolError,
            ) as e:
                last_exc = e
                # The auth flow (e.g. OAuth2 token refresh) can issue its own
                # request to a different host before the actual FHIR request
                # is sent; exc.request reflects whichever one really failed,
                # which is not always `url`.
                failed_url = getattr(e, "request", None)
                failed_url = failed_url.url if failed_url is not None else url
                if attempt == self.MAX_RETRIES:
                    logger.error(
                        "Network error at %s (target %s): %s: %s, giving up after %s/%s",
                        url,
                        failed_url,
                        type(e).__name__,
                        e,
                        attempt,
                        self.MAX_RETRIES,
                    )
                    # httpx network exceptions often carry no message
                    # (str(e) == ""), which used to leave run.error_message
                    # blank. Raise something a human (and the frontend) can
                    # actually read.
                    raise FhirServerUnresponsiveError(
                        f"FHIR server did not respond after {self.MAX_RETRIES} "
                        f"attempts ({type(e).__name__} at {failed_url})"
                    ) from e
                wait = min(2**attempt, 60) + random.uniform(0, 1)
                logger.warning(
                    "Network error at %s (target %s): %s: %s, retry %s/%s in %.1fs",
                    url,
                    failed_url,
                    type(e).__name__,
                    e,
                    attempt,
                    self.MAX_RETRIES,
                    wait,
                )
                await asyncio.sleep(wait)
        raise last_exc

    @staticmethod
    def _parse_dt(raw: str | None):
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _pin_to_base(self, link: str) -> str:
        """
        Keep paging on the configured server. The credentials are attached to
        every request, so a next link to another host must not be followed.
        Servers behind a proxy sometimes report their internal host; if the
        path still lies below the base URL, the configured host is used.
        """
        absolute = urljoin(self.base_url + "/", link)
        if same_origin(absolute, self.base_url):
            return absolute
        base = urlsplit(self.base_url)
        parts = urlsplit(absolute)
        if parts.path.startswith(base.path):
            if not self._foreign_next_logged:
                self._foreign_next_logged = True
                logger.warning(
                    "Next link host %s differs from %s, using the configured "
                    "host. Check the base URL setting of the FHIR server.",
                    parts.netloc,
                    base.netloc,
                )
            return urlunsplit((base.scheme, base.netloc, parts.path, parts.query, ""))
        raise ValueError(
            f"The FHIR server returned a next link to {parts.scheme}://{parts.netloc}"
            f"{parts.path}, which is outside {self.base_url}. Check the base URL "
            "setting of the FHIR server."
        )

    @staticmethod
    def _next_link(bundle: dict) -> str | None:
        return next(
            (l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"),
            None,
        )

    @classmethod
    def _max_last_updated(cls, entries: list[dict]) -> str | None:
        best_raw, best_dt = None, None
        for e in entries:
            raw = e.get("resource", {}).get("meta", {}).get("lastUpdated")
            dt = cls._parse_dt(raw)
            if dt and (best_dt is None or dt > best_dt):
                best_dt, best_raw = dt, raw
        return best_raw

    @classmethod
    def _is_reanchorable(cls, exc: Exception) -> bool:
        # 400/401/403 = Config-/Auth-Fehler -> Re-Anchor hilft nicht, propagieren.
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in cls.REANCHOR_STATUS
        return isinstance(exc, httpx.HTTPError)  # Netzwerkfehler -> re-anchorbar

    async def _load_watermark(
        self, run_id: UUID, resource_type: str, db: AsyncSession
    ) -> str | None:
        run = (
            await db.execute(select(ValidationRun).where(ValidationRun.id == run_id))
        ).scalar_one_or_none()
        cp = (run.checkpoint or {}).get(resource_type) if run else None
        return cp.get("last_updated") if cp else None

    async def _persist_watermark(
        self, run_id: UUID, resource_type: str, watermark: str | None, db: AsyncSession
    ):
        if watermark is None:
            return
        run = (
            await db.execute(select(ValidationRun).where(ValidationRun.id == run_id))
        ).scalar_one_or_none()
        if not run:
            return
        cp = dict(run.checkpoint or {})
        cp[resource_type] = {"last_updated": watermark}
        run.checkpoint = cp
        await db.commit()

    async def iter_pages(
        self, resource_type: str, run_id: UUID, db: AsyncSession
    ) -> AsyncIterator[list[dict]]:
        """
        Crawl a resource type sorted ascending by _lastUpdated, following the
        server's next links. On resume the first search is anchored at the
        persisted watermark (_lastUpdated=ge). No automatic re-anchoring: if a
        page still fails after fetch_bundle's retries the error propagates, the
        run is marked FAILED, and re-anchoring happens once, on explicit resume.
        """
        watermark = await self._load_watermark(run_id, resource_type, db)
        watermark_dt = self._parse_dt(watermark)
        pages_since_cp = 0

        params = {"_count": self.PAGE_SIZE, "_sort": "_lastUpdated"}
        if watermark is not None:
            params["_lastUpdated"] = f"ge{watermark}"
        params = self._merge_params(params)

        url = f"{self.base_url}/{resource_type}"
        first = True

        try:
            while url:
                if await run_cancel_requested(run_id, db):
                    self.cancelled = True
                    break
                bundle = await self.fetch_bundle(url, params if first else None)
                first = False
                entries = bundle.get("entry", [])
                if entries:
                    yield entries
                    page_wm = self._max_last_updated(entries)
                    page_dt = self._parse_dt(page_wm)
                    if page_dt and (watermark_dt is None or page_dt > watermark_dt):
                        watermark, watermark_dt = page_wm, page_dt
                    pages_since_cp += 1
                    if pages_since_cp >= self.CHECKPOINT_EVERY_N_PAGES:
                        await self._persist_watermark(
                            run_id, resource_type, watermark, db
                        )
                        pages_since_cp = 0
                next_link = self._next_link(bundle)
                url = self._pin_to_base(next_link) if next_link else None
        finally:
            # persist even if the crawl raises, so resume starts from the last
            # processed page, not from the last periodic checkpoint.
            await self._persist_watermark(run_id, resource_type, watermark, db)

    async def save_invalid(
        self,
        run_id: UUID,
        resource_type: str,
        resource_id: str,
        issues: list[dict],
        metrics: dict[str, Any],
        db: AsyncSession,
    ):
        """
        UPSERT an invalid resource and replace its normalized issue rows.

        On first detection: insert with first_seen and last_seen both pointing
        to the current run. On subsequent detections: update only the
        "current state" fields, preserving first_seen_*. The issue rows in
        invalid_resource_issues always reflect the latest validation snapshot.
        """
        if self.server_id is None:
            logger.error(
                "server_id is not set on validator; cannot save %s/%s",
                resource_type,
                resource_id,
            )
            return

        now = datetime.now(timezone.utc)

        try:
            stmt = pg_insert(InvalidResource).values(
                server_id=self.server_id,
                server_base_url=self.base_url,
                resource_type=resource_type,
                resource_id=str(resource_id),
                issues=[i["message"] for i in issues],
                metrics={**metrics, "issues_detail": issues},
                first_seen_run_id=run_id,
                first_seen_at=now,
                last_seen_run_id=run_id,
                last_seen_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_server_resource_type_id",
                set_={
                    "issues": stmt.excluded.issues,
                    "metrics": stmt.excluded.metrics,
                    "last_seen_run_id": stmt.excluded.last_seen_run_id,
                    "last_seen_at": stmt.excluded.last_seen_at,
                },
            ).returning(InvalidResource.id)

            inv_id = (await db.execute(stmt)).scalar_one()

            # Replace issue rows with the latest snapshot (same transaction).
            await db.execute(
                delete(InvalidResourceIssue).where(
                    InvalidResourceIssue.invalid_resource_id == inv_id
                )
            )
            if issues:
                await db.execute(
                    insert(InvalidResourceIssue),
                    [
                        {
                            "invalid_resource_id": inv_id,
                            "rule": i.get("rule", "unknown"),
                            "severity": i.get("severity", "unknown"),
                        }
                        for i in issues
                    ],
                )

            await db.commit()

            # Only count towards rule_stats after a successful commit.
            for i in issues:
                key = (i.get("rule", "unknown"), i.get("severity", "unknown"))
                self._page_rule_counts[key] = self._page_rule_counts.get(key, 0) + 1

        except Exception as e:
            await db.rollback()
            logger.error("Save error for %s/%s: %s", resource_type, resource_id, e)

    async def sweep_stale_invalid(self, run_id: UUID, resource_type: str, db: AsyncSession) -> int:
        """
        Remove invalid_resources rows for this (server, resource_type) that
        were not reconfirmed by the crawl that just finished under run_id.

        Only call this after a resource type's crawl completed in full — no
        cancellation, no error, and (checked by the caller) no active
        validation_configs filter narrowing which resources get visited.
        A full crawl touches every resource of that type on the server, so
        anything still pointing at an older run_id is no longer invalid
        (fixed or deleted upstream, inside or outside Verity) and can be
        dropped. invalid_resource_issues rows cascade-delete with it.
        """
        result = await db.execute(
            delete(InvalidResource).where(
                InvalidResource.server_id == self.server_id,
                InvalidResource.resource_type == resource_type,
                InvalidResource.last_seen_run_id != run_id,
            )
        )
        await db.commit()
        removed = result.rowcount or 0
        if removed:
            logger.info(
                "Swept %s stale invalid_resources for %s on server %s",
                removed,
                resource_type,
                self.server_id,
            )
        return removed

    async def _update_run_counters(
        self,
        run_id: UUID,
        resource_type: str,
        page_processed: int,
        page_invalid: int,
        db: AsyncSession,
    ):
        """Batch update of run counters once per bundle page."""

        stmt = select(ValidationRun).where(ValidationRun.id == run_id)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            return

        run.total_processed = (run.total_processed or 0) + page_processed
        run.total_invalid = (run.total_invalid or 0) + page_invalid

        current_stats = run.per_resource_stats or {}
        existing = current_stats.get(resource_type, {"processed": 0, "invalid": 0})

        new_stats = {
            **{
                rt: {"processed": v["processed"], "invalid": v["invalid"]}
                for rt, v in current_stats.items()
            },
            resource_type: {
                "processed": existing["processed"] + page_processed,
                "invalid": existing["invalid"] + page_invalid,
            },
        }
        run.per_resource_stats = new_stats

        # Flush the per-page rule counter into the precomputed rule_stats.
        page_rules = self._page_rule_counts
        self._page_rule_counts = {}
        if page_rules:
            current = run.rule_stats or {}
            rt_bucket = dict(current.get(resource_type, {}))
            for (rule, severity), c in page_rules.items():
                key = f"{rule}|{severity}"
                rt_bucket[key] = rt_bucket.get(key, 0) + c
            # full reassignment so SQLAlchemy detects the JSON change
            run.rule_stats = {**current, resource_type: rt_bucket}

        await db.commit()

    async def _check_linked_resources(
        self,
        patient_ids: list[str],
        resource_type: str,
    ) -> set[str]:
        """
        Check which patients have at least one linked resource.
        Uses individual _summary=count requests fired concurrently.
        Semaphore limits to 20 parallel requests to avoid overloading the server.
        """
        patients_with_resource: set[str] = set()
        semaphore = asyncio.Semaphore(20)

        async def check_single(pid: str):
            url = (
                f"{self.base_url}/{resource_type}"
                f"?subject=Patient/{pid}"
                f"&_summary=count"
            )
            async with semaphore:
                try:
                    bundle = await self.fetch_bundle(url)
                    if bundle.get("total", 0) > 0:
                        patients_with_resource.add(pid)
                except Exception as e:
                    logger.warning(
                        "%s count check failed for Patient/%s: %s",
                        resource_type,
                        pid,
                        e,
                    )

        await asyncio.gather(*[check_single(pid) for pid in patient_ids])
        return patients_with_resource

    async def _emit_progress(
        self,
        run_id: UUID,
        resource_type: str,
        total_processed: int,
        total_invalid: int,
        pages_done: int,
        estimated_total: int,
        start_time: float,
    ):
        """
        Broadcast per-page progress via WebSocket.
        Imported here to avoid circular imports at module level.
        """

        elapsed = monotonic() - start_time
        percent = (
            round((total_processed / estimated_total) * 100, 1)
            if estimated_total > 0
            else 0.0
        )
        rps = round(total_processed / elapsed, 1) if elapsed > 0 else 0.0
        eta_seconds = (
            round((estimated_total - total_processed) / rps)
            if rps > 0 and estimated_total > total_processed
            else None
        )

        await broadcast_progress(
            str(run_id),
            {
                "type": "progress",
                "run_id": str(run_id),
                "status": "running",
                "resource_type": resource_type,
                "pages_done": pages_done,
                "total_processed": total_processed,
                "total_invalid": total_invalid,
                "estimated_total": estimated_total,
                "progress_percent": percent,
                "elapsed_seconds": round(elapsed, 1),
                "resources_per_second": rps,
                "eta_seconds": eta_seconds,
            },
        )

    async def _fetch_total(self, resource_type: str) -> int:
        """
        Fetch total resource count via _summary=count.
        Returns 0 if not available or on error.
        """
        url = f"{self.base_url}/{resource_type}"
        params = self._merge_params({"_summary": "count"})
        try:
            bundle = await self.fetch_bundle(url, params)
            return bundle.get("total", 0)
        except Exception as e:
            logger.warning("Could not fetch total for %s: %s", resource_type, e)
            return 0


class ResourceValidator(BaseValidator):
    """Checks every resource of one type against the enabled rules of the registry."""

    resource_type: str = ""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        resource_type = self.resource_type
        config = await get_config_for_run(self.server_id, resource_type, db)
        rules = active_rules(resource_type, config)
        page_hooks = [r for r in rules if r.prepare]

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0
        estimated_total = await self._fetch_total(resource_type)

        async for entries in self.iter_pages(resource_type, run_id, db):
            pages_done += 1
            resources = [e.get("resource", {}) for e in entries]
            page = {r.key: await r.prepare(self, resources) for r in page_hooks}

            page_invalid = 0
            for resource in resources:
                issues, metrics = evaluate(resource, rules, config, page)
                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, resource_type, resource.get("id", ""), issues, metrics, db
                    )

            cumulative_processed += len(resources)
            cumulative_invalid += page_invalid
            await self._update_run_counters(
                run_id, resource_type, len(resources), page_invalid, db
            )
            await self._emit_progress(
                run_id=run_id,
                resource_type=resource_type,
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )

        logger.info("%s validation complete for run %s", resource_type, run_id)


VALIDATORS: dict[str, type[ResourceValidator]] = {
    rt: type(f"{rt}Validator", (ResourceValidator,), {"resource_type": rt})
    for rt in RESOURCE_TYPES
}
