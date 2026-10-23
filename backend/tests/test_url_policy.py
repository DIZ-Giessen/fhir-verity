import pytest

from app.services import url_policy
from app.services.url_policy import check_outbound_url, same_origin


@pytest.fixture
def allow(monkeypatch):
    def _set(value: str) -> None:
        monkeypatch.setattr(url_policy.settings, "FHIR_ALLOWED_HOSTS", value)

    _set("")
    return _set


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://[fe80::1]/fhir",
        "http://0.0.0.0/fhir",
        "ftp://fhir.example.org/fhir",
        "file:///etc/passwd",
    ],
)
def test_refuses_dangerous_urls(allow, url):
    with pytest.raises(ValueError):
        check_outbound_url(url)


def test_any_host_without_allowlist(allow):
    check_outbound_url("https://fhir.example.org/fhir")


def test_allowlist_with_wildcard(allow):
    allow("fhir.example.org, *.diz.example.org")
    check_outbound_url("https://fhir.example.org/fhir")
    check_outbound_url("https://blaze.diz.example.org/fhir")
    with pytest.raises(ValueError):
        check_outbound_url("https://intranet.example.org/admin")


def test_same_origin_uses_default_ports():
    assert same_origin("https://a.example.org/fhir", "https://A.example.org:443/x")
    assert not same_origin("https://a.example.org/fhir", "http://a.example.org/fhir")
    assert not same_origin("https://a.example.org/fhir", "https://b.example.org/fhir")
