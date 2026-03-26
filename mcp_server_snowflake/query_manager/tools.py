from typing import Annotated

import sqlglot
from fastmcp import FastMCP
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
        expression_tree = sqlglot.parse_one(sql_string, dialect="snowflake")

        # The expression type is the class of the root node.
        statement_type = type(expression_tree).__name__

        return statement_type
    except (
        sqlglot.errors.ParseError
    ):  # We will map this back to user's Unknown statement type setting
        return "Unknown"


def validate_sql_type(
    sql_string: str, sql_allow_list: list[str], sql_disallow_list: list[str]
) -> tuple[str, bool]:
    """
    Validates a SQL statement type against a list of allowed and disallowed statement types.
    """
    statement_type = get_statement_type(sql_string)
    if (
        "all" in sql_allow_list
    ):  # Escape hatch for allowing all statements if user elects to explicitly
        valid = True
    elif (
        statement_type.lower() in sql_disallow_list
    ):  # Allow/Disallow lists should already be lowercase at load
        valid = False
    elif statement_type.lower() in sql_allow_list:
        valid = True
    # There may be a new unmapped type that is not in the allow/disallow lists. If the user has set Unknown to True, allow it.
    elif "unknown" in sql_allow_list:
        valid = True

    # User has not added any permissions, so we default to disallowing all statements
    elif len(sql_allow_list) == 0 and len(sql_disallow_list) == 0:
        valid = False

    else:  # If not in allowed or disallowed and unknown in disallow or omitted, return error. User can always add to list as they find statements not otherwise allowed.
        valid = False

    return (statement_type, valid)
