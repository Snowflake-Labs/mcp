from typing import Annotated

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
