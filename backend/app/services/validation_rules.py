"""
Validation logic for all supported FHIR resource types.
"""

import asyncio
import logging
from datetime import datetime, timezone
import random
from typing import Any, AsyncIterator
from time import monotonic
from uuid import UUID

import re
import httpx
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert


from app.models.invalid_resource import InvalidResource, InvalidResourceIssue
from app.models.validation_run import ValidationRun
from app.services.config_service import get_config_for_run, rule_enabled
from app.api.v1.endpoints.websocket import broadcast_progress

logger = logging.getLogger(__name__)

# FHIR date: YYYY, YYYY-MM or YYYY-MM-DD
FHIR_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


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

    @staticmethod
    def _as_utc(raw: str) -> datetime:
        """Parse a FHIR date/dateTime; values without time zone count as UTC."""
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def _end_before_start(start: str, end: str) -> bool:
        """
        True if a Period ends before it starts (FHIR invariant per-1 allows
        start == end). Values of different precision, e.g. a date against a
        dateTime, are compared at the lower precision. Raises ValueError for
        values that are not FHIR date/dateTime strings.
        """
        if "T" in start and "T" in end:
            return BaseValidator._as_utc(end) < BaseValidator._as_utc(start)
        start_date = start.split("T")[0]
        end_date = end.split("T")[0]
        if not (FHIR_DATE.match(start_date) and FHIR_DATE.match(end_date)):
            raise ValueError(f"not a FHIR date: {start!r} / {end!r}")
        precision = min(len(start_date), len(end_date))
        return end_date[:precision] < start_date[:precision]

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
                url = self._next_link(bundle)
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

    @staticmethod
    def _is_future(date_str: str) -> bool:
        if not date_str:
            return False
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt > datetime.now(timezone.utc)
        except ValueError:
            return False

    @staticmethod
    def _is_reference_format(reference: str, resource_type: str) -> bool:
        """Check if a reference follows the 'ResourceType/id' format."""

        return bool(reference) and reference.startswith(f"{resource_type}/")

    def _build_metrics(self, config: dict) -> dict:
        """Initialize metrics from config: all enabled rules start as True."""
        return {key: True for key in config if config[key].get("enabled", False)}


