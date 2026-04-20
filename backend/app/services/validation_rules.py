import httpx 

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from uuid import UUID
import json
from datetime import datetime
from typing import List, Dict, Any

from app.models.invalid_resource import InvalidResource
from app.models.validation_run import ValidationRun, ValidationStatus

class BaseValidator:
    def __init__(self, client: httpx.AsyncClient, base_url: str, auth_config: dict = None):
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.auth_config = auth_config or {}


    async def fetch_bundle(self, url: str) -> dict:
        """Fetch a bundle from the FHIR server."""

        headers = {"Accept": "application/fhir+json"}
        
        # Basic Auth 
        if self.auth_config and self.auth_config.get("username") and self.auth_config.get("password"):
            auth = httpx.BasicAuth(
                username=self.auth_config["username"],
                password=self.auth_config["password"]
            )
        else:
            auth = None

        try: 
            resp = await self.client.get(url, headers=headers, auth=auth)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            print(f"HTTP {exc.response.status_code} bei {url}: {exc.response.text[:300]}")
            raise
        except Exception as e:
            print(f"Request-Fehler bei {url}: {e}")
            raise

    async def save_invalid(self, run_id: UUID, resource_type: str, resource_id: str, issues: List[str], metrics: Dict[str, Any], db: AsyncSession):
        """Save an invalid resource to the database."""
        try: 

            invalid = InvalidResource(
                run_id=str(run_id),
                server_base_url=self.base_url,
                resource_type=resource_type,
                resource_id=resource_id,
                issues=issues,
                metrics=metrics
            )
            db.add(invalid)

            # Stats
            """stmt = select(ValidationRun).where(ValidationRun.id == run_id)
            result = await db.execute(stmt)
            run = result.scalar_one_or_none()

            if run:
                run.total_processed += 1
                run.total_invalid += 1
            else: 
                print(f"Run Id nicht gleicht {ValidationRun.id} und {run_id}")


            await db.commit()
            """

            stmt = (
                update(ValidationRun)
                .where(ValidationRun.id == run_id)
                .values(
                    total_processed=ValidationRun.total_processed + 1,
                    total_invalid=ValidationRun.total_invalid + 1
                )
            )
            await db.execute(stmt)
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            if "uq_run_resource" not in str(e):
               print(f"Save error for {resource_type}/{resource_id}: {e}")

