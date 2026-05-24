#!/usr/bin/env python3
"""
Compile a NightShift-style story folder into:
- story/build/manuscript.md
- story/build/manuscript.html
- story/build/manuscript.pdf

Expected layout:

root/
  story/
    TITLE.md              optional
    metadata.json         optional
    cover.png             optional, currently only copied/referenced
    chapters/
      chapter-000/
        scene-001.md
      chapter-001/
        scene-001.md
        scene-002.md
  .nightshift/
    tasks.md

Install:
  pip install markdown reportlab

Example:
  python compile_story.py --root .
  python compile_story.py --root . --chapter-format word
  python compile_story.py --root . --toc off
  python compile_story.py --root . --pdf-style manuscript
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# ----------------------------
# Models
# ----------------------------

@dataclass
class Metadata:
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    language: str | None = None


@dataclass
class BuildOptions:
    root: Path
    chapter_format: str
    toc: str
    pdf_style: str
    scene_headings: bool
    output_name: str


# ----------------------------
# Natural sorting
# ----------------------------

def natural_key(path: Path) -> list[object]:
    """
    Sorts scene-003a.md after scene-003.md and before scene-004.md.
    """
    text = path.name.lower()
    parts = re.split(r"(\d+)", text)
    return [int(p) if p.isdigit() else p for p in parts]


def chapter_number(chapter_dir: Path) -> int | None:
    match = re.search(r"chapter-(\d+)", chapter_dir.name, re.I)
    if not match:
        return None
    return int(match.group(1))


# ----------------------------
# Metadata / title / acts
# ----------------------------

def load_metadata(story_dir: Path) -> Metadata:
    metadata_path = story_dir / "metadata.json"
    if not metadata_path.exists():
        return Metadata()

    data = json.loads(metadata_path.read_text(encoding="utf-8"))

    return Metadata(
        title=data.get("title"),
        subtitle=data.get("subtitle"),
        author=data.get("author"),
        language=data.get("language"),
    )


def read_title_page(story_dir: Path) -> str:
    title_path = story_dir / "TITLE.md"
    if not title_path.exists():
        return ""
    return title_path.read_text(encoding="utf-8").strip()


def parse_act_headings(tasks_path: Path) -> list[str]:
    """
    Reads only headings like:

      # ACT 1 - LOW HEAT
      # ACT 2 - WHATEVER

    Ignores task entries, descriptions, acceptance criteria, etc.
    """
    if not tasks_path.exists():
        return []

    acts: list[str] = []

    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        match = re.match(r"^#\s+(ACT\s+\d+\s+-\s+.+)$", line, re.I)
        if match:
            acts.append(match.group(1).strip())

    return acts


# ----------------------------
# Chapter / scene rendering
# ----------------------------

def format_chapter_heading(chapter_dir: Path, fmt: str) -> str | None:
    num = chapter_number(chapter_dir)

    if num == 0:
        return None

    if fmt == "none":
        return None

    if fmt == "folder":
        return chapter_dir.name

    if fmt == "number":
        if num is None:
            return chapter_dir.name
        return f"{num:03d}"

    if fmt == "word":
        if num is None:
            return chapter_dir.name
        return f"Chapter {num}"

    if fmt == "chapter-dash":
        if num is None:
            return chapter_dir.name
        return f"Chapter-{num:03d}"

    raise ValueError(f"Unknown chapter format: {fmt}")


def first_heading(markdown_text: str) -> str | None:
    for line in markdown_text.splitlines():
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return None


def strip_top_heading(markdown_text: str) -> str:
    """
    Removes the first top-level heading only.
    Useful if scene headings are being generated separately.
    """
    lines = markdown_text.splitlines()
    output: list[str] = []
    removed = False

    for line in lines:
        if not removed and re.match(r"^#\s+.+$", line.strip()):
            removed = True
            continue
        output.append(line)

    return "\n".join(output).strip()


def build_scene_markdown(scene_path: Path, include_scene_heading: bool) -> str:
    raw = scene_path.read_text(encoding="utf-8").strip()

    if not include_scene_heading:
        return raw

    heading = first_heading(raw)

    if heading:
        body = strip_top_heading(raw)
        return f"### {heading}\n\n{body}".strip()

    fallback = scene_path.stem.replace("-", " ").title()
    return f"### {fallback}\n\n{raw}".strip()


def chapter_dirs(chapters_dir: Path) -> list[Path]:
    dirs = [p for p in chapters_dir.iterdir() if p.is_dir() and p.name.lower().startswith("chapter-")]
    return sorted(dirs, key=natural_key)


def scene_files(chapter_dir: Path) -> list[Path]:
    files = [p for p in chapter_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md"]
    return sorted(files, key=natural_key)


# ----------------------------
# TOC
# ----------------------------

def make_toc(chapter_map: list[tuple[Path, list[Path]]], opts: BuildOptions) -> str:
    if opts.toc == "off":
        return ""

    lines = ["# Contents", ""]

    for chapter_dir, scenes in chapter_map:
        ch_num = chapter_number(chapter_dir)

        if ch_num == 0:
            label = "Front Matter"
        else:
            label = format_chapter_heading(chapter_dir, opts.chapter_format) or chapter_dir.name

        if opts.toc == "acts":
            # Act-only TOC is handled elsewhere poorly without explicit mapping.
            # For now, treat as compact chapter-only.
            lines.append(f"- {label}")

        elif opts.toc == "chapters":
            lines.append(f"- {label}")

        elif opts.toc == "full":
            lines.append(f"- {label}")
            for scene in scenes:
                raw = scene.read_text(encoding="utf-8")
                heading = first_heading(raw) or scene.stem
                lines.append(f"  - {heading}")

        else:
            raise ValueError(f"Unknown TOC style: {opts.toc}")

    return "\n".join(lines).strip()


# ----------------------------
# Markdown assembly
# ----------------------------

def assemble_markdown(opts: BuildOptions) -> str:
    story_dir = opts.root / "story"
    chapters_dir = story_dir / "chapters"
    tasks_path = opts.root / ".nightshift" / "tasks.md"

    if not story_dir.exists():
        raise FileNotFoundError(f"Missing story directory: {story_dir}")

    if not chapters_dir.exists():
        raise FileNotFoundError(f"Missing chapters directory: {chapters_dir}")

    metadata = load_metadata(story_dir)
    title_page = read_title_page(story_dir)
    acts = parse_act_headings(tasks_path)

    all_chapters = chapter_dirs(chapters_dir)
    chapter_map = [(chapter, scene_files(chapter)) for chapter in all_chapters]

    parts: list[str] = []

    # Optional cover reference for markdown/html.
    cover_path = story_dir / "cover.png"
    if cover_path.exists():
        parts.append("![Cover](cover.png)")
        parts.append(r"\newpage")

    # TITLE.md wins over metadata title page.
    if title_page:
        parts.append(title_page)
        parts.append(r"\newpage")
    elif metadata.title or metadata.author:
        title_bits = []
        if metadata.title:
            title_bits.append(f"# {metadata.title}")
        if metadata.subtitle:
            title_bits.append(f"## {metadata.subtitle}")
        if metadata.author:
            title_bits.append(f"### {metadata.author}")
        parts.append("\n\n".join(title_bits))
        parts.append(r"\newpage")

    toc_md = make_toc(chapter_map, opts)
    if toc_md:
        parts.append(toc_md)
        parts.append(r"\newpage")

    act_index = 0

    for chapter_dir, scenes in chapter_map:
        ch_num = chapter_number(chapter_dir)

        # chapter-000 is front matter, no act divider, no chapter numbering.
        is_front_matter = ch_num == 0

        # Insert act divider before chapter-001, chapter-002, chapter-003, etc.
        # This assumes ACT 1 maps to chapter-001, ACT 2 maps to chapter-002, etc.
        if not is_front_matter and ch_num is not None:
            expected_act_number = ch_num
            if expected_act_number - 1 < len(acts):
                act_heading = acts[expected_act_number - 1]
                parts.append(f"# {act_heading}")
                parts.append(r"\newpage")

        chapter_heading = None if is_front_matter else format_chapter_heading(chapter_dir, opts.chapter_format)

        if chapter_heading:
            parts.append(f"# {chapter_heading}")
            parts.append("")

        for scene in scenes:
            scene_md = build_scene_markdown(scene, opts.scene_headings)
            if scene_md:
                parts.append(scene_md)
                parts.append("")

        parts.append(r"\newpage")

    return "\n\n".join(p for p in parts if p is not None).strip() + "\n"


# ----------------------------
# HTML
# ----------------------------

def markdown_to_html(md: str, metadata: Metadata) -> str:
    try:
        import markdown
    except ImportError as exc:
        raise RuntimeError("Missing dependency: pip install markdown") from exc

    body = markdown.markdown(
        md,
        extensions=[
            "extra",
            "toc",
            "sane_lists",
        ],
    )

    title = metadata.title or "Manuscript"

    return f"""<!doctype html>
