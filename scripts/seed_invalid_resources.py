"""
Seed script: posts 20 deliberately invalid Patient and 20 invalid Encounter
resources to a FHIR server, covering all rules our validators check.

Usage:
    python scripts/seed_invalid_resources.py \
        --base-url https://dizfhir.med.uni-giessen.de/test/fhir \
        --username myuser \
        --password mypass

The script prints a summary of created resource IDs grouped by violation type.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta

import httpx


# ---------------------------------------------------------------------------
# PATIENT — 20 resources covering all Patient-validator rules
# ---------------------------------------------------------------------------
def patient_payloads() -> list[tuple[str, dict]]:
    """Returns list of (violation_label, fhir_resource)."""
    out: list[tuple[str, dict]] = []

    def base() -> dict:
        return {
            "resourceType": "Patient",
            "identifier": [
                {"system": "http://verity.test/pseudonym", "value": "PSEUDO123"}
            ],
            "gender": "male",
            "birthDate": "1980-01-15",
        }

    # name_forbidden (3x)
    for fam in ["Mustermann", "Sauer", "Schmidt"]:
        p = base()
        p["name"] = [{"family": fam, "given": ["Max"]}]
        out.append(("name_forbidden", p))

    # address_forbidden (3x)
    for city in ["Gießen", "Frankfurt", "Berlin"]:
        p = base()
        p["address"] = [
            {
                "line": ["Musterstraße 5"],
                "city": city,
                "postalCode": "35392",
                "country": "DE",
            }
        ]
        out.append(("address_forbidden", p))

    # telecom_forbidden (2x)
    for val in ["+49 641 12345", "test@example.com"]:
        p = base()
        p["telecom"] = [{"system": "phone", "value": val}]
        out.append(("telecom_forbidden", p))

    # photo_forbidden (2x)
    for _ in range(2):
        p = base()
        p["photo"] = [{"contentType": "image/jpeg", "data": "dGVzdA=="}]
        out.append(("photo_forbidden", p))

    # birthdate_required (2x) — birthDate missing
    for _ in range(2):
        p = base()
        del p["birthDate"]
        out.append(("birthdate_required", p))

    # gender_required (2x) — gender missing
    for _ in range(2):
        p = base()
        del p["gender"]
        out.append(("gender_required", p))

    # birthdate_not_future (1x)
    p = base()
    future = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    p["birthDate"] = future
    out.append(("birthdate_not_future", p))

    # birthdate_plausible_range (1x) — >150 years ago
    p = base()
    p["birthDate"] = "1800-01-01"
    out.append(("birthdate_plausible_range", p))

    # identifier_required (2x) — no identifier
    for _ in range(2):
        p = base()
        del p["identifier"]
        out.append(("identifier_required", p))

    # Combined violation (2x) — name + telecom together
    for fam in ["Funk", "Becker"]:
        p = base()
        p["name"] = [{"family": fam, "given": ["Anna"]}]
        p["telecom"] = [{"system": "email", "value": "anna@test.de"}]
        out.append(("combined_name_telecom", p))

    return out


# ---------------------------------------------------------------------------
# ENCOUNTER — 20 resources covering all Encounter-validator rules
# ---------------------------------------------------------------------------
def encounter_payloads(patient_ref: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []

    def base() -> dict:
        return {
            "resourceType": "Encounter",
            "status": "finished",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "IMP",
                "display": "inpatient",
            },
            "subject": {"reference": patient_ref},
            "period": {
                "start": "2025-01-15T08:00:00+01:00",
                "end": "2025-01-20T16:00:00+01:00",
            },
        }

    # status_required (3x)
    for _ in range(3):
        e = base()
        del e["status"]
        out.append(("status_required", e))

    # class_required (3x)
    for _ in range(3):
        e = base()
        del e["class"]
        out.append(("class_required", e))

    # subject_required (3x)
    for _ in range(3):
        e = base()
        del e["subject"]
        out.append(("subject_required", e))

    # period_start_required (2x)
    for _ in range(2):
        e = base()
        e["period"] = {"end": "2025-01-20T16:00:00+01:00"}
        out.append(("period_start_required", e))

    # period_end_after_start (3x) — end before start
    for _ in range(3):
        e = base()
        e["period"] = {
            "start": "2025-06-15T10:00:00+01:00",
            "end": "2025-06-10T10:00:00+01:00",
        }
        out.append(("period_end_after_start", e))

    # period_plausible_duration (2x) — > 730 days
    for _ in range(2):
        e = base()
        e["period"] = {
            "start": "2020-01-01T00:00:00+01:00",
            "end": "2025-01-01T00:00:00+01:00",
        }
        out.append(("period_plausible_duration", e))

    # subject_reference_format (2x) — wrong format
    for ref in ["12345", "PatientReference/abc"]:
        e = base()
        e["subject"] = {"reference": ref}
        out.append(("subject_reference_format", e))

    # Combined (2x) — no status + no period.start
    for _ in range(2):
        e = base()
        del e["status"]
        e["period"] = {"end": "2025-01-20T16:00:00+01:00"}
        out.append(("combined_status_period", e))

    return out


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------
async def post_resource(
    client: httpx.AsyncClient,
    base_url: str,
    resource_type: str,
    body: dict,
    auth: httpx.BasicAuth | None,
) -> str | None:
    try:
        resp = await client.post(
            f"{base_url.rstrip('/')}/{resource_type}",
            json=body,
            headers={
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json",
            },
            auth=auth,
        )
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as exc:
        print(f"  FAILED: {resource_type} — {exc}", file=sys.stderr)
        return None


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username")
    parser.add_argument("--password")
    args = parser.parse_args()

    auth = None
    if args.username and args.password:
        auth = httpx.BasicAuth(args.username, args.password)

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:

        # ----- Patients first -----
        print("Posting 20 Patients...")
        created_patients: list[tuple[str, str]] = []  # (label, id)
        for label, body in patient_payloads():
            pid = await post_resource(client, args.base_url, "Patient", body, auth)
            if pid:
                created_patients.append((label, pid))
                print(f"  [{label}] Patient/{pid}")

        if not created_patients:
            print("No patients created — cannot create Encounters. Exiting.")
            return

        # Use the first created Patient as subject for Encounters
        ref = f"Patient/{created_patients[0][1]}"
        print(f"\nUsing {ref} as subject for Encounters")

        # ----- Encounters -----
        print("\nPosting 20 Encounters...")
        created_encounters: list[tuple[str, str]] = []
        for label, body in encounter_payloads(ref):
            eid = await post_resource(client, args.base_url, "Encounter", body, auth)
            if eid:
                created_encounters.append((label, eid))
                print(f"  [{label}] Encounter/{eid}")

    # ----- Summary -----
    print("\n" + "=" * 60)
    print(f"Patients created: {len(created_patients)}/20")
    print(f"Encounters created: {len(created_encounters)}/20")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
