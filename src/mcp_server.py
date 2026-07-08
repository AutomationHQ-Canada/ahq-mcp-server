import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.config.ahq_services import settings
from src.config.credentials import AhqCredentials
from src.clients.bundle import ClientBundle, DEFAULT_BUNDLE
from src.clients.generic_client import SERVICE_MAP
from src.tools.crawl_url import crawl_url as _crawl_url
from src.tools.extract_requirements import extract_requirements as _extract_requirements

server = Server("ahq-mcp-server")


class _HttpClientHolder:
    """
    Plain mutable holder (NOT a contextvars.ContextVar) for the one shared, long-lived
    httpx.AsyncClient used in hosted HTTP mode. A ContextVar was tried first and doesn't work
    here: it's set once in the Starlette lifespan task, but uvicorn spawns each incoming
    request in a separate, unrelated task — contextvars only propagate to child tasks created
    from a context where the var is already set, so the lifespan's value never reaches
    call_tool's task. A plain attribute, set once at startup and read on every call, is exactly
    what's needed since the client itself is intentionally shared across every tenant/request
    (only credentials vary per-request, and those already flow correctly through the SDK's own
    request_ctx contextvar since it's set inside the request-handling task itself).
    """

    client = None


app_http_client = _HttpClientHolder()

# Tools that are unsafe or meaningless to run from a centrally-hosted server: check_local_agent_status
# probes the SERVER's own localhost (not the caller's machine); crawl_url fetches arbitrary
# caller-given URLs from inside the cluster (SSRF surface); extract_requirements reads an arbitrary
# path off the SERVER's disk (arbitrary-file-read surface once "local" isn't the caller's laptop).
_HOSTED_UNSUPPORTED = {"check_local_agent_status", "crawl_url", "extract_requirements"}


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