# =========================== Patient Validator ===========================
class PatientValidator(BaseValidator):
    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save the resources."""
        url = f"{self.base_url}/Patient?_count=500"
        processed = 0
        invalid_count = 0

        while url:
            bundle = await self.fetch_bundle(url)
            for entry in bundle.get("entry", []):
                processed += 1
                patient = entry.get("resource", {})
                pid = patient.get("id")
                issues = []
                metrics = {
                    "has_birthdate": True,
                    "has_gender": True,
                    "has_name": False,
                    "has_address": False,
                    "is_pseudonym": True,
                    "has_observation": True,
                    "has_condition": True,
                    
                }

                # 1. Birthdate
                if not patient.get("birthDate"):
                    issues.append("Birthdate missing")
                    metrics["has_birthdate"] = False
                
                # 2. Gender
                if not patient.get("gender"):
                    issues.append("Gender missing")
                    metrics["has_gender"] = False
                
                # 3. Pseudonym
                def is_valid_patient_id(id_str: str) -> bool:
                    if not id_str:
                        return False
                    return not (id_str.startswith("20") and len(id_str) == 9)
                
                if not is_valid_patient_id(pid):
                    issues.append("Patien ID ist not pseudonymized")
                    metrics["is_pseudonym"] = False
                
                if patient.get("identifier"):
                    for identifier in patient["identifier"]:
                       # Maybe check the System of the identifier later 

                       if identifier.get("value") and not is_valid_patient_id(identifier["value"]):
                        issues.append("Identifier is not pseudonymized")
                        metrics["is_pseudonym"] = False
                        break
                
                
                # 4. Name 
                if patient.get("name"):
                    issues.append("Patient name is present.")
                    metrics["has_name"] = True
                
                # 5. Address
                if patient.get("address"):
                    addr = patient["address"][0]
                    if addr.get("line") or addr.get("city") or addr.get("text"):
                        issues.append("Address contains forbidden fields !.")
                        metrics["has_address"] = True

                # save invalid resource
                if issues:
                    invalid_count += 1
                    await self.save_invalid(run_id, "Patient", pid, issues, metrics, db)

            # update url for next batch
            url = None
            for link in bundle.get("link", []):
                if link.get("relation") == "next":
                    url = link.get("url")
                    break
        print(f"Patient validation finished: {processed} processed, {invalid_count} invalid")


#=========================== Encounter ====================================
class EncounterValidator(BaseValidator):
    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save the resources."""
        url = f"{self.base_url}/Encounter?_count=1000"

        while url:
            bundle = await self.fetch_bundle(url)

            for entry in bundle.get("entry", []):
                encounter = entry.get("resource", {})
                eid = encounter.get("id", "")
                issues = []
                metrics = {
                    "has_period": True,
                    "has_patient": True,
                    "is_pseudonym": True,                   
                }

                # 1. Period 
                if not encounter.get("period") or not encounter["period"].get("start"):
                    issues.append("Encounter period is missing or invalid")
                    metrics["has_period"] = False
                
                # 2. Patient Reference
                subject = encounter.get("subject", {})
                if not subject or not subject.get("reference") or not subject["reference"].startswith("Patient/"):
                    issues.append("Encounter patient reference is missing")
                    metrics["has_patient"] = False
                
                # 3. Pseudonym
                def is_valid_enc_id(id_str: str) -> bool:
                    if not id_str:
                        return False
                    return not (id_str.startswith("20") and len(id_str) == 10)
                
                if not is_valid_enc_id(eid):
                    issues.append("Encounter ID is not pseudonymized")
                    metrics["is_pseudonym"] = False
                
                # save invalid resource
                if issues:
                    await self.save_invalid(run_id, "Encounter", eid, issues, metrics, db)
            
            url = next((link["url"] for link in bundle.get("link", []) if link.get("relation") == "next"), None)


# =============================== MEDICATION ============================================
class MedicationValidator(BaseValidator):
    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        """Validate and save the resources."""
        url = f"{self.base_url}/Medication?_count=1000"

        while url:
            bundle = await self.fetch_bundle(url)

            for entry in bundle.get("entry", []):
                medication = entry.get("resource", {})
                mid = medication.get("id", "")
                issues = []
                metrics = {
                    "has_code": True,
                    "is_pseudonym": True,
                    "has_ingredient": True,
                }
                

                # 1. Code 
                if not medication.get("code") or not (medication["code"].get("coding") or medication["code"].get("text")):
                    issues.append("code field missing or invalid")
                    metrics["has_code"] = False
                
                # 2. Pseudonym
                if medication.get("identifier"):
                    for ident in medication["identifier"]:
                        if ident.get("value") and ident["value"].startswith("MID"):
                            issues.append("Medication is not pseudonym")
                            metrics["is_pseudonym"] = False
                            break
                
                # 3 Ingredient 
                if medication.get("ingredient"):
                    for ingredient in medication["ingredient"]:
                        if not ingredient.get("itemCodeableConcept") or not ingredient.get("itemReference"):
                            issues.append("Ingredient is missing or invalid")
                            metrics["has_ingredient"] = False
                            break
                
                # save invalid resource
                if issues:
                    await self.save_invalid(run_id, "Medication", mid, issues, metrics, db)
            
            url = next((link["url"] for link in bundle.get("link", []) if link.get("relation") == "next"), None)




# ====================== MEDICATIONREQUEST ======================


