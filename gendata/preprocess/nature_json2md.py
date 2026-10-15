#!/usr/bin/env python3
"""Build Nature Communications paper Markdown from article JSON plus the references in the PDF.

Each <id>.json must provide `title` and `section_set`: {"section_1": {"title", "type", "content"}, ...}, where
`type` is "section" or "subsection". The body comes from the JSON sections; the References section is extracted
from <id>.pdf with PyMuPDF. Output: <output>/<id>.md.
"""

import argparse
import json
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Sections to skip (not part of the main paper body)
# ---------------------------------------------------------------------------
SKIP_SECTION_TITLES = {
    "change history",
    "this article is cited by",
}

SKIP_TITLE_PREFIXES = [
    "supplementary movie",
    "supplementary data",
    "supplementary file",
    "supplementry data",  # typo seen in data
    "description of additional supplementary",
]

# ---------------------------------------------------------------------------
# Reference extraction from the PDF text
# ---------------------------------------------------------------------------
REF_START_PATTERNS = [
    re.compile(r"(?im)^\s*references\s*$"),
    re.compile(r"(?im)^\s*reference\s*$"),
    re.compile(r"(?im)^\s*references\s*[\.:]?\s*$"),
    re.compile(r"(?im)\breferences\b\s*(?:[\.:]|\n)"),
]

STOP_HEADINGS = [
    r"Acknowledg(e)?ments",
    r"Author\s+contributions?",
    r"Competing\s+interests?",
    r"Additional\s+information",
    r"Supplementary\s+information",
    r"Publisher[''\u2019]s\s+note",
    r"Peer\s+review\s+information",
    r"Data\s+availability",
    r"Code\s+availability",
    r"Reporting\s+summary",
    r"Ethics\s+declarations?",
]

STOP_REGEX = re.compile(r"(?im)^\s*(?:%s)\s*$" % "|".join(STOP_HEADINGS))


def _normalize_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() + "\n"


def _find_references_start(page_text: str):
    m = re.search(r"(?im)^\s*references\s*$", page_text)
    if m:
        return m.end()
    for pat in REF_START_PATTERNS[1:]:
        m = pat.search(page_text)
        if m:
            return m.end()
    return None


def extract_references(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    start_page = None
    start_offset = None

    for i in range(doc.page_count):
        txt = doc.load_page(i).get_text("text") or ""
        off = _find_references_start(txt)
        if off is not None:
            start_page = i
            start_offset = off
            break

    if start_page is None:
        return ""

    parts = []
    for i in range(start_page, doc.page_count):
        txt = doc.load_page(i).get_text("text") or ""
        if i == start_page and start_offset is not None:
            txt = txt[start_offset:]
        parts.append(txt)

    refs = _normalize_text("\n".join(parts))
    m = STOP_REGEX.search(refs)
    if m:
        refs = refs[: m.start()].rstrip() + "\n"
    refs = _normalize_text(refs)
    return refs


# ---------------------------------------------------------------------------
# Section filtering
# ---------------------------------------------------------------------------
def should_skip_section(title: str) -> bool:
    t = title.strip().lower()
    if t in SKIP_SECTION_TITLES:
        return True
    for prefix in SKIP_TITLE_PREFIXES:
        if t.startswith(prefix):
            return True
    return False


# ---------------------------------------------------------------------------
# Markdown builder
# ---------------------------------------------------------------------------
def build_markdown(data: dict, references: str) -> str:
    lines: list[str] = []

    title = data.get("title", "Untitled")
    lines.append(f"# {title}\n")

    section_set = data.get("section_set", {})
    # section_set keys are like section_1, section_2, ...
    # Sort by numeric suffix to preserve order.
    sorted_keys = sorted(
        section_set.keys(),
        key=lambda k: int(re.search(r"(\d+)$", k).group(1)) if re.search(r"(\d+)$", k) else 0,
    )

    skipping_parent = False
    for key in sorted_keys:
        sec = section_set[key]
        sec_title = sec.get("title", "")
        sec_type = sec.get("type", "section")
        content = sec.get("content", "")

        if sec_type == "section":
            skipping_parent = should_skip_section(sec_title)
        if skipping_parent and sec_type == "subsection":
            continue
        if should_skip_section(sec_title):
            continue

        heading = "##" if sec_type == "section" else "###"
        lines.append(f"{heading} {sec_title}\n")
        if content.strip():
            lines.append(content.strip() + "\n")

    if references.strip():
        lines.append("## References\n")
        lines.append(references.strip() + "\n")

    return "\n".join(lines)


def process_paper(stem, json_dir, pdf_dir, md_dir):
    """Return an error message, or an empty string on success."""
    md_path = Path(md_dir) / f"{stem}.md"
    if md_path.exists():
        return ""
    try:
        data = json.loads((Path(json_dir) / f"{stem}.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return f"[JSON ERROR] {stem}: {exc}"
    try:
        refs = extract_references(str(Path(pdf_dir) / f"{stem}.pdf"))
    except Exception as exc:
        refs = ""
        logging.warning("Reference extraction failed for %s: %s", stem, exc)
    md_path.write_text(build_markdown(data, refs), encoding="utf-8")
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json-dir", required=True, help="Article JSON files")
    parser.add_argument("--pdf-dir", required=True, help="Article PDFs")
    parser.add_argument("-o", "--output", required=True, help="Folder for Markdown files")
    parser.add_argument("--limit", type=int, help="Convert the first N papers")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    Path(args.output).mkdir(parents=True, exist_ok=True)
    stems = sorted(p.stem for p in Path(args.pdf_dir).glob("*.pdf") if (Path(args.json_dir) / f"{p.stem}.json").exists())
    stems = stems[:args.limit]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        errors = [e for e in pool.map(process_paper, stems, *[[d] * len(stems) for d in
                                                               (args.json_dir, args.pdf_dir, args.output)]) if e]
    logging.info("Converted %d papers, %d errors", len(stems) - len(errors), len(errors))
    for error in errors[:20]:
        logging.warning("  %s", error)


if __name__ == "__main__":
    main()
