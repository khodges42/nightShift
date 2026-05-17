# Tasks

- [ ] TASK-001: Parse Lisp expressions

Description:
Implement tokenization and parsing for a tiny Lisp subset.

Acceptance Criteria:
- Parses numbers
- Parses symbols
- Parses nested lists
- Raises useful errors for unbalanced parentheses
- Includes unit tests

- [ ] TASK-002: Evaluate arithmetic forms

Dependencies:
- TASK-001

Description:
Evaluate parsed arithmetic expressions.

Acceptance Criteria:
- Supports `+`, `-`, `*`, and `/`
- Evaluates nested arithmetic
- Includes unit tests

- [ ] TASK-003: Add variables and definitions

Dependencies:
- TASK-002

Description:
Add an environment and support variable lookup and definitions.

Acceptance Criteria:
- Supports symbol lookup
- Supports `(define name value)`
- Keeps environment behavior tested

- [ ] TASK-004: Add conditionals

Dependencies:
- TASK-003

Description:
Implement simple truthiness and `if` expressions.

Acceptance Criteria:
- Supports `(if condition then else)`
- Handles false-like values consistently
- Includes tests for both branches