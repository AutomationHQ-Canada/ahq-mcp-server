import asyncio
import sys

# Playwright surfaces a missing or version-mismatched browser build through the normal launch
# exception; these are the two phrasings it uses for it.
_MISSING_BROWSER_MARKERS = ("Executable doesn't exist", "playwright install")

# A cold Chromium download is ~150 MB. It happens once per environment, so the ceiling only
# needs to be generous enough for a slow connection, not tight.
_INSTALL_TIMEOUT_SECONDS = 600

# Two concurrent crawls would otherwise both start the same download into the same directory.
_INSTALL_LOCK = asyncio.Lock()


def is_missing_browser_error(exc: BaseException) -> bool:
    text = str(exc)
    return any(marker in text for marker in _MISSING_BROWSER_MARKERS)


async def ensure_chromium(hosted: bool) -> str | None:
    """
    Download the Chromium build the installed playwright package expects. Returns None once the
    browser is present, or an actionable error string if it could not be installed.

    Hosted mode deliberately does NOT install: the Docker image already ships the browser, so a
    miss there means the image is wrong. Downloading 150 MB inside the pod on a caller's request
    would convert that into a slow, repeating, possibly read-only-filesystem failure instead of
    a loud one that gets fixed.

    Invoked as `<this interpreter> -m playwright` rather than a bare `playwright` executable —
    under `uv run` the console script is not necessarily on PATH even though the package imports
    fine, and the interpreter is the only thing guaranteed to be the right environment.
    """
    if hosted:
        return (
            "Playwright's browser binary is missing from this server's image. That is a "
            "deployment problem rather than something a caller can fix — report it instead of "
            "retrying."
        )

    async with _INSTALL_LOCK:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "playwright",
                "install",
                "chromium",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as e:
            return (
                f"Could not start the Chromium download ({e}). Install it manually with "
                f"`uv run playwright install chromium` in the plugin folder, then retry."
            )

        try:
            output, _ = await asyncio.wait_for(proc.communicate(), _INSTALL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            return (
                f"The Chromium download did not finish within {_INSTALL_TIMEOUT_SECONDS} seconds. "
                f"Run `uv run playwright install chromium` in the plugin folder to complete it, "
                f"then retry."
            )

    if proc.returncode != 0:
        tail = (output or b"").decode(errors="replace").strip()[-500:]
        return (
            f"Chromium download failed (exit {proc.returncode}). Run "
            f"`uv run playwright install chromium` in the plugin folder to see the full output "
            f"and retry. Last lines: {tail}"
        )
    return None
