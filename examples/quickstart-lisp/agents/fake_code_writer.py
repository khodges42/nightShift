"""Fake code writer for the NightShift end-to-end quickstart."""

from __future__ import annotations

from pathlib import Path
import difflib


FILES = {
    "lisp.py": '''"""Tiny Lisp parser used by the NightShift quickstart."""


def tokenize(source):
    spaced = source.replace("(", " ( ").replace(")", " ) ")
    return spaced.split()


def parse(source):
    tokens = tokenize(source)
    if not tokens:
        raise ValueError("empty expression")
    expression = _parse_tokens(tokens)
    if tokens:
        raise ValueError("unexpected trailing tokens")
    return expression


def _parse_tokens(tokens):
    if not tokens:
        raise ValueError("unexpected end of input")
    token = tokens.pop(0)
    if token == "(":
        values = []
        while tokens and tokens[0] != ")":
            values.append(_parse_tokens(tokens))
        if not tokens:
            raise ValueError("unbalanced parentheses")
        tokens.pop(0)
        return values
    if token == ")":
        raise ValueError("unexpected closing parenthesis")
    return _atom(token)


def _atom(token):
    try:
        return int(token)
    except ValueError:
        return token
''',
    "tests/test_lisp.py": """import unittest

from lisp import parse


class ParserTests(unittest.TestCase):
    def test_parses_numbers(self):
        self.assertEqual(parse("42"), 42)

    def test_parses_symbols(self):
        self.assertEqual(parse("answer"), "answer")

    def test_parses_nested_lists(self):
        self.assertEqual(parse("(+ 1 (* 2 3))"), ["+", 1, ["*", 2, 3]])

    def test_rejects_unbalanced_parentheses(self):
        with self.assertRaises(ValueError):
            parse("(+ 1 2")


if __name__ == "__main__":
    unittest.main()
""",
}


def main() -> None:
    chunks: list[str] = []
    for relative_path, desired in FILES.items():
        path = Path(relative_path)
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        chunks.append(f"diff --git a/{relative_path} b/{relative_path}\n")
        chunks.extend(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                desired.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            )
        )
    print("".join(chunks), end="")


if __name__ == "__main__":
    main()
