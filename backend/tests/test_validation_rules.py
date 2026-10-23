import httpx
import pytest

from app.services.rules.fhir import end_before_start
from app.services.validation_rules import BaseValidator


@pytest.mark.parametrize(
    "start, end, expected",
    [
        # FHIR per-1: start == end is allowed
        ("2020-01-01T10:00:00+01:00", "2020-01-01T10:00:00+01:00", False),
        ("2020-01-01T10:00:00Z", "2020-01-01T09:00:00Z", True),
        # same instant, different time zones
        ("2020-01-01T10:00:00+01:00", "2020-01-01T09:00:00Z", False),
        # date against dateTime is compared per day
        ("2020-01-01", "2020-01-01T08:00:00+02:00", False),
        ("2020-01-02", "2020-01-01T23:00:00Z", True),
        ("2020-01", "2020-01-15", False),
        ("2021", "2020-12-31", True),
        # values without time zone count as UTC
        ("2020-01-01T10:00:00", "2020-01-01T09:00:00+00:00", True),
    ],
)
def test_end_before_start(start, end, expected):
    assert end_before_start(start, end) is expected


def test_end_before_start_rejects_garbage():
    with pytest.raises(ValueError):
        end_before_start("yesterday", "2020-01-01")


@pytest.fixture
def validator():
    return BaseValidator(httpx.AsyncClient(), "https://fhir.example.org/curate/fhir")


def test_next_link_on_same_host(validator):
    link = "https://fhir.example.org/curate/fhir/Patient?_page=2"
    assert validator._pin_to_base(link) == link


def test_relative_next_link(validator):
    assert (
        validator._pin_to_base("/curate/fhir/__page/abc")
        == "https://fhir.example.org/curate/fhir/__page/abc"
    )


def test_next_link_with_internal_host_is_moved_to_base(validator):
    link = "http://blaze:8080/curate/fhir/Patient?_page=2"
    assert (
        validator._pin_to_base(link)
        == "https://fhir.example.org/curate/fhir/Patient?_page=2"
    )


def test_next_link_to_foreign_host_is_refused(validator):
    with pytest.raises(ValueError):
        validator._pin_to_base("https://attacker.example.net/steal")