class MedicationRequestValidator(BaseValidator):
    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        url = f"{self.base_url}/MedicationRequest?_count=1000"
        while url:
            bundle = await self.fetch_bundle(url)
            for entry in bundle.get("entry", []):
                mr = entry.get("resource", {})
                mrid = mr.get("id", "")
                issues = []
                metrics = {
                    "has_medication": True, 
                    "has_patient": True, 
                    "has_timestamp": True,
                    "is_correct_boundperiod": True, 
                    "has_status": True, 
                    "is_pseudonym": True
                }

                # 1. Medication Reference
                med_ref = mr.get("medicationReference") or mr.get("medicationCodeableConcept")
                if not med_ref:
                    issues.append("medication reference missing")
                    metrics["has_medication"] = False

                # 2. Patient Reference
                if not mr.get("subject") or "Patient" not in str(mr.get("subject")):
                    issues.append("patient reference missing")
                    metrics["has_patient"] = False

                # 3. Status
                if not mr.get("status"):
                    issues.append("status missing")
                    metrics["has_status"] = False

                # 4. Timestamp (authoredOn or boundsPeriod)
                if not mr.get("authoredOn") and not any(
                    d.get("timing", {}).get("repeat", {}).get("boundsPeriod")
                    for d in mr.get("dosageInstruction", [])
                ):
                    issues.append("timestamp missing")
                    metrics["has_timestamp"] = False

                # 5. Pseudonym
                if mr.get("identifier"):
                    for ident in mr["identifier"]:
                        if ident.get("value") and ident["value"].startswith("MO"):
                            issues.append("Resource is not pseudonym (contains MO identifier)")
                            metrics["is_pseudonym"] = False
                            break

                if issues:
                    await self.save_invalid(run_id, "MedicationRequest", mrid, issues, metrics, db)

            url = next((link["url"] for link in bundle.get("link", []) if link.get("relation") == "next"), None)

# ====================== MEDICATIONADMINISTRATION ======================
class MedicationAdministrationValidator(BaseValidator):
    async def validate_and_save(self, run_id: UUID, db: AsyncSession):
        url = f"{self.base_url}/MedicationAdministration?_count=1000"
        while url:
            bundle = await self.fetch_bundle(url)
            for entry in bundle.get("entry", []):
                ma = entry.get("resource", {})
                maid = ma.get("id", "")
                issues = []
                metrics = {
                    "has_medication": True, "has_patient": True, "has_timestamp": True,
                    "is_correct_effective_period": True, "has_status": True, "is_pseudonym": True
                }

                # Medication Reference
                if not (ma.get("medicationReference") or ma.get("medicationCodeableConcept")):
                    issues.append("medication reference missing")
                    metrics["has_medication"] = False

                # Patient Reference
                if not ma.get("subject") or "Patient" not in str(ma.get("subject")):
                    issues.append("patient reference missing")
                    metrics["has_patient"] = False

                # Status
                if not ma.get("status"):
                    issues.append("status missing")
                    metrics["has_status"] = False

                # Effective DateTime or Period
                if not ma.get("effectiveDateTime") and not ma.get("effectivePeriod"):
                    issues.append("timestamp missing (neither effectiveDateTime nor effectivePeriod)")
                    metrics["has_timestamp"] = False

                # Pseudonym
                if ma.get("identifier"):
                    for ident in ma["identifier"]:
                        if ident.get("value") and ident["value"].startswith("MED"):
                            issues.append("Resource is not pseudonym (contains MED identifier)")
                            metrics["is_pseudonym"] = False
                            break

                if issues:
                    await self.save_invalid(run_id, "MedicationAdministration", maid, issues, metrics, db)

            url = next((link["url"] for link in bundle.get("link", []) if link.get("relation") == "next"), None)


# Registry
VALIDATORS = {
    "Patient": PatientValidator,
    "Encounter": EncounterValidator,
    "Medication": MedicationValidator,
    "MedicationRequest": MedicationRequestValidator,
    "MedicationAdministration": MedicationAdministrationValidator,
}