import asyncio
import sys

from src.tools import browser_setup
from src.tools.browser_setup import ensure_chromium, is_missing_browser_error


class _FakeProc:
    def __init__(self, returncode=0, output=b"", hang=False):
        self.returncode = returncode
        self._output = output
        self._hang = hang
        self.killed = False

    async def communicate(self):
        if self._hang:
            await asyncio.sleep(3600)
        return self._output, None

    def kill(self):
        self.killed = True


def _spawn(proc, recorder=None):
    async def _fake(*args, **kwargs):
        if recorder is not None:
            recorder.append(args)
        return proc

    return _fake


def test_recognises_both_playwright_phrasings_and_nothing_else():
    assert is_missing_browser_error(Exception("Executable doesn't exist at /ms-playwright/..."))
    assert is_missing_browser_error(Exception("please run: playwright install"))
    # An unrelated launch failure must propagate rather than trigger a 150 MB download.
    assert not is_missing_browser_error(Exception("Target page, context or browser has been closed"))


async def test_hosted_never_installs_and_says_it_is_a_deployment_problem(monkeypatch):
    """The Docker image ships Chromium, so a miss in hosted mode means the image is wrong.
    Downloading inside the pod would hide that behind a slow, repeating per-request failure."""
    calls = []
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", _spawn(_FakeProc(), calls)
    )

    failure = await ensure_chromium(hosted=True)

    assert failure is not None
    assert "deployment problem" in failure
    assert calls == []


async def test_stdio_installs_via_this_interpreter_and_reports_success(monkeypatch):
    """`uv run` does not guarantee the `playwright` console script is on PATH, so the install
    must go through the running interpreter rather than a bare executable name."""
    calls = []
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", _spawn(_FakeProc(returncode=0), calls)
    )

    assert await ensure_chromium(hosted=False) is None
    assert calls == [(sys.executable, "-m", "playwright", "install", "chromium")]


async def test_failed_install_surfaces_the_real_output(monkeypatch):
    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        _spawn(_FakeProc(returncode=1, output=b"ERROR: no space left on device")),
    )

    failure = await ensure_chromium(hosted=False)

    assert failure is not None
    assert "no space left on device" in failure
    assert "exit 1" in failure


async def test_a_hanging_download_is_killed_rather_than_blocking_forever(monkeypatch):
    proc = _FakeProc(hang=True)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spawn(proc))
    monkeypatch.setattr(browser_setup, "_INSTALL_TIMEOUT_SECONDS", 0.01)

    failure = await ensure_chromium(hosted=False)

    assert failure is not None
    assert "did not finish" in failure
    assert proc.killed


async def test_a_failure_to_spawn_at_all_is_reported_not_raised(monkeypatch):
    async def _boom(*args, **kwargs):
        raise FileNotFoundError("no such interpreter")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _boom)

    failure = await ensure_chromium(hosted=False)

    assert failure is not None
    assert "no such interpreter" in failure
