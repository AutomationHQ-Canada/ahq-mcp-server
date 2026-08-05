"""`testbots-login` — sign in once, store a long-lived API token.

Why this exists rather than putting a password in .env like the hosted connector does: the
connector never stores the password (`sign_in`'s docstring says so — it lives for the duration of
one HTTP call). Stdio has no browser and no session, so "authenticate with a password" there
would mean keeping the password on disk permanently, to be replayed on every server start. That
is strictly worse than a token, which is revocable, scoped, and cannot change the account's own
password or open the web UI.

So this keeps the interactive part and drops the storage: prompt for the password, exchange it
for a sign-in JWT, use that JWT once to mint an ORGANIZATION token, write only the token. The
password is never written anywhere and is not held after the first call.
"""
import asyncio
import getpass
import os
import sys
from pathlib import Path

import httpx

from src.clients.user_client import UserClient
from src.config.ahq_services import settings
from src.config.credentials import AhqCredentials
from src.hosted.consent import _normalize_projects, sign_in

CREDENTIALS_HOME = Path.home() / ".testbots"
ENV_PATH = CREDENTIALS_HOME / ".env"

_NEEDS_TERMINAL = (
    "testbots-login needs an interactive terminal for the password prompt.\n"
    # Plain ASCII: the Windows console codepage mangles an em dash into a replacement char.
    "Run it in a terminal window, not through a pipe, a CI job, or an AI assistant\n"
    "session, none of which can prompt for a password without capturing it."
)


def _write_env(token: str, project_id: str, base_url: str) -> None:
    """Write the three settings, preserving any unrelated lines already in the file."""
    managed = {"TESTBOTS_API_TOKEN": token, "TESTBOTS_PROJECT_ID": project_id}
    # Only pin the gateway when the token cannot name it itself. Writing it unconditionally is
    # how an .env ends up pointing at the wrong environment after the token is later replaced.
    if base_url and base_url != settings.ahq_base_url:
        managed["TESTBOTS_BASE_URL"] = base_url

    existing = []
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip().upper()
            # Drop the AHQ_* spellings too, or the old value survives alongside the new one and
            # which wins depends on precedence rather than on anything the user chose.
            if key in managed or key.replace("TESTBOTS_", "AHQ_", 1) in {
                    k.replace("TESTBOTS_", "AHQ_", 1) for k in managed}:
                continue
            existing.append(line)

    CREDENTIALS_HOME.mkdir(parents=True, exist_ok=True)
    body = "\n".join(existing + [f"{k}={v}" for k, v in managed.items()]).strip() + "\n"
    ENV_PATH.write_text(body, encoding="utf-8")
    try:
        os.chmod(ENV_PATH, 0o600)  # best effort; a no-op on Windows
    except OSError:
        pass


def _choose(projects: list) -> dict:
    if len(projects) == 1:
        print(f"\nProject: {projects[0]['name']}")
        return projects[0]
    print("\nChoose a project:")
    for i, p in enumerate(projects, 1):
        print(f"  {i}. {p['name']}")
    while True:
        raw = input(f"\nNumber [1-{len(projects)}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(projects):
            return projects[int(raw) - 1]
        print("Not one of the options.")


async def _run(base_url: str, force: bool) -> int:
    if ENV_PATH.exists() and "TESTBOTS_API_TOKEN=" in ENV_PATH.read_text(encoding="utf-8") \
            and not force:
        # Minting is limited per organization and this endpoint does not revoke what it replaces,
        # so a login that silently re-mints burns a finite quota on every run.
        print(f"{ENV_PATH} already holds a token. Re-run with --force to mint another.")
        return 1

    # Only catches the redirected-stdin case, and only where isatty is trustworthy — Windows
    # reports NUL as a character device, so this is False there even with no console at all.
    # The EOFError below is what actually fires on Windows.
    if not sys.stdin.isatty():
        print(_NEEDS_TERMINAL)
        return 1

    # The gateway host is an implementation detail and currently still carries the old brand,
    # so show the product name instead. An explicit --base-url is different: someone overriding
    # the environment needs to see which one they actually got, or a prod/dev mix-up is silent.
    if base_url == settings.ahq_base_url:
        print("Signing in to TestBots.ai\n")
    else:
        print(f"Signing in to {base_url}\n")
    try:
        email = input("Email: ").strip()
        # No usable console means getpass reads the console device and blocks rather than
        # falling back to a visible prompt. Refusing beats hanging, and both beat echoing the
        # password into whatever is capturing output — a CI log, or an assistant transcript.
        password = getpass.getpass("Password: ")
    except EOFError:
        print(f"\n{_NEEDS_TERMINAL}")
        return 1
    if not email or not password:
        print("Email and password are both required.")
        return 1

    async with httpx.AsyncClient() as http:
        jwt = await sign_in(http, base_url, email, password)
        if not jwt:
            print("\nUnable to log in. Your login details are incorrect, or your account has "
                  "been disabled.")
            return 1

        def client(org_id: str = "") -> UserClient:
            return UserClient(
                credentials=AhqCredentials(base_url=base_url, api_token=jwt, org_id=org_id,
                                           project_id="", auth_scheme="bearer"),
                http_client=http,
            )

        # registration_info, not /users/me: the latter 500s for a password JWT, which carries
        # only `sub`. This is also the only lookup that works before an organization is known.
        me = await client().registration_info(email)
        org_id, user_id = str(me.get("organizationId") or ""), str(me.get("userId") or "")
        if not org_id or not user_id:
            print("\nSigned in, but this account is not attached to an organization.")
            return 1

        # User-scoped first (what this person holds a role in), then org-wide, which is what
        # the consent flow already used. Without the fallback an account with few or no
        # per-project roles dead-ends on an organization full of projects: support@ has one
        # role, on a project whose orgId is null, while its organization holds 54 — so this
        # reported "no projects" where the hosted connector listed them all.
        projects = await client(org_id).list_projects_for_user(user_id)
        if not projects:
            try:
                projects = _normalize_projects(await client(org_id).list_projects())
            except Exception:
                projects = []
        if not projects:
            # Naming the organization matters: both lookups are org-scoped, so an account in a
            # different organization than the user expects reads as a broken login rather than
            # as the wrong org. Minting would not help either -- createOrgToken allows
            # belongsToOrg || isOrgCreator, so this same organization is the only one reachable.
            print(f"\nSigned in, but organization {org_id} has no projects, so there is "
                  f"nothing to connect to.\nIf you expected projects here, check you are in "
                  f"the organization you think you are.")
            return 1
        project = _choose(projects)

        label = f"testbots-mcp-server ({os.environ.get('COMPUTERNAME') or os.uname().nodename})"
        result = await client(org_id).create_org_token(org_id, user_id, base_url, label=label)

    token = result.get("token") or ""
    if not token:
        print(f"\nToken was not issued: {result}")
        return 1

    _write_env(token, project["id"], base_url)
    print(f"\nWrote {ENV_PATH}")
    print(f"  organization {org_id}")
    print(f"  project      {project['name']}")
    if (remaining := result.get("remainingTokens")) is not None:
        print(f"  {remaining} token slot(s) left in this organization")
    print("\nRestart Claude Code, then run /mcp to confirm.")
    return 0


def main() -> int:
    args = sys.argv[1:]
    force = "--force" in args
    base_url = next((a.split("=", 1)[1] for a in args if a.startswith("--base-url=")),
                    settings.ahq_base_url)
    if not base_url:
        print("No gateway URL. Pass --base-url=https://api-dev.automationhq.ai")
        return 1
    try:
        return asyncio.run(_run(base_url, force))
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except Exception as exc:
        print(f"\n{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
