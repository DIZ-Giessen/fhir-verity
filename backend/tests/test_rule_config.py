from app.services.rules import default_rules, effective_rules


def test_defaults_come_from_the_registry():
    rules = default_rules("Patient")
    assert rules["name_forbidden"]["enabled"] is True
    assert rules["pseudonym_format_check"]["pattern"] == "^20[0-9]{7}$"
    assert "pattern" not in rules["name_forbidden"]


def test_override_changes_only_configurable_fields():
    rules = effective_rules(
        "Patient",
        {
            "name_forbidden": {
                "enabled": False,
                "severity": "warning",
                "description": "stale text from an old override",
                "category": "completeness",
            },
            "pseudonym_format_check": {"pattern": "^99[0-9]+$"},
        },
    )
    assert rules["name_forbidden"]["enabled"] is False
    assert rules["name_forbidden"]["severity"] == "warning"
    assert rules["name_forbidden"]["description"] == default_rules("Patient")["name_forbidden"]["description"]
    assert rules["name_forbidden"]["category"] == "privacy"
    assert rules["pseudonym_format_check"]["pattern"] == "^99[0-9]+$"
    assert rules["pseudonym_format_check"]["enabled"] is True


def test_override_ignores_unknown_rules():
    rules = effective_rules("Patient", {"removed_rule": {"enabled": True}, "x": None})
    assert "removed_rule" not in rules
    assert set(rules) == set(default_rules("Patient"))


def test_new_rules_appear_without_database_changes():
    rules = effective_rules("Encounter", {"status_required": {"enabled": False}})
    assert rules["kontaktebene_required"]["enabled"] is False
    assert rules["status_required"]["enabled"] is False
