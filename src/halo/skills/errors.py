"""Errors skills raise for problems the caller can handle."""


class SkillArgsError(ValueError):
    """The arguments given to a skill are missing or invalid (for example a
    model-supplied app name that is blank). The executor reports it as a step
    error; it is never a sign that Halo itself is misconfigured."""
