import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.clients.ahq_api_client import ahq_client
from src.tools.crawl_url import crawl_url as _crawl_url

server = Server("ahq-mcp-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="crawl_url",
            description=(
                "Crawl a live web application and capture interactive element locators "
                "(XPath, CSS, aria-label) for AHQ test script generation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to crawl"},
                    "credentials": {
                        "type": "object",
                        "description": "Optional login credentials {username, password}",
                        "properties": {
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                        },
                    },
                    "max_pages": {
                        "type": "integer",
                        "default": 20,
                        "description": "Max pages to crawl (default 20)",
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="create_website",
            description="Create a website record in AHQ asset-services.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Website display name"},
                    "url": {"type": "string", "description": "Root URL of the website"},
                },
                "required": ["name", "url"],
            },
        ),
        Tool(
            name="create_page",
            description="Create a page under an existing website in AHQ asset-services.",
            inputSchema={
                "type": "object",
                "properties": {
                    "website_id": {"type": "string"},
                    "name": {"type": "string", "description": "Page display name"},
                    "url": {"type": "string", "description": "Full page URL"},
                },
                "required": ["website_id", "name", "url"],
            },
        ),
        Tool(
            name="add_locators",
            description="Batch-create locators for a page in AHQ asset-services.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string"},
                    "website_id": {"type": "string"},
                    "locators": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of locator objects from crawl_url",
                    },
                },
                "required": ["page_id", "website_id", "locators"],
            },
        ),
        Tool(
            name="create_test_script",
            description="Create a test script in AHQ test-management-services.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Script name e.g. 'Login Page — Happy Path'"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of step objects using AHQ action types",
                    },
                    "page_id": {"type": "string", "description": "Optional page to link the script to"},
                },
                "required": ["name", "steps"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "crawl_url":
            result = await _crawl_url(
                url=arguments["url"],
                credentials=arguments.get("credentials"),
                max_pages=arguments.get("max_pages", 20),
            )
        elif name == "create_website":
            result = await ahq_client.create_website(arguments["name"], arguments["url"])
        elif name == "create_page":
            result = await ahq_client.create_page(
                arguments["website_id"], arguments["name"], arguments["url"]
            )
        elif name == "add_locators":
            result = await ahq_client.add_locators(
                arguments["page_id"], arguments["website_id"], arguments["locators"]
            )
        elif name == "create_test_script":
            result = await ahq_client.create_test_script(
                arguments["name"], arguments["steps"], arguments.get("page_id")
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    try:
        me = await ahq_client.validate_token()
        name = me.get("name") or me.get("userId", "unknown")
        print(f"[ahq-mcp-server] Connected as: {name}", file=sys.stderr)
    except Exception as e:
        print(f"[ahq-mcp-server] WARNING: Token validation failed: {e}", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
