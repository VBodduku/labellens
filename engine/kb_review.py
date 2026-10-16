"""Generate the complete human review inventory from the validated KB."""

from pathlib import Path
from engine.kb_loader import TERMS, Term


def needs_review(term: Term) -> bool:
    return bool(
        term.confidence == "medium"
        or term.possible_categories
        or term.origin == "varies"
        or term.review_reason
    )


def render_review() -> str:
    review = [term for term in TERMS if needs_review(term)]
    lines = [
        "# Knowledge base human review",
        "",
        f"{len(TERMS)} entries; {len(review)} require source, taxonomy or community-practice review below.",
        "",
        "Status: pending human review. Inclusion here is not approval. No real packet corpus was available when this inventory was prepared.",
        "",
        "Every medium-confidence, possible-category, variable-origin or explicitly flagged entry is included. Definite categories describe an ingredient/source signal; they do not measure allergenic protein, concentration or personal diet acceptance.",
        "",
        "## References and scope",
        "",
        "- [UK Food Standards Agency allergen groups](https://www.food.gov.uk/sites/default/files/media/document/14-Allergens%2016Nov21.pdf): standard milk/egg/cereal/nut ingredient identities, not an Indian regulatory authorization list.",
        "- [NCBI albumin family](https://www.ncbi.nlm.nih.gov/mesh?Cmd=DetailsSearch&Db=mesh&Term=%22Albumins%22%5BMeSH+Terms%5D) and [plant 2S albumins](https://www.ncbi.nlm.nih.gov/mesh/68055516): generic albumin does not establish an egg source. Egg albumen/ovalbumin remain definite egg.",
        "- [NHS supplier ingredient specification](https://media.supplychain.nhs.uk/media/documents/AEF130/Specification/87501_AEF130_02.08.2022.pdf): hydrolysed vegetable protein may have wheat, maize or soy source; this supports ambiguity, not the composition of another product.",
        "- Shared catalog/spec conventions are retained for lactitol, maltodextrin, date paste and lactose; their taxonomy limitations need human review. No new INS numbers were added in Phase 3.",
        "- Regional aliases below are common ingredient names, not certified translations. A Hindi/Telugu reader must check spelling, regional meaning and actual packet usage; no corpus frequency claim is made.",
        "",
        "## Entries requiring review",
        "",
        "| ID | Confidence | Definite | Possible | Review question / notes |",
        "| --- | --- | --- | --- | --- |",
    ]

    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    for term in review:
        reason = term.review_reason or term.notes
        lines.append(
            f"| `{term.id}` | {term.confidence} | {', '.join(term.categories) or 'none'} | {', '.join(term.possible_categories) or 'none'} | {cell(reason)} |"
        )
    lines += [
        "",
        "## Native-speaker check: every Hindi/Telugu alias",
        "",
        "All entries below remain pending native-speaker review, including high-confidence ingredient identities.",
        "",
        "| ID | Hindi | Telugu |",
        "| --- | --- | --- |",
    ]
    for term in TERMS:
        if term.names.hi or term.names.te:
            lines.append(
                f"| `{term.id}` | {cell(', '.join(term.names.hi)) or '—'} | {cell(', '.join(term.names.te)) or '—'} |"
            )
    lines += [
        "",
        "Regenerate from the repository root with `python -m engine.kb_review`. After a human review, record the decision in the entry's notes/review_reason and regenerate; do not remove uncertainty just to reduce this list.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    Path(__file__).with_name("KB_REVIEW.md").write_text(
        render_review(), encoding="utf-8"
    )
