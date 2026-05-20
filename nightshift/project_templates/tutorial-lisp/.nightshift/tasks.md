# Tasks

- [ ] TASK-001: REPL foundation

Description:
Create the initial Lisp REPL application. Implement the command-line entry point, read-eval-print loop, basic input handling, graceful exit commands, and tests. Keep source code under `src/`, tests under `tests/`.

Acceptance Criteria:
- Provides a CLI entry point for starting the REPL
- Reads user input in a loop
- Prints evaluation results
- Supports exit commands like `exit`, `quit`, or Ctrl-D
- Handles blank input without crashing
- Includes basic REPL loop tests

- [ ] TASK-002: Tokenizer and parser

Dependencies:
- TASK-001

Description:
Implement tokenization and parsing for Lisp expressions. Convert source text into tokens, then parse tokens into an AST representation for atoms, numbers, symbols, and nested lists.

Acceptance Criteria:
- Tokenizes parentheses, symbols, numbers, and strings
- Parses simple atoms
- Parses nested S-expressions
- Reports helpful syntax errors for unbalanced parentheses
- Includes tokenizer and parser tests

- [ ] TASK-003: Evaluator and environment

Dependencies:
- TASK-002

Description:
Implement the evaluator and runtime environment. Support symbol lookup, literal values, basic arithmetic, variable definitions, and nested expression evaluation.

Acceptance Criteria:
- Evaluates numeric literals and symbols
- Supports `+`, `-`, `*`, and `/`
- Supports nested arithmetic expressions
- Implements an environment for symbol bindings
- Supports `define`
- Includes evaluator and environment tests

- [ ] TASK-004: Special forms and functions

Dependencies:
- TASK-003

Description:
Add core Lisp special forms and user-defined functions. Implement `quote`, `if`, `lambda`, and function application with lexical scoping.

Acceptance Criteria:
- Supports quoted expressions
- Supports conditional evaluation with `if`
- Supports anonymous functions with `lambda`
- Supports calling user-defined functions
- Preserves lexical scope through closures
- Includes special form and function tests

- [ ] TASK-005: REPL usability and error handling

Dependencies:
- TASK-004

Description:
Improve the REPL user experience. Add multiline input for incomplete expressions, readable error messages, command history if supported by the platform, and a small standard library of helper functions.

Acceptance Criteria:
- Supports multiline input for unfinished expressions
- Displays readable parse and evaluation errors
- Does not crash on invalid user input
- Provides a small standard library such as `list`, `car`, `cdr`, `cons`, and comparison operators
- Includes REPL behavior and error handling tests