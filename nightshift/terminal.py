"""Terminal styling helpers for NightShift."""

from __future__ import annotations

import os
import sys
from typing import TextIO
import random
import threading
import time

from .version import display_version


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
    "why break the build while you're awake?",
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

HOTDOG_ANIMATIONS = {
    "classic_dance": [
        "🌭",
        "ヽ(🌭)ﾉ",
        "(🌭)",
        "(🌭)",
        "(🌭)",
    ],
    "shuffle_mode": [
        " (🌭) ",
        " (🌭) ",
        "<(🌭<)",
        "(>🌭)>",
        "~(🌭)~",
    ],
    "gremlin_energy": [
        "(ﾉ🌭)ﾉ",
        "ᕕ(🌭)ᕗ",
        "^(🌭)^",
        "(🌭)b",
        "(🌭)",
    ],
    "roller_grill": [
        "🌭",
        "🌭",
        "🌭",
        "🌭",
        "🌭",
    ],
    "ascending_glizzy": [
        "🌭",
        " 🌭",
        "  🌭",
        "   ",
        "🌭",
    ],
    "agent_thinking": [
        "🌭 .",
        "🌭 ..",
        "🌭 ...",
        "🌭 ....",
        "🌭 ???",
    ],
    "tubular_offering": [
        " つ 🌭_🌭 つ",
        " つ🌭 _🌭 つ",
        " つ 🌭🌭 つ",
        " つ🌭🌭_ つ",
        " つ 🌭_🌭 つ",
    ],
    "tubular_offering_wobble": [
        " つ 🌭_🌭 つ",
        " つ 🌭~🌭 つ",
        " つ ~🌭~ つ",
        " つ 🌭~🌭 つ",
        " つ 🌭_🌭 つ",
    ],
    "chaotic_summoning": [
        " つ 🌭_🌭 つ",
        " つ 🌭 つ",
        " つ 🌭🔥 つ",
        " つ 🌭 つ",
        " つ 🌭_🌭 つ",
    ],
    "hotdog_ritual_dance": [
        "( ಠ_ಠ)🌭(ಠ_ಠ )",
        "( ಠ_ಠ)🌭(ಠ_ಠ )",
        "( ಠ_ಠ) 🌭 (ಠ_ಠ )",
        "( ಠ_ಠ)  🌭  (ಠ_ಠ )",
        "( ಠ_ಠ)🌭(ಠ_ಠ )",
    ],
    "ritual_side_to_side": [
        "( ಠ_ಠ)🌭(ಠ_ಠ )",
        "( ಠ_ಠ) 🌭(ಠ_ಠ )",
        "( ಠ_ಠ)  🌭(ಠ_ಠ )",
        "( ಠ_ಠ) (ಠ_ಠ )",
        "( ಠ_ಠ)🌭(ಠ_ಠ )",
    ],
    "full_rave_mode": [
        "( ಠ_ಠ)🌭(ಠ_ಠ )",
        "(ಠ_ಠ )🌭( ಠ_ಠ)",
        "( ಠ_ಠ)🌭(ಠ_ಠ )",
        "(ಠ_ಠ )🔥🌭🔥( ಠ_ಠ)",
        "( ಠ_ಠ)🌭(ಠ_ಠ )",
    ],
    "terminal_cult_initiation": [
        "( ಠ_ಠ)     (ಠ_ಠ )",
        "( ಠ_ಠ)🌭    (ಠ_ಠ )",
        "( ಠ_ಠ) 🌭   (ಠ_ಠ )",
        "( ಠ_ಠ)  🌭  (ಠ_ಠ )",
        "( ಠ_ಠ)   🌭 (ಠ_ಠ )",
    ],
}


class TerminalAnimation:
    """Transient terminal status animation."""

    def __init__(
        self,
        name: str = "agent_thinking",
        *,
        message: str = "NightShift running",
        stream: TextIO | None = None,
        interval_seconds: float = 0.18,
        enabled: bool = True,
    ) -> None:
        self.frames = animation_frames(name)
        self.message = message
        self.stream = stream or sys.stderr
        self.interval_seconds = interval_seconds
        self.enabled = enabled and should_style(self.stream)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._width = 0

    def __enter__(self) -> "TerminalAnimation":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=1)
        self._clear()
        self._thread = None

    def _run(self) -> None:
        index = 0
        while not self._stop.is_set():
            frame = self.frames[index % len(self.frames)]
            text = f"{frame} {self.message}"
            self._width = max(self._width, len(text))
            self.stream.write("\r" + text.ljust(self._width))
            self.stream.flush()
            index += 1
            self._stop.wait(self.interval_seconds)

    def _clear(self) -> None:
        if not self.enabled:
            return
        self.stream.write("\r" + (" " * self._width) + "\r")
        self.stream.flush()


def animation_frames(name: str) -> tuple[str, ...]:
    frames = HOTDOG_ANIMATIONS.get(name)
    if not frames:
        frames = HOTDOG_ANIMATIONS["agent_thinking"]
    return tuple(frames)

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
        f"      VERSION: {display_version()}",
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
