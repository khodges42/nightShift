"""Project-specific exceptions."""


class NightShiftError(Exception):
    """Base exception for NightShift failures."""


class ConfigError(NightShiftError):
    """Raised when a NightShift config is missing or invalid."""


class InitError(NightShiftError):
    """Raised when project initialization cannot proceed."""


class SafetyError(NightShiftError):
    """Raised when a path or command violates configured safety rules."""


class TaskError(NightShiftError):
    """Raised when task parsing or selection fails."""


class ArtifactError(NightShiftError):
    """Raised when artifact storage cannot proceed safely."""


class CommandError(NightShiftError):
    """Raised when command stage execution cannot proceed."""
