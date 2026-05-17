# Repo Tool Calls

## 1. read_file

Arguments:
- path: `lisp_parser.py`

Output:

```text
File not found: lisp_parser.py
```

## 2. read_file

Arguments:
- path: `tests/test_lisp_parser.py`

Output:

```text
File not found: tests/test_lisp_parser.py
```

## 3. list_files

Arguments:
- path: `.`
- pattern: `*.py`

Output:

```text
lisp.py
tests/__init__.py
tests/test_lisp.py
```

## 4. grep

Arguments:
- path: `.`
- pattern: `def parse\(`

Output:

```text
No matches found.
```

## 5. grep

Arguments:
- path: `.`
- pattern: `class LispParser`

Output:

```text
No matches found.
```
