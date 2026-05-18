"""Terminal styling helpers for NightShift."""

from __future__ import annotations

import os
import sys
from typing import TextIO
import random



RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
GREEN = "\x1b[32m"
RED = "\x1b[31m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
WHITE = "\x1b[37m"

BANNER_MESSAGES = [
    "Real LARPer Hours",
    "Who the heck is claude?",
    "WHO UP BREAKIN THEY BUILD?",
    "me and the boys at 2am lookin for BEANS",
    "local-first autonomous coding pipeline",
    "why break then build while you're awake?",
    "compiling bad ideas into good software",
    "local-first synthetic cognition",
    "the graveyard shift for software engineering",
    "pipeline humming at unsafe levels",
    "generated at 3:14am with malicious intent",
    "all outputs are guilty until proven correct",
    "daemonized software production",
    "running tests until morale improves",
    "you wouldn't download a senior engineer",
    "sleep is temporary. infrastructure is forever.",
]
quote = random.choice(BANNER_MESSAGES)

def should_style(stream: TextIO | None = None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def style_text(text: str, *, color: str | None = None, bold: bool = False, dim: bool = False, stream: TextIO | None = None) -> str:
    if not should_style(stream):
        return text
    parts: list[str] = []
    if bold:
        parts.append(BOLD)
    if dim:
        parts.append(DIM)
    if color:
        parts.append(color)
    if not parts:
        return text
    return "".join(parts) + text + RESET


def format_banner(stream: TextIO | None = None) -> str:
    lines = [
        "███╗   ██╗██╗ ██████╗ ██╗  ██╗████████╗███████╗██╗  ██╗██╗███████╗████████╗",
        "████╗  ██║██║██╔════╝ ██║  ██║╚══██╔══╝██╔════╝██║  ██║██║██╔════╝╚══██╔══╝",
        "██╔██╗ ██║██║██║  ███╗███████║   ██║   ███████╗███████║██║█████╗     ██║   ",
        "██║╚██╗██║██║██║   ██║██╔══██║   ██║   ╚════██║██╔══██║██║██╔══╝     ██║   ",
        "██║ ╚████║██║╚██████╔╝██║  ██║   ██║   ███████║██║  ██║██║██║        ██║   ",
        "╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   ",
        "",
        "      NightShift",
       f"      [ {quote} ]",
        "      [ planner | implementer | verifier | audit ]",
        "",
        "      VERSION: 0.1.0-alpha-glizzy",
        "-" * 50,
        "",
    ]

    if not should_style(stream):
        return "\n".join(lines)
    styled: list[str] = []
    for index, line in enumerate(lines):
        if not line:
            styled.append(line)
            continue
        color = CYAN if index < 8 else WHITE
        bold = index < 8 or line == "NightShift"
        styled.append(style_text(line, color=color, bold=bold, stream=stream))
    return "\n".join(styled)


def format_console_event_line(
    timestamp: str,
    event: str,
    message: str,
    fields: dict[str, object],
    *,
    stream: TextIO | None = None,
) -> str:
    line = format_plain_event_line(timestamp, event, message, fields)
    if not should_style(stream):
        return line
    color = _event_color(event, fields)
    if color is None:
        return line
    return style_text(line, color=color, stream=stream)


def format_plain_event_line(timestamp: str, event: str, message: str, fields: dict[str, object]) -> str:
    parts = [timestamp, event, message]
    for key, value in sorted(fields.items()):
        if value is None or value == "":
            continue
        parts.append(f"{key}={_format_value(value)}")
    return " | ".join(parts)


def _event_color(event: str, fields: dict[str, object]) -> str | None:
    status = str(fields.get("status", "")).lower()
    reason = str(fields.get("reason", "")).lower()
    event_name = event.lower()
    if status in {"fail", "failed", "error"} or "fail" in reason or "error" in reason:
        return RED
    if status in {"complete", "pass", "success", "ok"}:
        return GREEN
    if status in {"retry", "warning", "warn", "blocked"}:
        return YELLOW
    if event_name.endswith(".start"):
        return BLUE
    if event_name.endswith(".finish"):
        return GREEN
    if "tool" in event_name:
        return MAGENTA
    if "command" in event_name:
        return CYAN
    return None


def _format_value(value: object) -> str:
    return str(value).replace("\n", " ").replace("\r", " ")
