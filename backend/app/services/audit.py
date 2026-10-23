"""Audit entries for changes to Verity itself (servers, sharing, roles)."""

from datetime import datetime, timezone
from typing import Any

from app.models.audit_log import AuditAction, AuditLog, AuditStatus
from app.models.fhir_server import FhirServer
from app.models.user import User


def server_audit_entry(
    action: AuditAction,
    actor: User,
    server: FhirServer,
    *,
    target_type: str = "Server",
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    keep_server_link: bool = True,
) -> AuditLog:
    """
    Build an audit row about a server. keep_server_link=False is for rows
    written while the server is being deleted.
    """
    return AuditLog(
        server_id=server.id if keep_server_link else None,
        server_base_url=server.base_url,
        resource_type=target_type,
        resource_id=target_id or server.name,
        action=action,
        fhir_request_payload=payload,
        resource_before=before,
        status=AuditStatus.SUCCESS,
        actor_id=actor.id,
        executed_at=datetime.now(timezone.utc),
    )


def role_change_entry(actor: User, target: User, old_role: str, new_role: str) -> AuditLog:
    return AuditLog(
        server_id=None,
        server_base_url=None,
        resource_type="User",
        resource_id=target.username or target.email or str(target.id),
        action=AuditAction.USER_ROLE_CHANGE,
        fhir_request_payload={
            "user_id": str(target.id),
            "from": old_role,
            "to": new_role,
        },
        status=AuditStatus.SUCCESS,
        actor_id=actor.id,
        executed_at=datetime.now(timezone.utc),
    )