# =============================================================================
# PATIENT
# =============================================================================
class PatientValidator(BaseValidator):
    """Patient Validator Class"""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validation and save for patients resources"""

        config = await get_config_for_run(self.server_id, "Patient", db)

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0

        estimated_total = await self._fetch_total("Patient")

        async for entries in self.iter_pages("Patient", run_id, db):
            pages_done += 1

            page_patient_ids = [
                e.get("resource", {}).get("id", "")
                for e in entries
                if e.get("resource", {}).get("id")
            ]

            # Batch-query: wich patient are mindestens one obesertation or condition
            patients_with_observation: set[str] = set()
            patients_with_condition: set[str] = set()

            if rule_enabled(config, "has_observation"):
                patients_with_observation = await self._check_linked_resources(
                    page_patient_ids, "Observation"
                )

            if rule_enabled(config, "has_condition"):
                patients_with_condition = await self._check_linked_resources(
                    page_patient_ids, "Condition"
                )

            page_processed = 0
            page_invalid = 0

            for entry in entries:
                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)

                # privacy:
                if rule_enabled(config, "text_forbidden"):
                    if resource.get("text"):
                        issues.append(
                            {
                                "rule": "text_forbidden",
                                "severity": config["text_forbidden"]["severity"],
                                "message": "Patient.text is present. Cleartext are forbidden in pseudonymized data.",
                            }
                        )
                        metrics["text_forbidden"] = False
                if rule_enabled(config, "name_forbidden"):
                    if resource.get("name"):
                        issues.append(
                            {
                                "rule": "name_forbidden",
                                "severity": config["name_forbidden"]["severity"],
                                "message": "Patient.name is present. Cleartext names are forbidden in pseudonymized data.",
                            }
                        )
                        metrics["name_forbidden"] = False

                # privacy: address_forbidden
                if rule_enabled(config, "address_forbidden"):
                    addr_list = resource.get("address", [])
                    if addr_list:
                        addr = addr_list[0]
                        if addr.get("line") or addr.get("city") or addr.get("text"):
                            issues.append(
                                {
                                    "rule": "address_forbidden",
                                    "severity": config["address_forbidden"]["severity"],
                                    "message": "Patient.address contains forbidden fields (line, city, or text).",
                                }
                            )
                            metrics["address_forbidden"] = False

                # privacy: telecom_forbidden
                if rule_enabled(config, "telecom_forbidden"):
                    if resource.get("telecom"):
                        issues.append(
                            {
                                "rule": "telecom_forbidden",
                                "severity": config["telecom_forbidden"]["severity"],
                                "message": "Patient.telecom is present. Contact data is forbidden in pseudonymized data.",
                            }
                        )
                        metrics["telecom_forbidden"] = False

                # privacy: photo_forbidden
                if rule_enabled(config, "photo_forbidden"):
                    if resource.get("photo"):
                        issues.append(
                            {
                                "rule": "photo_forbidden",
                                "severity": config["photo_forbidden"]["severity"],
                                "message": "Patient.photo is present and must be removed.",
                            }
                        )
                        metrics["photo_forbidden"] = False

                # privacy: pseudonym_format_check (Patient.id)
                if rule_enabled(config, "pseudonym_format_check"):
                    pattern = config["pseudonym_format_check"].get("pattern")
                    if pattern:
                        if re.match(pattern, rid):
                            issues.append(
                                {
                                    "rule": "pseudonym_format_check",
                                    "severity": config["pseudonym_format_check"][
                                        "severity"
                                    ],
                                    "message": f"Patient.id '{rid}' is not pseudonymized.",
                                }
                            )
                            metrics["pseudonym_format_check"] = False

                # privacy: identifier_pseudonym_check
                if rule_enabled(config, "identifier_pseudonym_check"):
                    pattern = config["identifier_pseudonym_check"].get("pattern")
                    if pattern:
                        for ident in resource.get("identifier", []):
                            value = ident.get("value", "")
                            if value and re.match(pattern, value):
                                issues.append(
                                    {
                                        "rule": "identifier_pseudonym_check",
                                        "severity": config[
                                            "identifier_pseudonym_check"
                                        ]["severity"],
                                        "message": f"Patient.identifier value '{value}' not pseudonymized.",
                                    }
                                )
                                metrics["identifier_pseudonym_check"] = False
                                break

                # ============================= completeness  ==============================

                # completeness: has_observation
                if rule_enabled(config, "has_observation"):
                    if rid not in patients_with_observation:
                        issues.append(
                            {
                                "rule": "has_observation",
                                "severity": config["has_observation"]["severity"],
                                "message": f"Patient/{rid} has no linked Observation.",
                            }
                        )
                        metrics["has_observation"] = False

                # completeness: has_condition
                if rule_enabled(config, "has_condition"):
                    if rid not in patients_with_condition:
                        issues.append(
                            {
                                "rule": "has_condition",
                                "severity": config["has_condition"]["severity"],
                                "message": f"Patient/{rid} has no linked Condition.",
                            }
                        )
                        metrics["has_condition"] = False

                # Identifier Required
                if rule_enabled(config, "identifier_required"):
                    if not resource.get("identifier"):
                        issues.append(
                            {
                                "rule": "identifier_required",
                                "severity": config["identifier_required"]["severity"],
                                "message": "Patient.identifier is missing. At least one identifier is required. ",
                            }
                        )
                        metrics["identifier_required"] = False

                # birthdate_required
                if rule_enabled(config, "birthdate_required"):
                    if not resource.get("birthDate"):
                        issues.append(
                            {
                                "rule": "birthdate_required",
                                "severity": config["birthdate_required"]["severity"],
                                "message": "Patient.birthDate is missing.",
                            }
                        )
                        metrics["birthdate_required"] = False

                # gender_required
                if rule_enabled(config, "gender_required"):
                    if not resource.get("gender"):
                        issues.append(
                            {
                                "rule": "gender_required",
                                "severity": config["gender_required"]["severity"],
                                "message": "Patient.gender is missing.",
                            }
                        )
                        metrics["gender_required"] = False

                # ======================= plausibility:================================
                # birthdate_not_future
                if rule_enabled(config, "birthdate_not_future"):
                    bd = resource.get("birthDate", "")
                    if bd and self._is_future(bd):
                        issues.append(
                            {
                                "rule": "birthdate_not_future",
                                "severity": config["birthdate_not_future"]["severity"],
                                "message": f"Patient.birthDate '{bd}' is in the future.",
                            }
                        )
                        metrics["birthdate_not_future"] = False

                # plausibility: birthdate_plausible_range
                if rule_enabled(config, "birthdate_plausible_range"):
                    bd = resource.get("birthDate", "")
                    if bd:
                        try:
                            bd_year = int(bd[:4])
                            if datetime.now().year - bd_year > 150:
                                issues.append(
                                    {
                                        "rule": "birthdate_plausible_range",
                                        "severity": config["birthdate_plausible_range"][
                                            "severity"
                                        ],
                                        "message": f"Patient.birthDate '{bd}' is more than 150 years in the past. ",
                                    }
                                )
                                metrics["birthdate_plausible_range"] = False
                        except ValueError:
                            pass

                if issues:
                    page_invalid += 1
                    await self.save_invalid(run_id, "Patient", rid, issues, metrics, db)

            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "Patient", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="Patient",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )


# =============================================================================
# ENCOUNTER
# =============================================================================
class EncounterValidator(BaseValidator):
    """Encounter Validator"""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save the Fall resources."""
        config = await get_config_for_run(self.server_id, "Encounter", db)

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0

        estimated_total = await self._fetch_total("Encounter")

        async for entries in self.iter_pages("Encounter", run_id, db):
            pages_done += 1

            page_processed = 0
            page_invalid = 0

            for entry in entries:
                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)

                #  ============= privacy =====================

                if rule_enabled(config, "pseudonym_format_check"):
                    pattern = config["pseudonym_format_check"].get("pattern")
                    if pattern:
                        # ID prüfen
                        if re.match(pattern, rid):
                            issues.append(
                                {
                                    "rule": "pseudonym_format_check",
                                    "severity": config["pseudonym_format_check"][
                                        "severity"
                                    ],
                                    "message": f"Encounter.id '{rid}' is not pseudonymized.",
                                }
                            )
                            metrics["pseudonym_format_check"] = False

                        # Identifier prüfen
                        for ident in resource.get("identifier", []):
                            value = ident.get("value", "")
                            if value and re.match(pattern, value):
                                issues.append(
                                    {
                                        "rule": "pseudonym_format_check",
                                        "severity": config["pseudonym_format_check"][
                                            "severity"
                                        ],
                                        "message": f"Encounter.identifier value '{value}' is not pseudonymized.",
                                    }
                                )
                                metrics["pseudonym_format_check"] = False
                                break

                #  ============== completeness: ==================

                # status_required
                if rule_enabled(config, "status_required"):
                    if not resource.get("status"):
                        issues.append(
                            {
                                "rule": "status_required",
                                "severity": config["status_required"]["severity"],
                                "message": "Encounter.status is missing.",
                            }
                        )
                        metrics["status_required"] = False

                # class_required
                if rule_enabled(config, "class_required"):
                    if not resource.get("class"):
                        issues.append(
                            {
                                "rule": "class_required",
                                "severity": config["class_required"]["severity"],
                                "message": "Encounter.class is missing.",
                            }
                        )
                        metrics["class_required"] = False

                # subject_required
                if rule_enabled(config, "subject_required"):
                    if not resource.get("subject"):
                        issues.append(
                            {
                                "rule": "subject_required",
                                "severity": config["subject_required"]["severity"],
                                "message": "Encounter.subject is missing.",
                            }
                        )
                        metrics["subject_required"] = False

                # period_start_required
                if rule_enabled(config, "period_start_required"):
                    period = resource.get("period", {})
                    if not period or not period.get("start"):
                        issues.append(
                            {
                                "rule": "period_start_required",
                                "severity": config["period_start_required"]["severity"],
                                "message": "Encounter.period.start is missing.",
                            }
                        )
                        metrics["period_start_required"] = False

                #  ================ plausibility: ==================

                # period_end_after_start
                if rule_enabled(config, "period_end_after_start"):
                    period = resource.get("period", {})
                    start = period.get("start")
                    end = period.get("end")
                    if start and end:
                        try:
                            if self._end_before_start(start, end):
                                issues.append(
                                    {
                                        "rule": "period_end_after_start",
                                        "severity": config["period_end_after_start"][
                                            "severity"
                                        ],
                                        "message": (
                                            f"Encounter.period.end '{end}' is before "
                                            f"period.start '{start}'."
                                        ),
                                    }
                                )
                                metrics["period_end_after_start"] = False
                        except ValueError:
                            pass

                #  period_plausible_duration
                if rule_enabled(config, "period_plausible_duration"):
                    period = resource.get("period", {})
                    start = period.get("start")
                    end = period.get("end")
                    if start and end:
                        try:
                            duration_days = (
                                self._as_utc(end) - self._as_utc(start)
                            ).days
                            if duration_days > 730:
                                issues.append(
                                    {
                                        "rule": "period_plausible_duration",
                                        "severity": config["period_plausible_duration"][
                                            "severity"
                                        ],
                                        "message": f"Encounter duration is {duration_days} days, which exceeds 730 days.",
                                    }
                                )
                                metrics["period_plausible_duration"] = False
                        except ValueError:
                            pass

                # ========= integrity: ===============

                # subject_reference_format
                if rule_enabled(config, "subject_reference_format"):
                    ref = resource.get("subject", {}).get("reference", "")
                    if ref and not self._is_reference_format(ref, "Patient"):
                        issues.append(
                            {
                                "rule": "subject_reference_format",
                                "severity": config["subject_reference_format"][
                                    "severity"
                                ],
                                "message": f"Encounter.subject.reference '{ref}'must follow 'Patient/{{id}}' format.",
                            }
                        )
                        metrics["subject_reference_format"] = False

                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, "Encounter", rid, issues, metrics, db
                    )

            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "Encounter", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="Encounter",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )


