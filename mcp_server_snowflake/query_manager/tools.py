from typing import Annotated

import sqlglot
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from pydantic import Field

from mcp_server_snowflake.query_manager.prompts import query_tool_prompt
from mcp_server_snowflake.utils import SnowflakeException


def run_query(statement: str, snowflake_service):
    """
    Execute SQL statement and fetch all results using Snowflake connector.

    Establishes a connection to Snowflake, executes the provided SQL statement,
    and returns all results using a dictionary cursor for easier data access.

    Parameters
    ----------
    statement : str
        SQL statement to execute
    snowflake_service : SnowflakeService
        The Snowflake service instance to use for connection

    Returns
    -------
    list[dict]
        List of dictionaries containing query results with column names as keys

    Raises
    ------
    snowflake.connector.errors.Error
        If connection fails or SQL execution encounters an error
    """
    try:
        with snowflake_service.get_connection(
            use_dict_cursor=True,
            session_parameters=snowflake_service.get_query_tag_param(),
        ) as (
            con,
            cur,
        ):
            cur.execute(statement)
            return cur.fetchall()
    except Exception as e:
        raise SnowflakeException(
            tool="query_manager",
            message=f"Error executing query: {e}",
            status_code=500,
        )


def initialize_query_manager_tool(server: FastMCP, snowflake_service):
    @server.tool(
        name="run_snowflake_query",
        description=query_tool_prompt,
    )
    def run_query_tool(
        statement: Annotated[
            str,
            Field(description="SQL query to execute"),
        ],
    ):
        return run_query(statement, snowflake_service)


def get_statement_type(sql_string):
    """
    Parses a SQL statement and returns its primary command type.
    """
    try:
        # Parse the SQL statement. The root of the AST is the statement type.
        expression_tree = sqlglot.parse_one(sql_string)

        # The expression type is the class of the root node.
        statement_type = type(expression_tree).__name__

        return statement_type
    except sqlglot.errors.ParseError as e:
        return f"SQL parsing error: {e}"


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
            statement_type = get_statement_type(
                context.message.arguments.get("statement", None)
            )
            if (
                "all" in self.sql_allow_list
            ):  # Escape hatch for allowing all statements if user elects to explicitly
                return await call_next(context)
            elif (
                statement_type.lower() in self.sql_disallow_list
            ):  # Allow/Disallow lists should already be lowercase at load
                raise ToolError(
                    f"SQL statement type of {statement_type} is not allowed. Please review sql statement permissions in configuration file."
                )
            elif statement_type.lower() in self.sql_allow_list:
                return await call_next(context)
            else:  # If not in allowed or disallowed, return error. User can always add to list as they find statements not otherwise allowed.
                raise ToolError(
                    f"SQL statement type of {statement_type} is not allowed. Please review sql statement permissions in configuration file."
                )

        # Allow other tools to proceed
        else:
            return await call_next(context)