async def _get_ahq_context(clients: ClientBundle) -> dict:
    results = await asyncio.gather(
        clients.user.get_current_user(),
        clients.user.list_projects(),
        clients.asset.list_websites(),
        clients.config.list_environments(),
        clients.test_mgmt.list_epics(),
        clients.test_mgmt.list_bots(),
        clients.test_mgmt.list_suites(),
        clients.background.get_queue_status(),
        return_exceptions=True,
    )
    keys = ["user", "projects", "websites", "environments", "epics", "bots", "suites", "queue"]
    return {
        k: (str(v) if isinstance(v, Exception) else v)
        for k, v in zip(keys, results)
    }


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    # Context
    Tool(name="get_ahq_context", description="Load full AHQ project snapshot from all services in parallel. Call this first before any other action.", inputSchema={"type": "object", "properties": {}}),

    # Asset — websites
    Tool(name="search_websites", description="Search for an existing website by name in AHQ.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
    Tool(name="create_website", description="Create a new website record in AHQ.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "url": {"type": "string"}}, "required": ["name", "url"]}),

    # Asset — pages
    Tool(name="list_pages", description="List all pages under a website.", inputSchema={"type": "object", "properties": {"website_id": {"type": "string"}}, "required": ["website_id"]}),
    Tool(name="create_page", description="Create a page under an existing website.", inputSchema={"type": "object", "properties": {"website_id": {"type": "string"}, "name": {"type": "string"}, "url": {"type": "string"}}, "required": ["website_id", "name", "url"]}),
    Tool(name="get_page_by_url", description="Check if a page already exists at a given URL (for dedup).", inputSchema={"type": "object", "properties": {"website_id": {"type": "string"}, "url": {"type": "string"}}, "required": ["website_id", "url"]}),
    Tool(name="add_locators", description="Batch-create locators for a page.", inputSchema={"type": "object", "properties": {"page_id": {"type": "string"}, "website_id": {"type": "string"}, "locators": {"type": "array", "items": {"type": "object"}}}, "required": ["page_id", "website_id", "locators"]}),

    # Test scripts
    Tool(name="list_test_scripts", description="List or search test scripts by name.", inputSchema={"type": "object", "properties": {"name": {"type": "string", "description": "Optional name filter"}}}),
    Tool(name="get_test_script", description="Get full details of a test script by ID.", inputSchema={"type": "object", "properties": {"script_id": {"type": "string"}}, "required": ["script_id"]}),
    Tool(
        name="create_test_script",
        description=(
            "Create a test script in AHQ. Each step's templateId MUST come from "
            "list_step_templates/search_step_templates — never invent one. Call get_step_template "
            "on the chosen template first to see which params sub-fields it actually uses."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "page_id": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "templateId": {"type": "string", "description": "Real template ID from list_step_templates/search_step_templates — required, never fabricate"},
                            "testStepTitle": {"type": "string", "description": "Human-readable label for this step, e.g. 'Enter username'"},
                            "sequence": {"type": "integer", "description": "0-based order of this step within the script"},
                            "params": {
                                "type": "object",
                                "description": "Only set the sub-fields the chosen template actually uses (check get_step_template first)",
                                "properties": {
                                    "uiLocator": {
                                        "type": "object",
                                        "description": "Element target for click/type/assert-element style steps",
                                        "properties": {
                                            "locateBy": {"type": "string", "description": "Strategy: xpath, css, id, class, ..."},
                                            "locatorValue": {"type": "string", "description": "The selector itself; may contain {{placeholder}} tokens"},
                                            "locatorType": {"type": "string", "description": "Element type, e.g. button, input, select"}
                                        }
                                    },
                                    "text": {"type": "object", "description": "Input value for type/navigate steps", "properties": {"value": {"type": "string"}}},
                                    "expected": {"type": "object", "description": "Expected value for assert steps", "properties": {"value": {"type": "string"}}},
                                    "variable": {"type": "object", "description": "Runtime variable reference", "properties": {"value": {"type": "string"}}}
                                }
                            }
                        },
                        "required": ["templateId", "testStepTitle"]
                    }
                }
            },
            "required": ["name", "steps"]
        }
    ),

    # Step templates — resolve real templateIds before writing any test step
    Tool(name="list_step_templates", description="List available step templates (built-in action types + org-defined Common Functions) for the current project. Use this or search_step_templates before writing any test step — templateId is never invented.", inputSchema={"type": "object", "properties": {"offset": {"type": "integer", "default": 0}}}),
    Tool(name="search_step_templates", description="Search step templates by title (e.g. 'Click', 'Navigate', 'Assert Text') to find the real templateId for an action.", inputSchema={"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}),
    Tool(name="get_step_template", description="Get full detail of a step template by ID, including which params sub-fields it expects.", inputSchema={"type": "object", "properties": {"template_id": {"type": "string"}}, "required": ["template_id"]}),

    # Organization
    Tool(name="list_epics", description="List all epics in the project.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="list_bots", description="List all test bots in the project.", inputSchema={"type": "object", "properties": {"name": {"type": "string", "description": "Optional name filter"}}}),
    Tool(name="list_suites", description="List all test suites in the project.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="list_environments", description="List all configured environments.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="create_suite", description="Create a new test suite.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
    Tool(name="add_scripts_to_suite", description="Add test scripts to a test suite.", inputSchema={"type": "object", "properties": {"suite_id": {"type": "string"}, "script_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["suite_id", "script_ids"]}),

    # Execution
    Tool(name="execute_bot", description="Run a test bot immediately. execution_configuration must include gridUrlForExecution and browser — get these from list_environments().", inputSchema={"type": "object", "properties": {"bot_id": {"type": "string"}, "execution_configuration": {"type": "object", "description": "Must include gridUrlForExecution, browser. Get from list_environments().", "properties": {"gridUrlForExecution": {"type": "string"}, "browser": {"type": "string"}, "profileId": {"type": "string"}}}, "partial_execution": {"type": "boolean", "default": False}}, "required": ["bot_id", "execution_configuration"]}),
    Tool(name="schedule_bot_recurring", description="Schedule a bot on a cron expression. execution_configuration from list_environments().", inputSchema={"type": "object", "properties": {"bot_id": {"type": "string"}, "execution_configuration": {"type": "object"}, "cron": {"type": "string", "description": "Cron expression e.g. '0 0 * * *'"}}, "required": ["bot_id", "execution_configuration", "cron"]}),
    Tool(name="schedule_bot_once", description="Schedule a bot to run once at a specific epoch millisecond timestamp.", inputSchema={"type": "object", "properties": {"bot_id": {"type": "string"}, "execution_configuration": {"type": "object"}, "epoch_ms": {"type": "integer"}}, "required": ["bot_id", "execution_configuration", "epoch_ms"]}),
    Tool(name="cancel_schedule", description="Cancel a recurring scheduled bot.", inputSchema={"type": "object", "properties": {"schedule_id": {"type": "string"}}, "required": ["schedule_id"]}),
    Tool(name="get_job_status", description="Get the status and details of an execution job.", inputSchema={"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]}),
    Tool(name="list_recent_runs", description="List recent execution runs, optionally filtered by bot.", inputSchema={"type": "object", "properties": {"bot_id": {"type": "string"}, "limit": {"type": "integer", "default": 10}}}),

    # Reporting
    Tool(name="get_execution_report", description="Get full pass/fail execution report for a job.", inputSchema={"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]}),
    Tool(name="get_execution_screenshots", description="Get screenshots from a test execution (useful for failures).", inputSchema={"type": "object", "properties": {"execution_id": {"type": "string"}}, "required": ["execution_id"]}),
    Tool(name="get_performance_report", description="Get performance/ROI metrics from an execution.", inputSchema={"type": "object", "properties": {"execution_id": {"type": "string"}}, "required": ["execution_id"]}),

    # Application context
    Tool(name="crawl_url", description="Crawl a live web application and capture locators (XPath, CSS, aria-label) for test script generation.", inputSchema={"type": "object", "properties": {"url": {"type": "string"}, "credentials": {"type": "object", "properties": {"username": {"type": "string"}, "password": {"type": "string"}}}, "max_pages": {"type": "integer", "default": 20}}, "required": ["url"]}),
    Tool(
        name="extract_requirements",
        description=(
            "Parse a local requirements file (PDF/DOCX/XLSX/CSV/TXT/MD) into structured text or rows, "
            "for generating Given/When/Then test cases. Does not generate test cases itself — "
            "returns extracted content for the caller to reason over."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the requirements file"},
            },
            "required": ["file_path"],
        },
    ),

    # API / Performance Testing (mtaf-core) — a separate flow from UI bot testing, for
    # REST/GraphQL request validation, chained-workflow testing, and JMeter-backed load testing.
    Tool(name="list_api_collections", description="List API test collections (Postman-style, for REST/GraphQL testing — separate from UI test scripts).", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_api_collection", description="Get full details of an API collection by ID.", inputSchema={"type": "object", "properties": {"collection_id": {"type": "string"}}, "required": ["collection_id"]}),
    Tool(name="create_api_collection", description="Create a new API collection to group related API requests.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "variables": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "initialValue": {"type": "string"}}}, "description": "Collection-scoped variables, e.g. base_url"}}, "required": ["name"]}),
    Tool(name="list_api_requests", description="List all saved API requests.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_api_request", description="Get full details of an API request by ID.", inputSchema={"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"]}),
    Tool(name="create_api_request", description="Create and save a new API request (REST/GraphQL).", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]}, "url": {"type": "string", "description": "May contain {{varName:defaultValue}} placeholders"}, "collection_id": {"type": "string"}, "query_params": {"type": "array", "items": {"type": "object"}}, "header_params": {"type": "array", "items": {"type": "object"}}, "body_params": {"description": "Request body, shape depends on contentType"}}, "required": ["name", "method", "url"]}),
    Tool(name="test_api_request", description="Execute a saved (or ad-hoc) API request once and get the response, without needing a full workflow.", inputSchema={"type": "object", "properties": {"request": {"type": "object", "description": "Full ApiRequestV2 object: name, method, url, headerParams, queryParams, bodyParams, ..."}, "variables": {"type": "object", "description": "Pre-seeded {{var}} overrides, e.g. {\"token\": \"abc123\"}"}, "data_row": {"type": "object", "description": "Test-data row: column name -> value"}, "environment": {"type": "string", "description": "Name of the collection environment to activate"}}, "required": ["request"]}),
    Tool(name="import_curl", description="Import one or more curl commands as API requests (splits on lines starting with 'curl'). Set save=false to preview without persisting.", inputSchema={"type": "object", "properties": {"commands": {"type": "string"}, "save": {"type": "boolean", "default": True}, "collection_name": {"type": "string", "default": "cURL Import"}, "collection_id": {"type": "string", "description": "Add to an existing collection instead of creating a new one"}}, "required": ["commands"]}),
    Tool(name="import_postman_collection", description="Import a Postman Collection (v2.0/v2.1 JSON) as API requests. Set save=false to preview without persisting.", inputSchema={"type": "object", "properties": {"collection": {"type": "object", "description": "Raw Postman collection JSON"}, "save": {"type": "boolean", "default": True}}, "required": ["collection"]}),
    Tool(name="list_workflows", description="List chained API-request workflows.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_workflow", description="Get full details of a workflow by ID.", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "string"}}, "required": ["workflow_id"]}),
    Tool(name="create_workflow", description="Create a chained-API-request workflow (multiple requests run in sequence, e.g. for a user journey).", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "workflow_list": {"type": "array", "items": {"type": "object"}, "description": "Ordered list of chained requests — if the shape is unclear, use get_service_spec first"}}, "required": ["name"]}),
    Tool(name="test_workflow", description="Run a one-off chained API workflow test (does not need to be saved first).", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "api_requests": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "integer"}, "method": {"type": "string"}, "name": {"type": "string"}, "url": {"type": "string"}, "headers": {"type": "object"}, "body": {}}}, "description": "Max 50 requests"}, "description": {"type": "string"}, "load_ratio": {"type": "number"}}, "required": ["name", "api_requests"]}),
    Tool(name="list_performance_bots", description="List performance/load test bots (JMeter-backed).", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_performance_bot", description="Get full details of a performance bot by ID.", inputSchema={"type": "object", "properties": {"bot_id": {"type": "string"}}, "required": ["bot_id"]}),
    Tool(name="run_performance_bot", description="Run an existing performance bot by ID. Runs async in the background (can take hours) — returns a metrics ID immediately for polling via get_performance_results.", inputSchema={"type": "object", "properties": {"bot_id": {"type": "string"}}, "required": ["bot_id"]}),
    Tool(name="stop_performance_bot", description="Stop a running performance bot.", inputSchema={"type": "object", "properties": {"bot_id": {"type": "string"}}, "required": ["bot_id"]}),
    Tool(name="get_performance_results", description="Poll dashboard results (throughput, response times, errors) for a performance run by metrics ID.", inputSchema={"type": "object", "properties": {"metrics_id": {"type": "string"}, "polling": {"type": "boolean", "default": True}}, "required": ["metrics_id"]}),
    Tool(name="list_vault_secrets", description="List vault secret names/keys (metadata only — never returns decrypted values; ask the user to check the UI if the raw value is needed).", inputSchema={"type": "object", "properties": {}}),

    # Local execution agent — for TestBots configured to run on the user's own machine
    # (gridUrlForExecution contains "localhost"), not the cloud grid.
    Tool(name="check_local_agent_status", description="Check whether the local execution agent is running on this machine. Call this before execute_bot if the bot's environment targets localhost.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="list_local_agents", description="List machines in this project that have the local execution agent installed/registered.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="list_fake_data_types", description="List available fake/synthetic test-data generator types (e.g. Email, SIN, Full Name) usable with generate_fake_data.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="generate_fake_data", description="Generate one synthetic value of a given fake-data type, for populating test data.", inputSchema={"type": "object", "properties": {"display_name": {"type": "string", "description": "Must be one of the names returned by list_fake_data_types"}}, "required": ["display_name"]}),

    # Email
    Tool(name="send_email", description="Send a transactional email through AHQ (e.g. a test run summary).", inputSchema={"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "message": {"type": "string"}, "multiple_tos": {"type": "array", "items": {"type": "string"}}, "from_address": {"type": "string"}}, "required": ["to", "subject", "message"]}),

    # Consumer-Driven Contract Testing (Pact) — niche capability for API contract verification
    Tool(name="list_consumers", description="List Pact contract-testing consumers (API clients).", inputSchema={"type": "object", "properties": {}}),
    Tool(name="create_consumer", description="Create a Pact consumer.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
    Tool(name="list_providers", description="List Pact contract-testing providers (API servers).", inputSchema={"type": "object", "properties": {}}),
    Tool(name="create_provider", description="Create a Pact provider.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
    Tool(name="list_contracts", description="List Pact contracts (consumer-provider agreements).", inputSchema={"type": "object", "properties": {}}),
    Tool(name="create_contract", description="Create a Pact contract between a consumer and provider for one API interaction.", inputSchema={"type": "object", "properties": {"consumer_id": {"type": "string"}, "provider_id": {"type": "string"}, "method": {"type": "string"}, "contract_description": {"type": "string"}, "request_body": {"type": "string"}, "response_body": {"type": "string"}}, "required": ["consumer_id", "provider_id", "method"]}),
    Tool(name="run_pact_tests", description="Run both consumer and provider Pact verification tests for a contract.", inputSchema={"type": "object", "properties": {"contract_id": {"type": "string"}}, "required": ["contract_id"]}),

    # Service Virtualization (WireMock-backed API mocking)
    Tool(name="list_mock_mappings", description="List service-virtualization mock API mappings, optionally filtered.", inputSchema={"type": "object", "properties": {"method": {"type": "string"}, "search": {"type": "string"}}}),
    Tool(name="get_mock_mapping", description="Get a mock mapping by ID.", inputSchema={"type": "object", "properties": {"mapping_id": {"type": "string"}}, "required": ["mapping_id"]}),
    Tool(name="get_mock_mapping_template", description="Get an example mock-mapping JSON template to use as a starting point for create_mock_mapping.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="create_mock_mapping", description="Create a mock API mapping (request matcher + canned response) for service virtualization. Call get_mock_mapping_template first if the shape is unclear.", inputSchema={"type": "object", "properties": {"mapping": {"type": "object", "description": "WireMock-style mapping: {request: {method, url, headers}, response: {status, body, headers}}"}}, "required": ["mapping"]}),
    Tool(name="delete_mock_mapping", description="Delete a mock API mapping by ID.", inputSchema={"type": "object", "properties": {"mapping_id": {"type": "string"}}, "required": ["mapping_id"]}),

    # Auto-discovery — future-proof API access
    Tool(
        name="get_service_spec",
        description=(
            "Fetch the full OpenAPI spec (all endpoints, schemas, params) for any AHQ service. "
            "Use this to discover new or unknown endpoints when the hand-written tools don't cover a feature. "
            f"Available services: {', '.join(sorted(set(SERVICE_MAP.keys())))}"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Service name e.g. 'ahq-asset-services' or short alias 'asset'",
                }
            },
            "required": ["service_name"],
        },
    ),
    Tool(
        name="call_api",
        description=(
            "Call ANY AHQ REST endpoint directly. Use after get_service_spec to invoke a discovered endpoint "
            "that is not covered by a hand-written tool. Supports GET, POST, PUT, DELETE."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name or alias"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "path": {"type": "string", "description": "Endpoint path e.g. '/rest/api/websites'"},
                "body": {"type": "object", "description": "Request body for POST/PUT"},
                "params": {"type": "object", "description": "Query parameters"},
                "extra_headers": {"type": "object", "description": "Additional headers if required"},
            },
            "required": ["service", "method", "path"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def _resolve_clients() -> tuple[ClientBundle, bool]:
    """
    stdio mode: no Starlette request in context -> DEFAULT_BUNDLE (credentials from .env, one
    per process, identical to today's behavior).
    HTTP mode (src/http_server.py): a Starlette Request is available per tool-call via
    server.request_context.request -> build a fresh per-request ClientBundle from that
    request's X-API-AUTH-KEY/org-id/projectId headers, sharing the one pooled httpx.AsyncClient
    set up by the HTTP entrypoint's lifespan.
    """
    try:
        req = server.request_context.request
    except LookupError:
        req = None
    if req is None:
        return DEFAULT_BUNDLE, False
    creds = AhqCredentials.from_headers(req.headers, base_url=settings.ahq_base_url)
    return ClientBundle.build(credentials=creds, http_client=app_http_client.client), True


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        clients, is_hosted = _resolve_clients()
        result = await _dispatch(name, arguments, clients, is_hosted)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _dispatch(name: str, args: dict, clients: ClientBundle, is_hosted: bool = False):
    if is_hosted and name in _HOSTED_UNSUPPORTED:
        return {"error": f"{name} is not available over the hosted MCP server yet — run ahq-mcp-server locally via stdio for this tool."}

    # Context
    if name == "get_ahq_context":
        return await _get_ahq_context(clients)

    # Asset
    if name == "search_websites":
        return await clients.asset.search_websites(args["name"])
    if name == "create_website":
        return await clients.asset.create_website(args["name"], args["url"])
    if name == "list_pages":
        return await clients.asset.list_pages(args["website_id"])
    if name == "create_page":
        return await clients.asset.create_page(args["website_id"], args["name"], args["url"])
    if name == "get_page_by_url":
        return await clients.asset.get_page_by_url(args["website_id"], args["url"])
    if name == "add_locators":
        return await clients.asset.add_locators(args["page_id"], args["website_id"], args["locators"])

    # Test scripts
    if name == "list_test_scripts":
        return await clients.test_mgmt.list_test_scripts(args.get("name"))
    if name == "get_test_script":
        return await clients.test_mgmt.get_test_script(args["script_id"])
    if name == "create_test_script":
        return await clients.test_mgmt.create_test_script(args["name"], args["steps"], args.get("page_id"))
    if name == "list_step_templates":
        return await clients.test_mgmt.list_templates(args.get("offset", 0))
    if name == "search_step_templates":
        return await clients.test_mgmt.search_templates(args["title"])
    if name == "get_step_template":
        return await clients.test_mgmt.get_template(args["template_id"])

    # Organization
    if name == "list_epics":
        return await clients.test_mgmt.list_epics()
    if name == "list_bots":
        return await clients.test_mgmt.list_bots(args.get("name"))
    if name == "list_suites":
        return await clients.test_mgmt.list_suites()
    if name == "list_environments":
        return await clients.config.list_environments()
    if name == "create_suite":
        return await clients.test_mgmt.create_suite(args["name"])
    if name == "add_scripts_to_suite":
        return await clients.test_mgmt.add_scripts_to_suite(args["suite_id"], args["script_ids"])

    # Execution
    if name == "execute_bot":
        # Correct entry point: executor-services validates bot, fan-outs, then calls background-v2 internally
        return await clients.executor.execute_bot(args["bot_id"], args["execution_configuration"], args.get("partial_execution", False))
    if name == "schedule_bot_recurring":
        return await clients.background.schedule_bot_recurring(args["bot_id"], args["execution_configuration"], args["cron"])
    if name == "schedule_bot_once":
        return await clients.background.schedule_bot_once(args["bot_id"], args["execution_configuration"], args["epoch_ms"])
    if name == "cancel_schedule":
        return await clients.background.cancel_schedule(args["schedule_id"])
    if name == "get_job_status":
        return await clients.background.get_job_status(args["job_id"])
    if name == "list_recent_runs":
        return await clients.background.list_recent_runs(args.get("bot_id"), args.get("limit", 10))

    # Reporting
    if name == "get_execution_report":
        return await clients.background.get_execution_report(args["job_id"])
    if name == "get_execution_screenshots":
        return await clients.executor.get_execution_screenshots(args["execution_id"])
    if name == "get_performance_report":
        return await clients.executor.get_performance_report(args["execution_id"])

    # Application context
    if name == "crawl_url":
        return await _crawl_url(
            url=args["url"],
            credentials=args.get("credentials"),
            max_pages=args.get("max_pages", 20),
        )
    if name == "extract_requirements":
        return _extract_requirements(args["file_path"])

    # API / Performance Testing (mtaf-core)
    if name == "list_api_collections":
        return await clients.managed_testing.list_api_collections()
    if name == "get_api_collection":
        return await clients.managed_testing.get_api_collection(args["collection_id"])
    if name == "create_api_collection":
        return await clients.managed_testing.create_api_collection(args["name"], args.get("description"), args.get("variables"))
    if name == "list_api_requests":
        return await clients.managed_testing.list_api_requests()
    if name == "get_api_request":
        return await clients.managed_testing.get_api_request(args["request_id"])
    if name == "create_api_request":
        return await clients.managed_testing.create_api_request(
            args["name"], args["method"], args["url"], args.get("collection_id"),
            args.get("query_params"), args.get("header_params"), args.get("body_params"),
        )
    if name == "test_api_request":
        return await clients.managed_testing.test_api_request(
            args["request"], args.get("variables"), args.get("data_row"), args.get("environment")
        )
    if name == "import_curl":
        return await clients.managed_testing.import_curl(
            args["commands"], args.get("save", True), args.get("collection_name", "cURL Import"), args.get("collection_id")
        )
    if name == "import_postman_collection":
        return await clients.managed_testing.import_postman(args["collection"], args.get("save", True))
    if name == "list_workflows":
        return await clients.managed_testing.list_workflows()
    if name == "get_workflow":
        return await clients.managed_testing.get_workflow(args["workflow_id"])
    if name == "create_workflow":
        return await clients.managed_testing.create_workflow(args["name"], args.get("description"), args.get("workflow_list"))
    if name == "test_workflow":
        return await clients.managed_testing.test_workflow(
            args["name"], args["api_requests"], args.get("description"), args.get("load_ratio")
        )
    if name == "list_performance_bots":
        return await clients.managed_testing.list_performance_bots()
    if name == "get_performance_bot":
        return await clients.managed_testing.get_performance_bot(args["bot_id"])
    if name == "run_performance_bot":
        return await clients.managed_testing.run_performance_bot(args["bot_id"])
    if name == "stop_performance_bot":
        return await clients.managed_testing.stop_performance_bot(args["bot_id"])
    if name == "get_performance_results":
        return await clients.managed_testing.get_performance_results(args["metrics_id"], args.get("polling", True))
    if name == "list_vault_secrets":
        return await clients.managed_testing.list_vault_secrets()

    # Local execution agent
    if name == "check_local_agent_status":
        return await clients.local_exec.get_agent_status()
    if name == "list_local_agents":
        return await clients.local_exec.list_registered_agents()
    if name == "list_fake_data_types":
        return await clients.local_exec.list_fake_data_types()
    if name == "generate_fake_data":
        return await clients.local_exec.generate_fake_data(args["display_name"])

    # Email
    if name == "send_email":
        return await clients.email.send_email(
            args["to"], args["subject"], args["message"], args.get("multiple_tos"), args.get("from_address")
        )

    # Pact contract testing
    if name == "list_consumers":
        return await clients.cdct.list_consumers()
    if name == "create_consumer":
        return await clients.cdct.create_consumer(args["name"])
    if name == "list_providers":
        return await clients.cdct.list_providers()
    if name == "create_provider":
        return await clients.cdct.create_provider(args["name"])
    if name == "list_contracts":
        return await clients.cdct.list_contracts()
    if name == "create_contract":
        return await clients.cdct.create_contract(
            args["consumer_id"], args["provider_id"], args["method"],
            args.get("contract_description"), args.get("request_body"), args.get("response_body"),
        )
    if name == "run_pact_tests":
        return await clients.cdct.run_both_tests(args["contract_id"])

    # Service Virtualization
    if name == "list_mock_mappings":
        return await clients.virtualization.list_mock_mappings(args.get("method"), args.get("search"))
    if name == "get_mock_mapping":
        return await clients.virtualization.get_mock_mapping(args["mapping_id"])
    if name == "get_mock_mapping_template":
        return await clients.virtualization.get_mock_mapping_template()
    if name == "create_mock_mapping":
        return await clients.virtualization.create_mock_mapping(args["mapping"])
    if name == "delete_mock_mapping":
        return await clients.virtualization.delete_mock_mapping(args["mapping_id"])

    # Auto-discovery
    if name == "get_service_spec":
        return await clients.generic.get_service_spec(args["service_name"])
    if name == "call_api":
        return await clients.generic.call_api(
            service=args["service"],
            method=args["method"],
            path=args["path"],
            body=args.get("body"),
            params=args.get("params"),
            extra_headers=args.get("extra_headers"),
        )

    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    try:
        me = await DEFAULT_BUNDLE.asset.validate_token()
        name = me.get("name") or me.get("userId", "unknown")
        print(f"[ahq-mcp-server] Connected as: {name}", file=sys.stderr)
    except Exception as e:
        print(f"[ahq-mcp-server] WARNING: Token validation failed: {e}", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