# =============================================================================
# OBSERVATION
# =============================================================================
class ObservationValidator(BaseValidator):
    """Observation Validators"""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save the resources Observations."""

        config = await get_config_for_run(self.server_id, "Observation", db)

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0
        estimated_total = await self._fetch_total("Observation")

        async for entries in self.iter_pages("Observation", run_id, db):
            pages_done += 1
            page_processed = 0
            page_invalid = 0

            for entry in entries:

                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)
                # ======== privacy: ===========
                #
                # value_string_cleartext_forbidden
                if rule_enabled(config, "value_string_cleartext_forbidden"):
                    value_string = resource.get("valueString", "")
                    if value_string and len(value_string) > 50:
                        issues.append(
                            {
                                "rule": "value_string_cleartext_forbidden",
                                "severity": config["value_string_cleartext_forbidden"][
                                    "severity"
                                ],
                                "message": """
                                    Observation.valueString containsa long string that may include personal data.""",
                            }
                        )
                        metrics["value_string_cleartext_forbidden"] = False

                # ========== completeness:  =========
                #
                # status_required
                if rule_enabled(config, "status_required"):
                    if not resource.get("status"):
                        issues.append(
                            {
                                "rule": "status_required",
                                "severity": config["status_required"]["severity"],
                                "message": "Observation.status is missing.",
                            }
                        )
                        metrics["status_required"] = False

                # code_required
                if rule_enabled(config, "code_required"):
                    if not resource.get("code"):
                        issues.append(
                            {
                                "rule": "code_required",
                                "severity": config["code_required"]["severity"],
                                "message": "Observation.code is missing.",
                            }
                        )
                        metrics["code_required"] = False

                # subject_required
                if rule_enabled(config, "subject_required"):
                    if not resource.get("subject"):
                        issues.append(
                            {
                                "rule": "subject_required",
                                "severity": config["subject_required"]["severity"],
                                "message": "Observation.subject is missing.",
                            }
                        )
                        metrics["subject_required"] = False

                # effective_required
                if rule_enabled(config, "effective_required"):
                    has_effective = (
                        resource.get("effectiveDateTime")
                        or resource.get("effectivePeriod")
                        or resource.get("effectiveInstant")
                    )
                    if not has_effective:
                        issues.append(
                            {
                                "rule": "effective_required",
                                "severity": config["effective_required"]["severity"],
                                "message": "Observation.effective[x] is missing.",
                            }
                        )
                        metrics["effective_required"] = False

                # value_present
                if rule_enabled(config, "value_present"):
                    has_value = any(
                        resource.get(f)
                        for f in [
                            "valueQuantity",
                            "valueCodeableConcept",
                            "valueString",
                            "valueBoolean",
                            "valueInteger",
                            "valueRange",
                            "valueRatio",
                            "valueSampledData",
                            "valueTime",
                            "valueDateTime",
                            "valuePeriod",
                            "dataAbsentReason",
                        ]
                    )
                    if not has_value:
                        issues.append(
                            {
                                "rule": "value_present",
                                "severity": config["value_present"]["severity"],
                                "message": "Observation has no value[x] and no dataAbsentReason.",
                            }
                        )
                        metrics["value_present"] = False

                # ========= plausibility: ==========
                #
                #  effective_not_future
                if rule_enabled(config, "effective_not_future"):
                    eff = resource.get("effectiveDateTime") or resource.get(
                        "effectiveInstant"
                    )
                    if eff and self._is_future(eff):
                        issues.append(
                            {
                                "rule": "effective_not_future",
                                "severity": config["effective_not_future"]["severity"],
                                "message": f"Observation.effectiveDateTime '{eff}' is in the future.",
                            }
                        )
                        metrics["effective_not_future"] = False

                # ========= integrity: =============
                #
                # subject_reference_format
                if rule_enabled(config, "subject_reference_format"):
                    ref = resource.get("subject", {}).get("reference", "")
                    if ref and not self._is_reference_format(ref, "Patient"):
                        issues.append(
                            {
                                "rule": "subject_reference_format",
                                "severity": config["subject_reference_format"][
                                    "severity"
                                ],
                                "message": f"""Observation.subject.reference
                                 '{ref}' must follow 
                                 'Patient/{{id}}' format.""",
                            }
                        )
                        metrics["subject_reference_format"] = False

                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, "Observation", rid, issues, metrics, db
                    )
            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "Observation", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="Observation",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )

        logger.info("Observation validation complete for run %s", run_id)


# =============================================================================
# MEDICATION
# =============================================================================
class MedicationValidator(BaseValidator):
    """Medication Validatin Class"""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and Saving Medication"""
        config = await get_config_for_run(self.server_id, "Medication", db)

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0

        estimated_total = await self._fetch_total("Medication")

        async for entries in self.iter_pages("Medication", run_id, db):
            pages_done += 1
            page_processed = 0
            page_invalid = 0

            for entry in entries:
                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)

                # ========== completeness: ============
                #
                # code_required
                if rule_enabled(config, "code_required"):
                    code = resource.get("code", {})
                    if not code or (not code.get("coding") and not code.get("text")):
                        issues.append(
                            {
                                "rule": "code_required",
                                "severity": config["code_required"]["severity"],
                                "message": """Medication.code is
                                    missing or has neither 
                                    coding nor text.""",
                            }
                        )
                        metrics["code_required"] = False

                # code_coding_present
                if rule_enabled(config, "code_coding_present"):
                    code = resource.get("code", {})
                    if code and not code.get("coding"):
                        issues.append(
                            {
                                "rule": "code_coding_present",
                                "severity": config["code_coding_present"]["severity"],
                                "message": "Medication.code.coding is missing.",
                            }
                        )
                        metrics["code_coding_present"] = False

                # ======= plausibility: =======
                #
                # ingredient_item_check
                if rule_enabled(config, "ingredient_item_check"):
                    for ingredient in resource.get("ingredient", []):
                        has_codeable = ingredient.get("itemCodeableConcept")
                        has_reference = ingredient.get("itemReference")
                        if not has_codeable and not has_reference:
                            issues.append(
                                {
                                    "rule": "ingredient_item_check",
                                    "severity": config["ingredient_item_check"][
                                        "severity"
                                    ],
                                    "message": "Medication.ingredient has no itemCodeableConcept or itemReference.",
                                }
                            )
                            metrics["ingredient_item_check"] = False
                            break

                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, "Medication", rid, issues, metrics, db
                    )

            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "Medication", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="Medication",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )

        logger.info("Medication validation complete for run %s", run_id)


