import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.clients.asset_client import asset_client
from src.clients.test_mgmt_client import test_mgmt_client
from src.clients.background_client import background_client
from src.clients.config_client import config_client
from src.clients.generic_client import generic_client, SERVICE_MAP
from src.clients.user_client import user_client
from src.clients.executor_client import executor_client
from src.tools.crawl_url import crawl_url as _crawl_url

server = Server("ahq-mcp-server")


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

async def _get_ahq_context() -> dict:
    results = await asyncio.gather(
        user_client.get_current_user(),
        user_client.list_projects(),
        asset_client.list_websites(),
        config_client.list_environments(),
        test_mgmt_client.list_epics(),
        test_mgmt_client.list_bots(),
        test_mgmt_client.list_suites(),
        background_client.get_queue_status(),
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
    Tool(name="create_test_script", description="Create a test script in AHQ.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "steps": {"type": "array", "items": {"type": "object"}}, "page_id": {"type": "string"}}, "required": ["name", "steps"]}),

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

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _dispatch(name: str, args: dict):
    # Context
    if name == "get_ahq_context":
        return await _get_ahq_context()

    # Asset
    if name == "search_websites":
        return await asset_client.search_websites(args["name"])
    if name == "create_website":
        return await asset_client.create_website(args["name"], args["url"])
    if name == "list_pages":
        return await asset_client.list_pages(args["website_id"])
    if name == "create_page":
        return await asset_client.create_page(args["website_id"], args["name"], args["url"])
    if name == "get_page_by_url":
        return await asset_client.get_page_by_url(args["website_id"], args["url"])
    if name == "add_locators":
        return await asset_client.add_locators(args["page_id"], args["website_id"], args["locators"])

    # Test scripts
    if name == "list_test_scripts":
        return await test_mgmt_client.list_test_scripts(args.get("name"))
    if name == "get_test_script":
        return await test_mgmt_client.get_test_script(args["script_id"])
    if name == "create_test_script":
        return await test_mgmt_client.create_test_script(args["name"], args["steps"], args.get("page_id"))

    # Organization
    if name == "list_epics":
        return await test_mgmt_client.list_epics()
    if name == "list_bots":
        return await test_mgmt_client.list_bots(args.get("name"))
    if name == "list_suites":
        return await test_mgmt_client.list_suites()
    if name == "list_environments":
        return await config_client.list_environments()
    if name == "create_suite":
        return await test_mgmt_client.create_suite(args["name"])
    if name == "add_scripts_to_suite":
        return await test_mgmt_client.add_scripts_to_suite(args["suite_id"], args["script_ids"])

    # Execution
    if name == "execute_bot":
        # Correct entry point: executor-services validates bot, fan-outs, then calls background-v2 internally
        return await executor_client.execute_bot(args["bot_id"], args["execution_configuration"], args.get("partial_execution", False))
    if name == "schedule_bot_recurring":
        return await background_client.schedule_bot_recurring(args["bot_id"], args["execution_configuration"], args["cron"])
    if name == "schedule_bot_once":
        return await background_client.schedule_bot_once(args["bot_id"], args["execution_configuration"], args["epoch_ms"])
    if name == "cancel_schedule":
        return await background_client.cancel_schedule(args["schedule_id"])
    if name == "get_job_status":
        return await background_client.get_job_status(args["job_id"])
    if name == "list_recent_runs":
        return await background_client.list_recent_runs(args.get("bot_id"), args.get("limit", 10))

    # Reporting
    if name == "get_execution_report":
        return await background_client.get_execution_report(args["job_id"])
    if name == "get_execution_screenshots":
        return await executor_client.get_execution_screenshots(args["execution_id"])
    if name == "get_performance_report":
        return await executor_client.get_performance_report(args["execution_id"])

    # Application context
    if name == "crawl_url":
        return await _crawl_url(
            url=args["url"],
            credentials=args.get("credentials"),
            max_pages=args.get("max_pages", 20),
        )

    # Auto-discovery
    if name == "get_service_spec":
        return await generic_client.get_service_spec(args["service_name"])
    if name == "call_api":
        return await generic_client.call_api(
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
        me = await asset_client.validate_token()
        name = me.get("name") or me.get("userId", "unknown")
        print(f"[ahq-mcp-server] Connected as: {name}", file=sys.stderr)
    except Exception as e:
        print(f"[ahq-mcp-server] WARNING: Token validation failed: {e}", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
