"""app.open: launch an allowlisted app.

Only apps in the config allowlist are ever launched here. Nothing in `args` can
widen that: approval for other apps is the executor's job, not this skill's.
"""

import asyncio
import shutil
import subprocess
import sys

from halo.config import AppEntry, load_config
from halo.core.contracts import RiskLevel, RunContext
from halo.core.events import make_event
from halo.skills.errors import SkillArgsError


def _normalize(name: str) -> str:
    return " ".join(name.casefold().split())


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
    if found is None:
        return {"opened": False, "app": name, "needs_approval": True}

    key, entry = found
    ctx.emit(
        make_event(ctx.run_id, "tool.called", f"Opening {key}", payload={"app": key})
    )

    argv = entry.command.get(sys.platform)
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
        except OSError as exc:
            result = {"opened": False, "app": key, "error": f"could not launch: {exc}"}

    title = f"Opened {key}" if result["opened"] else f"Could not open {key}"
    ctx.emit(make_event(ctx.run_id, "tool.result", title, payload=result))
    return result