# =============================================================================
# MEDICATIONREQUEST
# =============================================================================
class MedicationRequestValidator(BaseValidator):
    "MedicationRequest Validator."

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        "Validate and save the resources Medicationrequests."

        config = await get_config_for_run(self.server_id, "MedicationRequest", db)

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0
        estimated_total = await self._fetch_total("MedicationRequest")

        async for entries in self.iter_pages("MedicationRequest", run_id, db):
            pages_done += 1
            page_processed = 0
            page_invalid = 0

            for entry in entries:
                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)

                # =========  completeness: ===========
                #
                # status_required
                if rule_enabled(config, "status_required"):
                    if not resource.get("status"):
                        issues.append(
                            {
                                "rule": "status_required",
                                "severity": config["status_required"]["severity"],
                                "message": "MedicationRequest.status is missing.",
                            }
                        )
                        metrics["status_required"] = False

                # intent_required
                if rule_enabled(config, "intent_required"):
                    if not resource.get("intent"):
                        issues.append(
                            {
                                "rule": "intent_required",
                                "severity": config["intent_required"]["severity"],
                                "message": "MedicationRequest.intent is missing.",
                            }
                        )
                        metrics["intent_required"] = False

                # medication_required
                if rule_enabled(config, "medication_required"):
                    if not resource.get("medicationReference") and not resource.get(
                        "medicationCodeableConcept"
                    ):
                        issues.append(
                            {
                                "rule": "medication_required",
                                "severity": config["medication_required"]["severity"],
                                "message": "MedicationRequest.medication[x] is missing.",
                            }
                        )
                        metrics["medication_required"] = False

                #  subject_required
                if rule_enabled(config, "subject_required"):
                    if not resource.get("subject"):
                        issues.append(
                            {
                                "rule": "subject_required",
                                "severity": config["subject_required"]["severity"],
                                "message": "MedicationRequest.subject is missing.",
                            }
                        )
                        metrics["subject_required"] = False

                #  authored_on_required
                if rule_enabled(config, "authored_on_required"):
                    has_authored = resource.get("authoredOn")
                    has_bounds = any(
                        d.get("timing", {}).get("repeat", {}).get("boundsPeriod")
                        for d in resource.get("dosageInstruction", [])
                    )
                    if not has_authored and not has_bounds:
                        issues.append(
                            {
                                "rule": "authored_on_required",
                                "severity": config["authored_on_required"]["severity"],
                                "message": "MedicationRequest.authoredOn is missing and no boundsPeriod in dosageInstruction.",
                            }
                        )
                        metrics["authored_on_required"] = False

                # plausibility: authored_not_future
                if rule_enabled(config, "authored_not_future"):
                    authored = resource.get("authoredOn", "")
                    if authored and self._is_future(authored):
                        issues.append(
                            {
                                "rule": "authored_not_future",
                                "severity": config["authored_not_future"]["severity"],
                                "message": f"MedicationRequest.authoredOn '{authored}' is in the future.",
                            }
                        )
                        metrics["authored_not_future"] = False

                # integrity: subject_reference_format
                if rule_enabled(config, "subject_reference_format"):
                    ref = resource.get("subject", {}).get("reference", "")
                    if ref and not self._is_reference_format(ref, "Patient"):
                        issues.append(
                            {
                                "rule": "subject_reference_format",
                                "severity": config["subject_reference_format"][
                                    "severity"
                                ],
                                "message": f"MedicationRequest.subject.reference '{ref}' must follow 'Patient/{{id}}' format.",
                            }
                        )
                        metrics["subject_reference_format"] = False

                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, "MedicationRequest", rid, issues, metrics, db
                    )

            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "MedicationRequest", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="MedicationRequest",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )

        logger.info("MedicationRequest validation complete for run %s", run_id)