<html lang="{html.escape(metadata.language or "en")}">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{
      max-width: 720px;
      margin: 3rem auto;
      padding: 0 1.5rem;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 18px;
      line-height: 1.65;
      color: #111;
    }}

    h1, h2, h3 {{
      font-weight: normal;
      text-align: center;
      margin-top: 3rem;
    }}

    h1 {{
      font-size: 2.1rem;
      page-break-before: always;
    }}

    h2 {{
      font-size: 1.5rem;
    }}

    h3 {{
      font-size: 1.2rem;
      margin-top: 2rem;
    }}

    p {{
      text-indent: 1.5em;
      margin: 0 0 0.4rem 0;
    }}

    h1 + p,
    h2 + p,
    h3 + p {{
      text-indent: 0;
    }}

    ul, ol {{
      margin-left: 2rem;
    }}

    img {{
      max-width: 100%;
      display: block;
      margin: 2rem auto;
    }}

    code {{
      font-family: Consolas, monospace;
      font-size: 0.9em;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


# ----------------------------
# PDF via ReportLab
# ----------------------------

def write_pdf(md: str, output_path: Path, metadata: Metadata, pdf_style: str) -> None:
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A5, LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        PageBreak,
        Image,
    )

    story_dir = output_path.parent.parent
    cover_path = story_dir / "cover.png"

    if pdf_style == "paperback":
        pagesize = A5
        margins = {
            "leftMargin": 0.65 * inch,
            "rightMargin": 0.65 * inch,
            "topMargin": 0.7 * inch,
            "bottomMargin": 0.7 * inch,
        }
        body_size = 10.5
        leading = 15

    elif pdf_style == "manuscript":
        pagesize = LETTER
        margins = {
            "leftMargin": 1 * inch,
            "rightMargin": 1 * inch,
            "topMargin": 1 * inch,
            "bottomMargin": 1 * inch,
        }
        body_size = 12
        leading = 24

    else:
        raise ValueError(f"Unknown PDF style: {pdf_style}")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=pagesize,
        title=metadata.title or "Manuscript",
        author=metadata.author or "",
        **margins,
    )

    styles = getSampleStyleSheet()

    body = ParagraphStyle(
        "NovelBody",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=body_size,
        leading=leading,
        firstLineIndent=18,
        spaceAfter=4,
        alignment=TA_LEFT,
    )

    h1 = ParagraphStyle(
        "NovelH1",
        parent=styles["Heading1"],
        fontName="Times-Roman",
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        spaceBefore=36,
        spaceAfter=24,
    )

    h2 = ParagraphStyle(
        "NovelH2",
        parent=styles["Heading2"],
        fontName="Times-Roman",
        fontSize=15,
        leading=20,
        alignment=TA_CENTER,
        spaceBefore=28,
        spaceAfter=18,
    )

    h3 = ParagraphStyle(
        "NovelH3",
        parent=styles["Heading3"],
        fontName="Times-Roman",
        fontSize=13,
        leading=18,
        alignment=TA_CENTER,
        spaceBefore=20,
        spaceAfter=14,
    )

    story = []

    if cover_path.exists():
        printable_w = pagesize[0] - margins["leftMargin"] - margins["rightMargin"] - 8
        printable_h = pagesize[1] - margins["topMargin"] - margins["bottomMargin"] - 8

        img = Image(str(cover_path))
        scale = min(
            printable_w / img.imageWidth,
            printable_h / img.imageHeight,
            1.0,
        )

        img.drawWidth = img.imageWidth * scale
        img.drawHeight = img.imageHeight * scale

        story.append(img)
        story.append(PageBreak())

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 9)
        canvas.drawCentredString(pagesize[0] / 2, 0.35 * inch, str(doc.page))
        canvas.restoreState()

    def flush_paragraph(buffer):
        text = " ".join(x.strip() for x in buffer).strip()
        if text:
            story.append(Paragraph(html.escape(text), body))
        return []

    buffer = []

    for line in md.splitlines():
        stripped = line.strip()

        if stripped.startswith("!["):
            buffer = flush_paragraph(buffer)
            continue

        if stripped == r"\newpage":
            buffer = flush_paragraph(buffer)
            story.append(PageBreak())
            continue

        if not stripped:
            buffer = flush_paragraph(buffer)
            story.append(Spacer(1, 6))
            continue

        if stripped.startswith("# "):
            buffer = flush_paragraph(buffer)
            story.append(Paragraph(html.escape(stripped[2:].strip()), h1))
            continue

        if stripped.startswith("## "):
            buffer = flush_paragraph(buffer)
            story.append(Paragraph(html.escape(stripped[3:].strip()), h2))
            continue

        if stripped.startswith("### "):
            buffer = flush_paragraph(buffer)
            story.append(Paragraph(html.escape(stripped[4:].strip()), h3))
            continue

        if re.match(r"^[-*]\s+", stripped):
            buffer = flush_paragraph(buffer)
            item = re.sub(r"^[-*]\s+", "• ", stripped)
            story.append(Paragraph(html.escape(item), body))
            continue

        buffer.append(stripped)

    buffer = flush_paragraph(buffer)

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )


# ----------------------------
# Build
# ----------------------------

def build(opts: BuildOptions) -> None:
    story_dir = opts.root / "story"
    build_dir = story_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    metadata = load_metadata(story_dir)
    md = assemble_markdown(opts)

    md_path = build_dir / f"{opts.output_name}.md"
    html_path = build_dir / f"{opts.output_name}.html"
    pdf_path = build_dir / f"{opts.output_name}.pdf"

    md_path.write_text(md, encoding="utf-8")

    html_doc = markdown_to_html(md, metadata)
    html_path.write_text(html_doc, encoding="utf-8")

    write_pdf(md, pdf_path, metadata, opts.pdf_style)

    cover = story_dir / "cover.png"
    if cover.exists():
        shutil.copy2(cover, build_dir / "cover.png")

    print("Built:")
    print(f"  {md_path}")
    print(f"  {html_path}")
    print(f"  {pdf_path}")


# ----------------------------
# CLI
# ----------------------------

def parse_args() -> BuildOptions:
    parser = argparse.ArgumentParser(description="Compile story markdown into a novel build.")

    parser.add_argument("--root", default=".", help="Project root containing story/ and .nightshift/")
    parser.add_argument(
        "--chapter-format",
        default="folder",
        choices=["folder", "number", "word", "chapter-dash", "none"],
        help="How numbered chapters should be titled.",
    )
    parser.add_argument(
        "--toc",
        default="full",
        choices=["off", "chapters", "full", "acts"],
        help="Table of contents style. Default: full.",
    )
    parser.add_argument(
        "--pdf-style",
        default="paperback",
        choices=["paperback", "manuscript"],
        help="PDF formatting style.",
    )
    parser.add_argument(
        "--no-scene-headings",
        action="store_true",
        help="Do not generate scene headings from scene markdown.",
    )
    parser.add_argument(
        "--output-name",
        default="manuscript",
        help="Base output filename.",
    )

    args = parser.parse_args()

    return BuildOptions(
        root=Path(args.root).resolve(),
        chapter_format=args.chapter_format,
        toc=args.toc,
        pdf_style=args.pdf_style,
        scene_headings=not args.no_scene_headings,
        output_name=args.output_name,
    )


def main() -> None:
    opts = parse_args()
    build(opts)


if __name__ == "__main__":
    main()