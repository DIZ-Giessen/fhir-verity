import uuid

from app.core.security import can_manage_server, has_role, visible_servers_clause
from app.models.fhir_server import FhirServer
from app.models.user import User


def _user(role: str) -> User:
    return User(id=uuid.uuid4(), keycloak_sub=str(uuid.uuid4()), role=role)


def test_role_order():
    assert has_role(_user("editor"), "viewer")
    assert not has_role(_user("viewer"), "editor")
    assert has_role(_user("admin"), "editor")


def test_admins_see_every_server():
    assert visible_servers_clause(_user("admin")) is None
    assert visible_servers_clause(_user("viewer")) is not None


def test_manage_requires_editor_owner_or_admin():
    owner = _user("editor")
    server = FhirServer(id=uuid.uuid4(), owner_id=owner.id)
    assert can_manage_server(server, owner)
    assert can_manage_server(server, _user("admin"))
    assert not can_manage_server(server, _user("editor"))


def test_viewer_owner_cannot_manage():
    owner = _user("viewer")
    server = FhirServer(id=uuid.uuid4(), owner_id=owner.id)
    assert not can_manage_server(server, owner)