# =============================================================================
# MEDICATIONADMINISTRATION
# =============================================================================
class MedicationAdministrationValidator(BaseValidator):
    """Medication Administration Validator"""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save the resources Medicationadministrations"""

        config = await get_config_for_run(
            self.server_id, "MedicationAdministration", db
        )

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0
        estimated_total = await self._fetch_total("MedicationAdministration")

        async for entries in self.iter_pages("MedicationAdministration", run_id, db):
            pages_done += 1
            page_processed = 0
            page_invalid = 0

            for entry in entries:
                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)

                # completeness: status_required
                if rule_enabled(config, "status_required"):
                    if not resource.get("status"):
                        issues.append(
                            {
                                "rule": "status_required",
                                "severity": config["status_required"]["severity"],
                                "message": "MedicationAdministration.status is missing.",
                            }
                        )
                        metrics["status_required"] = False

                # completeness: medication_required
                if rule_enabled(config, "medication_required"):
                    if not resource.get("medicationReference") and not resource.get(
                        "medicationCodeableConcept"
                    ):
                        issues.append(
                            {
                                "rule": "medication_required",
                                "severity": config["medication_required"]["severity"],
                                "message": "MedicationAdministration.medication[x] is missing.",
                            }
                        )
                        metrics["medication_required"] = False

                # completeness: subject_required
                if rule_enabled(config, "subject_required"):
                    if not resource.get("subject"):
                        issues.append(
                            {
                                "rule": "subject_required",
                                "severity": config["subject_required"]["severity"],
                                "message": "MedicationAdministration.subject is missing.",
                            }
                        )
                        metrics["subject_required"] = False

                # completeness: effective_required
                if rule_enabled(config, "effective_required"):
                    if not resource.get("effectiveDateTime") and not resource.get(
                        "effectivePeriod"
                    ):
                        issues.append(
                            {
                                "rule": "effective_required",
                                "severity": config["effective_required"]["severity"],
                                "message": "MedicationAdministration.effective[x] is missing.",
                            }
                        )
                        metrics["effective_required"] = False

                # plausibility: effective_not_future
                if rule_enabled(config, "effective_not_future"):
                    eff = resource.get("effectiveDateTime", "")
                    if eff and self._is_future(eff):
                        issues.append(
                            {
                                "rule": "effective_not_future",
                                "severity": config["effective_not_future"]["severity"],
                                "message": f"MedicationAdministration.effectiveDateTime '{eff}' is in the future.",
                            }
                        )
                        metrics["effective_not_future"] = False

                # plausibility: effective_period_end_after_start
                if rule_enabled(config, "effective_period_end_after_start"):
                    period = resource.get("effectivePeriod", {})
                    start = period.get("start")
                    end = period.get("end")
                    if start and end:
                        try:
                            if self._end_before_start(start, end):
                                issues.append(
                                    {
                                        "rule": "effective_period_end_after_start",
                                        "severity": config[
                                            "effective_period_end_after_start"
                                        ]["severity"],
                                        "message": "MedicationAdministration.effectivePeriod.end is before start.",
                                    }
                                )
                                metrics["effective_period_end_after_start"] = False
                        except ValueError:
                            pass

                # integrity: subject_reference_format
                if rule_enabled(config, "subject_reference_format"):
                    ref = resource.get("subject", {}).get("reference", "")
                    if ref and not self._is_reference_format(ref, "Patient"):
                        issues.append(
                            {
                                "rule": "subject_reference_format",
                                "severity": config["subject_reference_format"][
                                    "severity"
                                ],
                                "message": f"MedicationAdministration.subject.reference '{ref}' must follow 'Patient/{{id}}' format.",
                            }
                        )
                        metrics["subject_reference_format"] = False

                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, "MedicationAdministration", rid, issues, metrics, db
                    )

            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "MedicationAdministration", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="MedicationAdministration",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )

        logger.info("MedicationAdministration validation complete for run %s", run_id)


# =============================================================================
# CONDITION
# =============================================================================
class ConditionValidator(BaseValidator):
    """Condition (Diagnose) Validator."""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save Condition resources."""
        config = await get_config_for_run(self.server_id, "Condition", db)

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0

        estimated_total = await self._fetch_total("Condition")

        async for entries in self.iter_pages("Condition", run_id, db):
            pages_done += 1
            page_processed = 0
            page_invalid = 0

            for entry in entries:
                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)

                # ========== privacy ==========

                if rule_enabled(config, "note_cleartext_check"):
                    for note in resource.get("note", []):
                        text = note.get("text", "")
                        if text and len(text) > 50:
                            issues.append(
                                {
                                    "rule": "note_cleartext_check",
                                    "severity": config["note_cleartext_check"][
                                        "severity"
                                    ],
                                    "message": "Condition.note contains a long free-text string that may include personal data.",
                                }
                            )
                            metrics["note_cleartext_check"] = False
                            break

                # ========== completeness ==========

                if rule_enabled(config, "code_required"):
                    if not resource.get("code"):
                        issues.append(
                            {
                                "rule": "code_required",
                                "severity": config["code_required"]["severity"],
                                "message": "Condition.code is missing.",
                            }
                        )
                        metrics["code_required"] = False

                if rule_enabled(config, "subject_required"):
                    if not resource.get("subject"):
                        issues.append(
                            {
                                "rule": "subject_required",
                                "severity": config["subject_required"]["severity"],
                                "message": "Condition.subject is missing.",
                            }
                        )
                        metrics["subject_required"] = False

                if rule_enabled(config, "clinicalstatus_required"):
                    if not resource.get("clinicalStatus"):
                        issues.append(
                            {
                                "rule": "clinicalstatus_required",
                                "severity": config["clinicalstatus_required"][
                                    "severity"
                                ],
                                "message": "Condition.clinicalStatus is missing.",
                            }
                        )
                        metrics["clinicalstatus_required"] = False

                if rule_enabled(config, "verificationstatus_required"):
                    if not resource.get("verificationStatus"):
                        issues.append(
                            {
                                "rule": "verificationstatus_required",
                                "severity": config["verificationstatus_required"][
                                    "severity"
                                ],
                                "message": "Condition.verificationStatus is missing.",
                            }
                        )
                        metrics["verificationstatus_required"] = False

                if rule_enabled(config, "onset_present"):
                    has_onset = any(
                        resource.get(f)
                        for f in [
                            "onsetDateTime",
                            "onsetAge",
                            "onsetPeriod",
                            "onsetRange",
                            "onsetString",
                        ]
                    )
                    if not has_onset:
                        issues.append(
                            {
                                "rule": "onset_present",
                                "severity": config["onset_present"]["severity"],
                                "message": "Condition.onset[x] is missing.",
                            }
                        )
                        metrics["onset_present"] = False

                # ========== integrity ==========

                if rule_enabled(config, "subject_reference_format"):
                    ref = resource.get("subject", {}).get("reference", "")
                    if ref and not self._is_reference_format(ref, "Patient"):
                        issues.append(
                            {
                                "rule": "subject_reference_format",
                                "severity": config["subject_reference_format"][
                                    "severity"
                                ],
                                "message": f"Condition.subject.reference '{ref}' must follow 'Patient/{{id}}' format.",
                            }
                        )
                        metrics["subject_reference_format"] = False

                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, "Condition", rid, issues, metrics, db
                    )

            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "Condition", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="Condition",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )

        logger.info("Condition validation complete for run %s", run_id)


