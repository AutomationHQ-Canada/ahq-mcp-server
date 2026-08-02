import html
import time

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import construct_redirect_uri

from src.config.credentials import AhqCredentials, base_url_from_claims, decode_ahq_token
from src.hosted.audit import audit_log
from src.hosted.oauth_provider import CODE_TTL
from src.hosted.token_codec import TokenCodec

# AutomationHQ mark, inlined so the page has no external asset dependency.
_LOGO_DATA_URI = "data:image/png;base64,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"

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect to {partner_name}</title>
<style>
  :root {{
    --ahq-primary: {primary_color};
    --ahq-primary-focus-ring: {primary_color_focus_ring};
    --ahq-danger: #dc2929;
    --ahq-text: #333333;
    --ahq-muted: #6b6b6b;
    --ahq-border: #e0e0e0;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f6f5f8;
    color: var(--ahq-text);
    margin: 0;
    padding: 3rem 1rem;
  }}
  .card {{
    max-width: 26rem;
    margin: 0 auto;
    background: #ffffff;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06);
    padding: 2rem;
  }}
  .logo {{ display: block; height: 40px; margin: 0 auto 1.5rem; }}
  h1 {{ font-size: 1.15rem; font-weight: 600; text-align: center; margin: 0 0 1.5rem; }}
  h1 strong {{ color: var(--ahq-primary); }}
  label {{ display: block; margin: 1rem 0 0.4rem; font-weight: 500; font-size: 0.9rem; }}
  input[type=password], input[type=text] {{
    width: 100%;
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--ahq-border);
    border-radius: 4px;
    font-size: 0.95rem;
    font-family: inherit;
  }}
  input[type=password]:focus, input[type=text]:focus {{
    outline: none;
    border-color: var(--ahq-primary);
    box-shadow: 0 0 0 3px var(--ahq-primary-focus-ring);
  }}
  .radio {{ margin: 0.5rem 0; font-weight: 400; }}
  .radio label {{ display: flex; align-items: center; gap: 0.5rem; font-weight: 400; margin: 0; }}
  button {{
    width: 100%;
    margin-top: 1.5rem;
    padding: 0.65rem 1.5rem;
    font-size: 0.95rem;
    font-weight: 600;
    font-family: inherit;
    color: #ffffff;
    background: var(--ahq-primary);
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }}
  button:hover {{ filter: brightness(0.87); }}
  .error {{ background: #fdecea; border: 1px solid #f5c6cb; color: var(--ahq-danger); padding: 0.6rem 0.75rem; border-radius: 4px; font-size: 0.9rem; }}
  .org {{ background: #f4e9f6; padding: 0.6rem 0.75rem; border-radius: 4px; font-size: 0.9rem; }}
  .hint {{ color: var(--ahq-muted); font-size: 0.8rem; margin-top: 0.4rem; }}
</style></head><body>
<div class="card">
  <img class="logo" src="{logo}" alt="{partner_name}">
  <h1>Connect <strong>{client_name}</strong> to your {partner_name} account</h1>
  {banner}
  <form method="post" action="consent">
    <input type="hidden" name="txn" value="{txn}">
    {token_field}
    {project_field}
    <button type="submit">Authorize</button>
  </form>
</div>
</body></html>"""


def _token_input(partner_name: str) -> str:
    escaped = html.escape(partner_name)
    return (
        f'<label for="ahq_token">{escaped} API token</label>\n'
        '<input type="password" id="ahq_token" name="ahq_token" autocomplete="off" required>\n'
        f'<p class="hint">Create one in the {escaped} web app under Administration '
        "&rarr; API Tokens. Either type works &mdash; note that a User token still has access "
        "to everything in its organization. <strong>Give it the longest expiry you can:</strong> "
        "this connection can never outlive the token sealed inside it, so a short-lived token "
        "means reconnecting and pasting a new one every time it expires.</p>"
    )


# Below this, a connection is short enough that the user will notice the reconnect and deserves to
# hear about it up front rather than discover it. The platform's own token dialog offers an
# 8-hour option, and it is a popular choice — 29% of live ORGANIZATION tokens use it.
_SHORT_TOKEN_LIFE_SECONDS = 7 * 24 * 3600


def _expiry_warning(claims: dict) -> str:
    """Plain-language warning when the pasted token expires soon, or "" when it doesn't.

    _capped_ttl never issues an access OR refresh token past the embedded AHQ token's own expiry
    — it cannot, since every downstream call re-presents that token to the gateway. So the AHQ
    token's lifetime IS the connection's lifetime, and an 8-hour token silently means re-pasting
    a new one before the next working day.
    """
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return ""
    remaining = int(exp - time.time())
    if remaining <= 0 or remaining >= _SHORT_TOKEN_LIFE_SECONDS:
        return ""
    # Rounded, not floored: an 8-hour token is a second or two into its life by the time it is
    # pasted, and "expires in about 7 hours" for a token the user just created reads as a bug.
    if remaining < 2 * 3600:
        window = f"{max(1, round(remaining / 60))} minutes"
    elif remaining < 48 * 3600:
        window = f"{round(remaining / 3600)} hours"
    else:
        window = f"{round(remaining / 86400)} days"
    return (
        f"Heads up: this token expires in about {window}, and this connection expires with it. "
        "To avoid reconnecting then, create a longer-lived token and paste that instead."
    )


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    # Used for the input-focus glow, which needs a translucent version of whatever primary
    # color a deployment configures — not just the AHQ purple this was originally hardcoded to.
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(156, 39, 176, {alpha})"  # fallback: AHQ purple, if a bad value slips through
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return f"rgba(156, 39, 176, {alpha})"
    return f"rgba({r}, {g}, {b}, {alpha})"


def _error_banner(message: str) -> str:
    return f'<p class="error">{html.escape(message)}</p>'


def _render(txn: str, client_name: str, partner_name: str, logo: str, primary_color: str,
            banner: str = "", token_value: str = "", projects: list | None = None,
            status: int = 200) -> Response:
    if projects is not None:
        # Project picker round-trip: the validated token rides along hidden so the user
        # doesn't have to paste it twice (their own browser, their own token, 10-min txn TTL).
        # Names only, no id shown — the id is still what actually travels as the field value.
        token_field = (
            f'<input type="hidden" name="ahq_token" value="{html.escape(token_value, quote=True)}">'
        )
        radios = "\n".join(
            f'<div class="radio"><label><input type="radio" name="project_id" '
            f'value="{html.escape(p["id"], quote=True)}" required> '
            f'{html.escape(p["name"])}</label></div>'
            for p in projects
        )
        project_field = f"<label>Choose a project</label>\n{radios}"
    else:
        # First screen: token only. No manual project-id entry — the project is always chosen
        # from the live picker after the token is validated (auto-selected if there's only one).
        token_field = _token_input(partner_name)
        project_field = ""
    return HTMLResponse(
        _PAGE.format(
            logo=logo,
            partner_name=html.escape(partner_name),
            primary_color=primary_color,
            primary_color_focus_ring=_hex_to_rgba(primary_color, 0.15),
            client_name=html.escape(client_name),
            banner=banner,
            txn=html.escape(txn, quote=True),
            token_field=token_field,
            project_field=project_field,
        ),
        status_code=status,
    )


# Both AHQ token types work here. They differ only in which identity claims they carry
# (ORGANIZATION: organizationName + createdByUserId; USER: userId + email + name) — both carry
# organizationId and urlDetails, which is everything the flow below actually needs.
#
# NOTE: accepting a USER token does NOT scope permissions to that user. The gateway's API-key
# path (SecurityContextRepository.validateApiKey) only checks that the token value exists in the
# `tokens` collection; it never reads tokenType, expiry or revocation, and attaches no user. So a
# USER token today has the same org-wide reach as an ORGANIZATION one. Verified live 2026-07-28.
# Documented in CONNECT.md so nobody reads "user token" as "restricted token".
_ACCEPTED_TOKEN_TYPES = ("ORGANIZATION", "USER")


def _subject_label(claims: dict, org_name: str) -> str:
    """Who the confirmation banner should name.

    For a USER token the person is the meaningful identity and we have it; for an ORGANIZATION
    token there is no user, so the org is the only thing to show.
    """
    if claims.get("tokenType") == "USER":
        who = claims.get("name") or claims.get("email")
        email = claims.get("email")
        if who and email and who != email:
            return f"{who} ({email})"
        if who:
            return str(who)
    return org_name


def _normalize_projects(raw: list) -> list[dict]:
    # The real projects-list documents use `_id` + `projectName`; other id/name field
    # variants are kept for compatibility with other deployments.
    projects = []
    for p in raw if isinstance(raw, list) else []:
        if not isinstance(p, dict):
            continue
        pid = p.get("projectId") or p.get("id") or p.get("_id")
        if pid:
            projects.append({
                "id": str(pid),
                "name": str(p.get("name") or p.get("projectName") or pid),
            })
    return projects


_EXPIRED_HTML = (
    "<h1>This connection link has expired</h1>"
    "<p>Go back to your MCP client and start the connection again.</p>"
)


def make_consent_endpoints(codec: TokenCodec, settings, user_client_factory, http_client_holder):
    """
    Returns (GET, POST) Starlette endpoints for the consent step of the OAuth flow: the page
    where a user pastes an AHQ API token (Organization or User) and picks a project. Both types
    carry the organizationId and urlDetails claims this flow needs; see _ACCEPTED_TOKEN_TYPES for
    what accepting a USER token does and does not buy. user_client_factory
    is the UserClient class (injected for tests); http_client_holder is mcp_server.app_http_client
    (the shared pooled httpx client).
    """
    extra_base_urls = frozenset(
        u.strip() for u in (getattr(settings, "ahq_mcp_extra_base_urls", "") or "").split(",") if u.strip()
    )
    # Per-deployment branding (e.g. a self-hosted client showing their own identity instead of
    # AutomationHQ's) — empty settings fall back to AHQ's own name/logo/color unchanged.
    partner_name = getattr(settings, "ahq_mcp_partner_display_name", "") or "AutomationHQ"
    partner_logo = getattr(settings, "ahq_mcp_partner_logo_url", "") or _LOGO_DATA_URI
    partner_color = getattr(settings, "ahq_mcp_partner_primary_color", "") or "#9c27b0"

    def _render_page(*args, **kwargs) -> Response:
        return _render(*args, partner_name=partner_name, logo=partner_logo,
                       primary_color=partner_color, **kwargs)

    def _load_txn(request: Request, form=None):
        txn = (form.get("txn") if form is not None else request.query_params.get("txn")) or ""
        return txn, codec.decode("txn", txn)

    async def _validate_and_list(token: str, project_id: str = "") -> dict:
        """
        Token-type check plus a live gateway call to list the org's real projects (this also
        confirms project_id, if given, actually belongs to the token's organization). Returns
        {"ok": False, "message": ...} on any failure ("projects"/"org_name" are also included
        for the project_not_in_org case, since that one still needs to show a picker), or
        {"ok": True, "org_id", "org_name", "projects", "base_url"} on success. base_url is
        resolved from the token's own urlDetails claim rather than this server's fixed
        AHQ_BASE_URL, so the same consent page correctly validates tokens from any environment.
        """
        claims = decode_ahq_token(token)
        org_id = claims.get("organizationId", "")
        token_type = claims.get("tokenType", "")
        if not token or not org_id or token_type not in _ACCEPTED_TOKEN_TYPES:
            audit_log("auth.consent_fail", reason="unsupported_token_type",
                      token_type=token_type or "none")
            return {
                "ok": False,
                "message": (
                    f"That doesn't look like a {partner_name} API token. Create one under "
                    "Administration → API Tokens (type: Organization or User) and paste it here."
                ),
            }

        base_url = base_url_from_claims(claims, extra_base_urls) or settings.ahq_base_url
        creds = AhqCredentials(base_url=base_url, api_token=token,
                               org_id=org_id, project_id=project_id)
        try:
            raw = await user_client_factory(
                credentials=creds, http_client=http_client_holder.client
            ).list_projects()
        except Exception:
            audit_log("auth.consent_fail", org=org_id, reason="gateway_rejected_token")
            return {
                "ok": False,
                "message": (
                    f"{partner_name} rejected this token — it may be expired or deleted. "
                    "Check it in Administration → API Tokens and try again."
                ),
            }
        projects = _normalize_projects(raw)
        if not projects:
            # Otherwise this renders "Choose a project" with no options and a `required` radio —
            # an unsubmittable form with no stated reason, which reads as "this token doesn't
            # work" while a colleague's token on a different org sails through. Confirmed
            # reachable: an organization holding a valid ORGANIZATION token and zero projects
            # exists in the live dev data.
            audit_log("auth.consent_fail", org=org_id, reason="no_projects_in_org")
            return {
                "ok": False,
                "message": (
                    "This token is valid, but its organization has no projects yet — there is "
                    f"nothing to connect to. Create a project in the {partner_name} web app "
                    "first, or use a token from an organization that already has one."
                ),
            }
        # ORGANIZATION tokens carry organizationName; USER tokens do not (TokenService's
        # generateOrgClaims vs createClaims). Without a fallback a user token would show its raw
        # org UUID on the confirmation banner.
        org_name = claims.get("organizationName") or org_id

        if project_id and project_id not in {p["id"] for p in projects}:
            audit_log("auth.consent_fail", org=org_id, reason="project_not_in_org")
            return {
                "ok": False,
                "projects": projects,
                "org_name": org_name,
                "subject": _subject_label(claims, org_name),
                "message": (
                    f"Project '{project_id}' does not belong to organization "
                    f"'{org_name}'. Pick one of its projects below."
                ),
            }
        return {"ok": True, "org_id": org_id, "org_name": org_name,
                "subject": _subject_label(claims, org_name), "token_type": token_type,
                "projects": projects, "base_url": base_url,
                "expiry_warning": _expiry_warning(claims)}

    def _issue_code(payload: dict, token: str, project_id: str, base_url: str) -> str:
        params = payload["params"]
        return codec.encode(
            "code",
            {
                "ahq_token": token,
                "project_id": project_id,
                "base_url": base_url,
                "client_id": payload["client_id"],
                "redirect_uri": params["redirect_uri"],
                "redirect_uri_provided_explicitly": params["redirect_uri_provided_explicitly"],
                "code_challenge": params["code_challenge"],
                "scopes": params.get("scopes") or [],
            },
            CODE_TTL,
        )

    def _redirect_url(payload: dict, code: str) -> str:
        params = payload["params"]
        return construct_redirect_uri(params["redirect_uri"], code=code, state=params.get("state"))

    async def consent_get(request: Request) -> Response:
        txn, payload = _load_txn(request)
        if payload is None:
            return HTMLResponse(_EXPIRED_HTML, status_code=400)
        return _render_page(txn, payload["client_name"])

    async def consent_post(request: Request) -> Response:
        form = await request.form()
        txn, payload = _load_txn(request, form)
        if payload is None:
            return HTMLResponse(_EXPIRED_HTML, status_code=400)
        client_name = payload["client_name"]
        token = str(form.get("ahq_token") or "").strip()
        project_id = str(form.get("project_id") or "").strip()

        result = await _validate_and_list(token, project_id)
        if not result["ok"]:
            return _render_page(
                txn, client_name, token_value=token, projects=result.get("projects"),
                status=400, banner=_error_banner(result["message"]),
            )
        projects = result["projects"]

        warning = result.get("expiry_warning") or ""
        if not project_id:
            if len(projects) == 1:
                project_id = projects[0]["id"]
            else:
                who = "" if result.get("token_type") == "USER" else "organization "
                extra = f" {html.escape(warning)}" if warning else ""
                return _render_page(
                    txn, client_name, token_value=token, projects=projects,
                    banner=f'<p class="org">Token accepted for {who}'
                           f"<strong>{html.escape(result['subject'])}</strong>.{extra}</p>",
                )

        code = _issue_code(payload, token, project_id, result["base_url"])
        # Logged even on the redirect path, where there is no page left to warn on: a support
        # question of the form "it keeps asking me to reconnect" is answerable from this line.
        audit_log("auth.consent_ok", org=result["org_id"], project=project_id,
                  token_type=result.get("token_type", ""),
                  short_lived_token=bool(warning))
        return RedirectResponse(
            _redirect_url(payload, code), status_code=302, headers={"Cache-Control": "no-store"},
        )

    return consent_get, consent_post
