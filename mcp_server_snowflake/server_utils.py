from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from mcp_server_snowflake.object_manager.tools import validate_object_tool
from mcp_server_snowflake.query_manager.tools import validate_sql_type


class CheckQueryType(Middleware):
    """Middleware that checks SQL statement to ensure it is of an approved type."""

    def __init__(self, sql_allow_list: list[str], sql_disallow_list: list[str]):
        self.sql_allow_list = sql_allow_list
        self.sql_disallow_list = sql_disallow_list

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Called for all MCP tool calls."""
        tool_name = context.message.name

        # Check SQL statement permissions before running query
        if tool_name.lower() == "run_snowflake_query" and context.message.arguments.get(
            "statement", None
        ):
            statement_type, valid = validate_sql_type(
                context.message.arguments.get("statement", None),
                self.sql_allow_list,
                self.sql_disallow_list,
            )

        elif tool_name.lower().startswith("create") or tool_name.lower().startswith(
            "drop"
        ):
            statement_type, valid = validate_object_tool(
                tool_name, self.sql_allow_list, self.sql_disallow_list
            )

        # Allow other tools to proceed
        else:
            valid = True

        if valid:
            return await call_next(context)
        else:
            raise ToolError(
                f"Statement type of {statement_type} is not allowed. Please review sql statement permissions in configuration file."
            )


def initialize_middleware(server: FastMCP, snowflake_service):
    server.add_middleware(
        CheckQueryType(
            sql_allow_list=snowflake_service.sql_statement_allowed,
            sql_disallow_list=snowflake_service.sql_statement_disallowed,
        )
    )
