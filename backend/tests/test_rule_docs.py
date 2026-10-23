from app.services.rules.docs import DOC, updated_document


def test_rule_docs_are_current():
    current = DOC.read_text(encoding="utf-8")
    assert current == updated_document(current), (
        "documentation/validierungsregeln.md is outdated; "
        "run: cd backend && python -m app.services.rules.docs"
    )
