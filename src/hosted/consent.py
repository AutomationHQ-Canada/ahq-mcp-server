import html

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import construct_redirect_uri

from src.config.credentials import AhqCredentials, decode_ahq_token
from src.hosted.audit import audit_log
from src.hosted.oauth_provider import CODE_TTL
from src.hosted.token_codec import TokenCodec

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect to AutomationHQ</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 30rem; margin: 4rem auto; padding: 0 1rem; color: #1a1a2e; }}
  h1 {{ font-size: 1.25rem; }}
  label {{ display: block; margin: 1rem 0 0.25rem; font-weight: 600; }}
  input[type=password], input[type=text] {{ width: 100%; padding: 0.5rem; box-sizing: border-box; }}
  .radio {{ margin: 0.35rem 0; font-weight: 400; }}
  button {{ margin-top: 1.25rem; padding: 0.5rem 1.5rem; font-size: 1rem; cursor: pointer; }}
  .error {{ background: #fdecea; border: 1px solid #f5c6cb; padding: 0.6rem; border-radius: 4px; }}
  .org {{ background: #eaf4fd; padding: 0.6rem; border-radius: 4px; }}
  .hint {{ color: #555; font-size: 0.85rem; }}
</style></head><body>
<h1>Connect {client_name} to AutomationHQ</h1>
{banner}
<form method="post" action="consent">
  <input type="hidden" name="txn" value="{txn}">
  {token_field}
  {project_field}
  <button type="submit">Authorize</button>
</form>
</body></html>"""

_TOKEN_INPUT = """<label for="ahq_token">AutomationHQ Organization API token</label>
<input type="password" id="ahq_token" name="ahq_token" autocomplete="off" required>
<p class="hint">Create one in the AutomationHQ web app under Administration &rarr; API Tokens (type: Organization).</p>"""


def _error_banner(message: str) -> str:
    return f'<p class="error">{html.escape(message)}</p>'


def _render(txn: str, client_name: str, banner: str = "", token_value: str = "",
            projects: list | None = None, status: int = 200) -> Response:
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
        token_field = _TOKEN_INPUT
        project_field = ""
    return HTMLResponse(
        _PAGE.format(
            client_name=html.escape(client_name),
            banner=banner,
            txn=html.escape(txn, quote=True),
            token_field=token_field,
            project_field=project_field,
        ),
        status_code=status,
    )


def _normalize_projects(raw: list) -> list[dict]:
    # The real /projects/organizations/{orgId}/all documents use `_id` + `projectName`
    # (confirmed live 2026-07-14) — projectId/id/name variants kept for other deployments.
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


def make_consent_endpoints(codec: TokenCodec, settings, user_client_factory, http_client_holder):
    """
    Returns (GET, POST) Starlette endpoints for the token-paste consent page — the human step
    of the OAuth flow. user_client_factory is the UserClient class (injected for tests);
    http_client_holder is mcp_server.app_http_client (shared pooled httpx client).
    """

    def _load_txn(request: Request, form=None):
        txn = (form.get("txn") if form is not None else request.query_params.get("txn")) or ""
        return txn, codec.decode("txn", txn)

    async def consent_get(request: Request) -> Response:
        txn, payload = _load_txn(request)
        if payload is None:
            return HTMLResponse(
                "<h1>This connection link has expired</h1><p>Go back to your MCP client and start the connection again.</p>",
                status_code=400,
            )
        return _render(txn, payload["client_name"])

    async def consent_post(request: Request) -> Response:
        form = await request.form()
        txn, payload = _load_txn(request, form)
        if payload is None:
            return HTMLResponse(
                "<h1>This connection link has expired</h1><p>Go back to your MCP client and start the connection again.</p>",
                status_code=400,
            )
        client_name = payload["client_name"]
        token = str(form.get("ahq_token") or "").strip()
        project_id = str(form.get("project_id") or "").strip()

        claims = decode_ahq_token(token)
        org_id = claims.get("organizationId", "")
        if not token or not org_id or claims.get("tokenType") != "ORGANIZATION":
            audit_log("auth.consent_fail", reason="not_an_organization_token")
            return _render(
                txn, client_name, status=400,
                banner=_error_banner(
                    "That doesn't look like an AutomationHQ ORGANIZATION API token. Create one "
                    "under Administration → API Tokens (type: Organization) and paste it here."
                ),
            )

        # Live validation against the real gateway — the same call is the Slice 9k
        # project↔org consistency check (the returned list IS the org's project set).
        creds = AhqCredentials(base_url=settings.ahq_base_url, api_token=token,
                               org_id=org_id, project_id=project_id)
        try:
            raw = await user_client_factory(
                credentials=creds, http_client=http_client_holder.client
            ).list_projects()
        except Exception:
            audit_log("auth.consent_fail", org=org_id, reason="gateway_rejected_token")
            return _render(
                txn, client_name, status=400,
                banner=_error_banner(
                    "AutomationHQ rejected this token — it may be expired or deleted. "
                    "Check it in Administration → API Tokens and try again."
                ),
            )
        projects = _normalize_projects(raw)

        if project_id and project_id not in {p["id"] for p in projects}:
            audit_log("auth.consent_fail", org=org_id, reason="project_not_in_org")
            org_name = claims.get("organizationName", org_id)
            return _render(
                txn, client_name, token_value=token, projects=projects, status=400,
                banner=_error_banner(
                    f"Project '{project_id}' does not belong to organization "
                    f"'{org_name}'. Pick one of its projects below."
                ),
            )
        if not project_id:
            if len(projects) == 1:
                project_id = projects[0]["id"]
            else:
                org_name = claims.get("organizationName", org_id)
                return _render(
                    txn, client_name, token_value=token, projects=projects,
                    banner=f'<p class="org">Token accepted for organization '
                           f"<strong>{html.escape(org_name)}</strong>.</p>",
                )

        params = payload["params"]
        code = codec.encode(
            "code",
            {
                "ahq_token": token,
                "project_id": project_id,
                "client_id": payload["client_id"],
                "redirect_uri": params["redirect_uri"],
                "redirect_uri_provided_explicitly": params["redirect_uri_provided_explicitly"],
                "code_challenge": params["code_challenge"],
                "scopes": params.get("scopes") or [],
            },
            CODE_TTL,
        )
        audit_log("auth.consent_ok", org=org_id, project=project_id)
        return RedirectResponse(
            construct_redirect_uri(params["redirect_uri"], code=code, state=params.get("state")),
            status_code=302,
            headers={"Cache-Control": "no-store"},
        )

    return consent_get, consent_post
