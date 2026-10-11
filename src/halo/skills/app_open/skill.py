"""app.open: launch an app.

Allowlisted apps open straight away. Any other app opens only when the
executor has set `ctx.approved` after the user said yes; nothing in `args`
can set it. The name of an approved app is validated and launched as an
argument list, never through a shell.
"""

import asyncio
import re
import shutil
import subprocess
import sys

from halo.config import AppEntry, load_config
from halo.core.contracts import RiskLevel, RunContext
from halo.core.events import make_event
from halo.skills.errors import SkillArgsError


def _normalize(name: str) -> str:
    return " ".join(name.casefold().split())


# Plain app names only: no path separators, quotes, operators or leading dashes.
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}")

_WINDOWS_COMMON = {"notepad": "notepad", "calculator": "calc", "paint": "mspaint"}


def _app_name(args: dict) -> str:
    app = args.get("app")
    if not isinstance(app, str) or not app.strip():
        raise SkillArgsError("app.open needs a non-empty 'app' string")
    return app.strip()


def _find_app(name: str) -> tuple[str, AppEntry] | None:
    wanted = _normalize(name)
    for key, entry in load_config().apps.items():
        if wanted == _normalize(key) or wanted in map(_normalize, entry.aliases):
            return key, entry
    return None


def assess_risk(args: dict) -> RiskLevel:
    """Allowlisted apps are low risk; anything else needs an approval."""
    return "low" if _find_app(_app_name(args)) else "medium"


def approved_argv(name: str) -> list[str]:
    """The launch command for an approved app that is not on the allowlist.
    `name` must already have passed _SAFE_NAME."""
    if sys.platform == "darwin":
        return ["open", "-a", name]
    if sys.platform == "win32":
        return [_WINDOWS_COMMON.get(_normalize(name), name)]
    return [name]


async def _spawn(argv: list[str]) -> None:
    """Start a detached process. Raises FileNotFoundError if the program is
    not installed."""
    exe = shutil.which(argv[0])
    if exe is None:
        raise FileNotFoundError(argv[0])
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        kwargs["start_new_session"] = True
    await asyncio.to_thread(
        subprocess.Popen,
        [exe, *argv[1:]],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


async def run(ctx: RunContext, args: dict) -> dict:
    name = _app_name(args)
    found = _find_app(name)
    approved = getattr(ctx, "approved", False) is True  # set by the executor only
    if found is None and not approved:
        return {"opened": False, "app": name, "needs_approval": True}
    if found is None and not _SAFE_NAME.fullmatch(name):
        return {
            "opened": False,
            "app": name[:64],
            "error": "that doesn't look like an app name I can open safely",
        }

    key = found[0] if found else name
    ctx.emit(
        make_event(ctx.run_id, "tool.called", f"Opening {key}", payload={"app": key})
    )

    argv = found[1].command.get(sys.platform) if found else approved_argv(name)
    if argv is None:
        result = {
            "opened": False,
            "app": key,
            "error": f"no launch command for platform {sys.platform}",
        }
    else:
        try:
            await _spawn(argv)
            result = {"opened": True, "app": key}
        except FileNotFoundError:
            result = {
                "opened": False,
                "app": key,
                "error": f"I couldn't find an app called {key} on this computer",
            }
        except OSError as exc:
            result = {"opened": False, "app": key, "error": f"could not launch: {exc}"}

    title = f"Opened {key}" if result["opened"] else f"Could not open {key}"
    ctx.emit(make_event(ctx.run_id, "tool.result", title, payload=result))
    return result
