"""
Generates the rule tables in documentation/validierungsregeln.md from the
registry. Run after changing rules:

    python -m app.services.rules.docs
"""

from pathlib import Path

from app.services.fix_templates import has_template
from app.services.rules import REGISTRY, RESOURCE_TYPES

DOC = Path(__file__).resolve().parents[4] / "documentation" / "validierungsregeln.md"
START = "<!-- rules:start -->"
END = "<!-- rules:end -->"


def _anchor(text: str) -> str:
    return text.lower().replace(" ", "-")


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _table(header: list[str], align: list[str], rows: list[list[str]]) -> list[str]:
    """Markdown table with padded columns; align per column: 'l' or 'c'."""
    widths = [max(len(str(c)) for c in col) for col in zip(header, *rows)]
    widths = [max(w, 3) for w in widths]

    def line(cells: list[str]) -> str:
        padded = [
            str(c).center(w) if a == "c" else str(c).ljust(w)
            for c, w, a in zip(cells, widths, align)
        ]
        return "| " + " | ".join(padded) + " |"

    rule = [(":" + "-" * (w - 2) + ":") if a == "c" else "-" * w for w, a in zip(widths, align)]
    return [line(header), "| " + " | ".join(rule) + " |"] + [line(r) for r in rows]


def render() -> str:
    lines = ["## Übersicht der Ressourcentypen", ""]
    lines += _table(
        ["Ressourcentyp", "Profil", "Regeln", "Standard an"],
        ["l", "l", "c", "c"],
        [
            [
                f"[{rt}](#{_anchor(rt)})",
                REGISTRY.profiles.get(rt, ""),
                str(len(REGISTRY.for_type(rt))),
                str(sum(r.enabled for r in REGISTRY.for_type(rt))),
            ]
            for rt in RESOURCE_TYPES
        ],
    )
    total = sum(len(REGISTRY.for_type(rt)) for rt in RESOURCE_TYPES)
    lines += ["", f"Insgesamt {total} Regeln.", ""]

    for rt in RESOURCE_TYPES:
        lines += [f"## {rt}", "", f"Profil: {REGISTRY.profiles.get(rt, '')}", ""]
        rows = []
        for r in REGISTRY.for_type(rt):
            pattern = f" Muster: `{r.pattern}`." if r.pattern else ""
            rows.append(
                [
                    f"`{r.key}`",
                    r.category,
                    r.severity,
                    "an" if r.enabled else "aus",
                    "ja" if has_template(rt, r.key) else "–",
                    _cell(r.description) + _cell(pattern),
                ]
            )
        lines += _table(
            ["Regel", "Kategorie", "Schwere", "Std.", "Fix", "Prüft"],
            ["l", "l", "l", "c", "c", "l"],
            rows,
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def updated_document(current: str) -> str:
    head, rest = current.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n\n{render()}\n{END}{tail}"


def main() -> None:
    DOC.write_text(updated_document(DOC.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    print(f"Updated {DOC}")


if __name__ == "__main__":
    main()
