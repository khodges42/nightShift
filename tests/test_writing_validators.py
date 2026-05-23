from pathlib import Path
import tempfile
import unittest

from nightshift.errors import PipelineError
from nightshift.patches import FileUpdate
from nightshift.writing_validators import validate_writing_file_updates


class WritingValidatorTests(unittest.TestCase):
    def test_rejects_character_pronoun_canon_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "story").mkdir()
            (root / "story" / "characters.md").write_text(
                """# Characters

## Cricket

### Pronouns / Reference
- Pronouns: she/her
- Narrative reference: Cricket; she/her

Scavenger.
""",
                encoding="utf-8",
            )
            updates = (
                FileUpdate(
                    path="story/characters.md",
                    content="""# Characters

## Cricket

### Pronouns / Reference
- Pronouns: they/them
- Narrative reference: Cricket; they/them

Scavenger.
""",
                ),
            )

            with self.assertRaisesRegex(PipelineError, "protected character pronoun canon changed"):
                validate_writing_file_updates(updates, root)

    def test_rejects_scene_pronoun_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "story" / "chapters").mkdir(parents=True)
            (root / "story" / "characters.md").write_text(
                """# Characters

## Proxy

### Pronouns / Reference
- Pronouns: she/her
- Narrative reference: Proxy; she/her
""",
                encoding="utf-8",
            )
            updates = (
                FileUpdate(
                    path="story/chapters/chapter-001/scene-001.md",
                    content="Proxy checked the rack. He shut down the bad job.\n",
                ),
            )

            with self.assertRaisesRegex(PipelineError, "scene pronoun canon violation for Proxy"):
                validate_writing_file_updates(updates, root)

    def test_allows_scene_pronouns_when_multiple_characters_make_ambiguous_sentence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "story" / "chapters" / "chapter-001").mkdir(parents=True)
            (root / "story" / "characters.md").write_text(
                """# Characters

## Proxy

### Pronouns / Reference
- Pronouns: she/her
- Narrative reference: Proxy; she/her

## Saint

### Pronouns / Reference
- Pronouns: he/him
- Narrative reference: Saint; he/him
""",
                encoding="utf-8",
            )
            updates = (
                FileUpdate(
                    path="story/chapters/chapter-001/scene-001.md",
                    content="Proxy watched Saint as he picked up the phone.\n",
                ),
            )

            validate_writing_file_updates(updates, root)


if __name__ == "__main__":
    unittest.main()