# =============================================================================
# PROCEDURE
# =============================================================================
class ProcedureValidator(BaseValidator):
    """Procedure (Prozedur) Validator."""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save Procedure resources."""
        config = await get_config_for_run(self.server_id, "Procedure", db)

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0

        estimated_total = await self._fetch_total("Procedure")

        async for entries in self.iter_pages("Procedure", run_id, db):
            pages_done += 1
            page_processed = 0
            page_invalid = 0

            for entry in entries:
                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)

                # ========== privacy ==========

                if rule_enabled(config, "note_cleartext_check"):
                    for note in resource.get("note", []):
                        text = note.get("text", "")
                        if text and len(text) > 50:
                            issues.append(
                                {
                                    "rule": "note_cleartext_check",
                                    "severity": config["note_cleartext_check"][
                                        "severity"
                                    ],
                                    "message": "Procedure.note contains a long free-text string that may include personal data.",
                                }
                            )
                            metrics["note_cleartext_check"] = False
                            break

                # ========== completeness ==========

                if rule_enabled(config, "status_required"):
                    if not resource.get("status"):
                        issues.append(
                            {
                                "rule": "status_required",
                                "severity": config["status_required"]["severity"],
                                "message": "Procedure.status is missing.",
                            }
                        )
                        metrics["status_required"] = False

                if rule_enabled(config, "code_required"):
                    if not resource.get("code"):
                        issues.append(
                            {
                                "rule": "code_required",
                                "severity": config["code_required"]["severity"],
                                "message": "Procedure.code is missing.",
                            }
                        )
                        metrics["code_required"] = False

                if rule_enabled(config, "subject_required"):
                    if not resource.get("subject"):
                        issues.append(
                            {
                                "rule": "subject_required",
                                "severity": config["subject_required"]["severity"],
                                "message": "Procedure.subject is missing.",
                            }
                        )
                        metrics["subject_required"] = False

                if rule_enabled(config, "performed_required"):
                    has_performed = (
                        resource.get("performedDateTime")
                        or resource.get("performedPeriod")
                        or resource.get("performedString")
                        or resource.get("performedAge")
                        or resource.get("performedRange")
                    )
                    if not has_performed:
                        issues.append(
                            {
                                "rule": "performed_required",
                                "severity": config["performed_required"]["severity"],
                                "message": "Procedure.performed[x] is missing.",
                            }
                        )
                        metrics["performed_required"] = False

                # ========== integrity ==========

                if rule_enabled(config, "subject_reference_format"):
                    ref = resource.get("subject", {}).get("reference", "")
                    if ref and not self._is_reference_format(ref, "Patient"):
                        issues.append(
                            {
                                "rule": "subject_reference_format",
                                "severity": config["subject_reference_format"][
                                    "severity"
                                ],
                                "message": f"Procedure.subject.reference '{ref}' must follow 'Patient/{{id}}' format.",
                            }
                        )
                        metrics["subject_reference_format"] = False

                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, "Procedure", rid, issues, metrics, db
                    )

            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "Procedure", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="Procedure",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )

        logger.info("Procedure validation complete for run %s", run_id)


# =============================================================================
# DIAGNOSTICREPORT
# =============================================================================
class DiagnosticReportValidator(BaseValidator):
    """DiagnosticReport Validator."""

    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save DiagnosticReport resources."""
        config = await get_config_for_run(self.server_id, "DiagnosticReport", db)

        start_time = monotonic()
        pages_done = 0
        cumulative_processed = 0
        cumulative_invalid = 0

        estimated_total = await self._fetch_total("DiagnosticReport")

        async for entries in self.iter_pages("DiagnosticReport", run_id, db):
            pages_done += 1
            page_processed = 0
            page_invalid = 0

            for entry in entries:
                page_processed += 1
                resource = entry.get("resource", {})
                rid = resource.get("id", "")
                issues = []
                metrics = self._build_metrics(config)

                # ========== privacy ==========

                if rule_enabled(config, "note_cleartext_check"):
                    # DiagnosticReport uses 'conclusion' (string) and 'text' (Narrative)
                    conclusion = resource.get("conclusion", "")
                    narrative_div = resource.get("text", {}).get("div", "")
                    flagged = (conclusion and len(conclusion) > 50) or (
                        narrative_div and len(narrative_div) > 100
                    )
                    if flagged:
                        issues.append(
                            {
                                "rule": "note_cleartext_check",
                                "severity": config["note_cleartext_check"]["severity"],
                                "message": "DiagnosticReport.conclusion or text.div contains a long free-text string that may include personal data.",
                            }
                        )
                        metrics["note_cleartext_check"] = False

                # ========== completeness ==========

                if rule_enabled(config, "status_required"):
                    if not resource.get("status"):
                        issues.append(
                            {
                                "rule": "status_required",
                                "severity": config["status_required"]["severity"],
                                "message": "DiagnosticReport.status is missing.",
                            }
                        )
                        metrics["status_required"] = False

                if rule_enabled(config, "code_required"):
                    if not resource.get("code"):
                        issues.append(
                            {
                                "rule": "code_required",
                                "severity": config["code_required"]["severity"],
                                "message": "DiagnosticReport.code is missing.",
                            }
                        )
                        metrics["code_required"] = False

                if rule_enabled(config, "subject_required"):
                    if not resource.get("subject"):
                        issues.append(
                            {
                                "rule": "subject_required",
                                "severity": config["subject_required"]["severity"],
                                "message": "DiagnosticReport.subject is missing.",
                            }
                        )
                        metrics["subject_required"] = False

                # ========== integrity ==========

                if rule_enabled(config, "subject_reference_format"):
                    ref = resource.get("subject", {}).get("reference", "")
                    if ref and not self._is_reference_format(ref, "Patient"):
                        issues.append(
                            {
                                "rule": "subject_reference_format",
                                "severity": config["subject_reference_format"][
                                    "severity"
                                ],
                                "message": f"DiagnosticReport.subject.reference '{ref}' must follow 'Patient/{{id}}' format.",
                            }
                        )
                        metrics["subject_reference_format"] = False

                if issues:
                    page_invalid += 1
                    await self.save_invalid(
                        run_id, "DiagnosticReport", rid, issues, metrics, db
                    )

            cumulative_processed += page_processed
            cumulative_invalid += page_invalid

            await self._update_run_counters(
                run_id, "DiagnosticReport", page_processed, page_invalid, db
            )

            await self._emit_progress(
                run_id=run_id,
                resource_type="DiagnosticReport",
                total_processed=cumulative_processed,
                total_invalid=cumulative_invalid,
                pages_done=pages_done,
                estimated_total=estimated_total,
                start_time=start_time,
            )

        logger.info("DiagnosticReport validation complete for run %s", run_id)


# =============================================================================
# VALIDATORS REGISTRY
# =============================================================================
VALIDATORS: dict[str, type[BaseValidator]] = {
    "Patient": PatientValidator,
    "Encounter": EncounterValidator,
    "Observation": ObservationValidator,
    "Medication": MedicationValidator,
    "MedicationRequest": MedicationRequestValidator,
    "MedicationAdministration": MedicationAdministrationValidator,
    "Condition": ConditionValidator,
    "Procedure": ProcedureValidator,
    "DiagnosticReport": DiagnosticReportValidator,
}
