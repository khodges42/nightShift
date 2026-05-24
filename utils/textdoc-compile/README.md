# Textdoc Compiler

# NightShift Story Compiler

Compile structured markdown fiction projects into novel-style builds.

Generates:

* paperback-style PDF
* assembled markdown manuscript
* HTML preview
* optional cover support
* front matter
* act divider pages
* table of contents

Designed for AI-assisted longform fiction pipelines.

---

# Features

* Pure Python
* Windows-friendly
* Natural scene sorting:

  * `scene-003.md`
  * `scene-003a.md`
  * `scene-003b.md`
* Front matter support via `chapter-000`
* Act dividers parsed from `.nightshift/tasks.md`
* Multiple chapter naming styles
* Optional metadata/title pages
* Paperback or manuscript formatting
* Scene heading extraction
* TOC generation
* Clean build output folder

---

# Example Project Structure

```text
project-root/
│
├── compile_story.py
│
├── .nightshift/
│   └── tasks.md
│
└── story/
    ├── TITLE.md
    ├── metadata.json
    ├── cover.png
    │
    ├── chapters/
    │   ├── chapter-000/
    │   │   ├── scene-001.md
    │   │   └── scene-002.md
    │   │
    │   ├── chapter-001/
    │   │   ├── scene-001.md
    │   │   ├── scene-002.md
    │   │   └── scene-003a.md
    │   │
    │   ├── chapter-002/
    │   └── chapter-003/
    │
    └── build/
```

---

# Install

```powershell
pip install markdown reportlab
```

---

# Quick Start

```powershell
python compile.py --root .
```

Outputs:

```text
story/build/
  manuscript.md
  manuscript.html
  manuscript.pdf
```

---

# Title Pages

## TITLE.md

If present:

```text
story/TITLE.md
```

Its contents are inserted as the title page.

Example:

```md
# NightShift

## A Novel

KHodges42
```

---

## metadata.json

Optional metadata fallback if `TITLE.md` is missing.

Example:

```json
{
  "title": "NightShift",
  "subtitle": "A Novel",
  "author": "KHodges42",
  "language": "en"
}
```

---

# Cover Support

Optional:

```text
story/cover.png
```

Currently:

* included in markdown/html
* copied into build folder
* ignored in ReportLab PDF for now

Future versions can embed directly into PDF.

---

# Front Matter

`chapter-000` is treated specially.

Example:

```text
story/chapters/chapter-000/
```

Use for:

* foreword
* acknowledgements
* author notes
* epigraphs
* dedication

No chapter numbering is applied.

---

# Act Dividers

Acts are parsed from:

```text
.nightshift/tasks.md
```

Example:

```md
# ACT 1 - LOW HEAT
# ACT 2 - STATIC BODIES
# ACT 3 - RECURSIVE CONTAMINATION
```

Each act becomes a standalone divider page.

Only the ACT headings are parsed.

Everything else in `tasks.md` is ignored.

---

# Chapter Naming

Default:

```powershell
--chapter-format folder
```

Results in:

```text
chapter-001
chapter-002
```

Other options:

```powershell
--chapter-format number
```

```text
001
002
```

```powershell
--chapter-format word
```

```text
Chapter 1
Chapter 2
```

```powershell
--chapter-format chapter-dash
```

```text
Chapter-001
Chapter-002
```

```powershell
--chapter-format none
```

No chapter headings.

---

# Table of Contents

Default:

```powershell
--toc full
```

Options:

## Full

```powershell
--toc full
```

Chapters + scenes.

## Chapters Only

```powershell
--toc chapters
```

## Compact Acts

```powershell
--toc acts
```

## Disable

```powershell
--toc off
```

---

# PDF Styles

## Paperback (default)

```powershell
--pdf-style paperback
```

* compact trim size
* tighter margins
* novel-like formatting

## Manuscript

```powershell
--pdf-style manuscript
```

* wider margins
* larger spacing
* draft/review friendly

---

# Scene Headings

By default:

* first `# Heading` in each scene file becomes scene title
* heading is normalized into manuscript structure

Disable:

```powershell
--no-scene-headings
```

---

# Example Commands

## Default Build

```powershell
python compile_story.py --root .
```

## Paperback Build

```powershell
python compile_story.py --root . --pdf-style paperback
```

## Manuscript Draft

```powershell
python compile_story.py --root . --pdf-style manuscript
```

## No TOC

```powershell
python compile_story.py --root . --toc off
```

## Word Chapter Format

```powershell
python compile_story.py --root . --chapter-format word
```

---

# Notes

## Natural Sorting

Scene files are sorted naturally.

Example:

```text
scene-001.md
scene-002.md
scene-003.md
scene-003a.md
scene-003b.md
scene-004.md
```

---

## EPUB

Not currently implemented.

Can be added later using:

* ebooklib
* pandoc
* markdown-it-py pipelines

---

# Planned Features

* EPUB export
* embedded cover art in PDF
* page numbers
* running headers
* chapter drop caps
* better typography
* custom fonts
* widow/orphan control
* scene separators
* theme presets
* print-ready trim sizes
* LaTeX backend
* AI-generated glossary/index support



---

# License

GPL3v2
