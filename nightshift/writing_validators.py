"""Writing-workflow validators.

These checks are intentionally kept out of the generic patch generator so code
generation can continue to treat file blocks as ordinary project files.
"""

from __future__ import annotations

from pathlib import Path
import re

from .errors import PipelineError
from .patches import FileUpdate


def validate_writing_file_updates(updates: tuple[FileUpdate, ...], project_root: Path) -> None:
    """Validate writing-specific invariants for novel scene/state file updates."""

    root = Path(project_root)
    characters_path = root / "story" / "characters.md"
    character_sections = (
        _pronoun_reference_sections(characters_path.read_text(encoding="utf-8", errors="replace"))
        if characters_path.is_file()
        else {}
    )
    for update in updates:
        normalized_path = update.path.replace("\\", "/").strip().strip("/")
        if normalized_path == "story/characters.md":
            _validate_protected_character_canon(normalized_path, character_sections, update.content)
        if normalized_path.startswith("story/chapters/") and normalized_path.endswith(".md"):
            _validate_scene_pronoun_canon(normalized_path, update.content, character_sections)


def _validate_protected_character_canon(
    path_text: str,
    old_sections: dict[str, str],
    new_text: str,
) -> None:
    if path_text != "story/characters.md" or not old_sections:
        return
    new_sections = _pronoun_reference_sections(new_text)
    changed = [
        character
        for character, old_section in old_sections.items()
        if new_sections.get(character) != old_section
    ]
    if changed:
        names = ", ".join(changed)
        raise PipelineError(
            "File writer error: protected character pronoun canon changed in "
            f"`story/characters.md` for: {names}."
        )


def _validate_scene_pronoun_canon(
    path_text: str,
    scene_text: str,
    sections: dict[str, str],
) -> None:
    if not sections:
        return
    rules = _pronoun_rules_from_sections(sections)
    if not rules:
        return
    aliases = {alias: character for character in rules for alias in _character_aliases(character)}
    active_character: str | None = None
    for sentence in _scene_sentences(scene_text):
        present = {
            character
            for alias, character in aliases.items()
            if re.search(rf"\b{re.escape(alias)}\b", sentence)
        }
        if len(present) > 1:
            active_character = None
            continue
        character = next(iter(present)) if present else active_character
        if character is None:
            continue
        forbidden = rules[character]
        if present:
            bad = _first_forbidden_pronoun(sentence, forbidden)
            active_character = character
        else:
            bad = _leading_forbidden_pronoun(sentence, forbidden)
            if not bad:
                active_character = None
        if bad:
            excerpt = sentence.strip()
            if len(excerpt) > 160:
                excerpt = excerpt[:157].rstrip() + "..."
            raise PipelineError(
                "File writer error: scene pronoun canon violation for "
                f"{character}: found `{bad}` near character reference. Excerpt: {excerpt}"
            )


def _first_forbidden_pronoun(sentence: str, forbidden: tuple[str, ...]) -> str | None:
    return next(
        (
            pronoun
            for pronoun in forbidden
            if re.search(rf"\b{re.escape(pronoun)}\b", sentence, flags=re.IGNORECASE)
        ),
        None,
    )


def _leading_forbidden_pronoun(sentence: str, forbidden: tuple[str, ...]) -> str | None:
    stripped = sentence.strip()
    return next(
        (
            pronoun
            for pronoun in forbidden
            if re.match(rf"^{re.escape(pronoun)}\b", stripped, flags=re.IGNORECASE)
        ),
        None,
    )


def _pronoun_rules_from_sections(sections: dict[str, str]) -> dict[str, tuple[str, ...]]:
    rules: dict[str, tuple[str, ...]] = {}
    for character, section in sections.items():
        match = re.search(r"(?im)^-\s*Pronouns:\s*(?P<pronouns>.+?)\s*$", section)
        if not match:
            continue
        pronouns = match.group("pronouns").lower()
        forbidden: set[str] = set()
        if "she/her" not in pronouns:
            forbidden.update({"she", "her", "hers", "herself"})
        if "he/him" not in pronouns:
            forbidden.update({"he", "him", "his", "himself"})
        if "they/them" not in pronouns:
            forbidden.update({"they", "them", "their", "theirs", "themselves"})
        if forbidden:
            rules[character] = tuple(sorted(forbidden))
    return rules


def _character_aliases(character: str) -> tuple[str, ...]:
    base = re.sub(r"\s*\([^)]*\)", "", character).strip()
    aliases = {base}
    if base.startswith("DJ "):
        aliases.add(base[3:].strip())
    if " aka " in base:
        aliases.update(part.strip() for part in base.split(" aka ") if part.strip())
    return tuple(alias for alias in aliases if alias)


def _scene_sentences(text: str) -> tuple[str, ...]:
    return tuple(part for part in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if part.strip())


def _pronoun_reference_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_character: str | None = None
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("## "):
            current_character = line[3:].strip()
            index += 1
            continue
        if current_character and line.strip() == "### Pronouns / Reference":
            start = index
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate.startswith("## ") or candidate.startswith("### "):
                    break
                index += 1
            sections[current_character] = "\n".join(lines[start:index]).strip()
            continue
        index += 1
    return sections
