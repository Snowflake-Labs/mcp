# Copyright 2025 Snowflake Inc.
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Annotated, Optional

import requests
from fastmcp import FastMCP
from pydantic import Field

from mcp_server_snowflake.cortex_services.prompts import (
    cortex_search_filter_description,
    get_cortex_agent_description,
    get_cortex_analyst_description,
    get_cortex_search_description,
)
from mcp_server_snowflake.environment import construct_snowflake_post
from mcp_server_snowflake.utils import SnowflakeException, SnowflakeResponse

sfse = SnowflakeResponse()


@sfse.snowflake_response(api="agent")
async def query_cortex_agent(
    snowflake_service,
    service_name: str,
    database_name: str,
    schema_name: str,
    query: str,
) -> dict:
    """
    Query a Cortex Agent Service using the REST API.

    Sends query to a configured Cortex Agent service using
    Snowflake's REST API. Tool choice is auto based on pre-configured Agent object.

    Parameters
    ----------
    snowflake_service
    service_name : str
        Name of the Cortex Agent Service
    database_name : str
        Target database containing the agent service
    schema_name : str
        Target schema containing the agent service
    query : str
        The user query string to submit to Cortex Agent

    Returns
    -------
    dict
        JSON response from the Cortex Agent API

    Raises
    ------
    SnowflakeException
        If the API request fails or returns an error status code

    References
    ----------
    Snowflake Cortex Agent REST API (for Agent Objects):
    https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api
    """
    host, headers = construct_snowflake_post(
        service=snowflake_service,
        api_path=f"/api/v2/databases/{database_name}/schemas/{schema_name}/agents/{service_name}:run",
    )

    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": query}]}],
        "tool_choice": {"type": "auto"},
        "stream": False,  # Ignored by Agent API
    }

    response = requests.post(host, headers=headers, json=payload, stream=True)
    try:
        response.raise_for_status()
        return response
    except Exception:
        raise SnowflakeException(
            tool="Cortex Agent",
            status_code=response.status_code,
            message=response.text,
        )


@sfse.snowflake_response(api="search")
async def query_cortex_search(
    snowflake_service,
    service_name: str,
    database_name: str,
    schema_name: str,
    query: str,
    columns: Optional[list[str]] = None,
    filter_query: Optional[dict] = {},
    limit: Optional[int] = 10,
) -> dict:
    """
    Query a Cortex Search Service using the REST API.

    Performs semantic search against a configured Cortex Search service using
    Snowflake's REST API. Supports filtering and column selection for refined
    search results.

    Parameters
    ----------
    snowflake_service
    service_name : str
        Name of the Cortex Search Service
    database_name : str
        Target database containing the search service
    schema_name : str
        Target schema containing the search service
    query : str
        The search query string to submit to Cortex Search
    columns : list[str], optional
        List of columns to return for each relevant result, by default None
    filter_query : dict, optional
        Filter query to apply to search results, by default {}
    limit : int, optional
        Limit on the number of results to return, by default 10

    Returns
    -------
    dict
        JSON response from the Cortex Search API containing search results

    Raises
    ------
    SnowflakeException
        If the API request fails or returns an error status code

    References
    ----------
    Snowflake Cortex Search REST API:
    https://docs.snowflake.com/developer-guide/snowflake-rest-api/reference/cortex-search-service
    """
    host, headers = construct_snowflake_post(
        service=snowflake_service,
        api_path=f"/api/v2/databases/{database_name}/schemas/{schema_name}/cortex-search-services/{service_name}:query",
    )

    if filter_query is None:
        filter_query = {}

    payload = {
        "query": query,
        "filter": filter_query,
        "limit": limit,
    }

    if isinstance(columns, list) and len(columns) > 0:
        payload["columns"] = columns

    response = requests.post(host, headers=headers, json=payload)

    if response.status_code == 200:
        return response

    else:
        raise SnowflakeException(
            tool="Cortex Search",
            status_code=response.status_code,
            message=response.text,
        )


@sfse.snowflake_response(api="analyst")
async def query_cortex_analyst(
    snowflake_service,
    semantic_model: str,
    query: str,
) -> dict:
    """
    Query Snowflake Cortex Analyst service for natural language to SQL conversion.

    Sends a natural language query to the Cortex Analyst service, which
    interprets the query against a semantic model and generates appropriate
    SQL responses with explanations.

    Parameters
    ----------
    snowflake_service
    semantic_model : str
        Fully qualified path to YAML semantic file or Snowflake Semantic View.
        Examples:
        - "@my_db.my_schema.my_stage/my_semantic_model.yaml"
        - "MY_DB.MY_SCH.MY_SEMANTIC_VIEW"
    query : str
        Natural language query string to submit to Cortex Analyst

    Returns
    -------
    dict
        JSON response from the Cortex Analyst API containing generated SQL,
        explanations, and query results

    Raises
    ------
    SnowflakeException
        If the API request fails or returns an error status code

    Notes
    -----
    The function automatically detects whether the semantic_model parameter
    refers to a YAML file (starts with @ and ends with .yaml) or a semantic view.
    Currently configured for non-streaming responses.
    """
    host, headers = construct_snowflake_post(
        service=snowflake_service,
        api_path="/api/v2/cortex/analyst/message",
    )

    if semantic_model.startswith("@") and semantic_model.endswith(".yaml"):
        semantic_type = "semantic_model_file"
    else:
        semantic_type = "semantic_view"

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": query,
                    }
                ],
            }
        ],
        semantic_type: semantic_model,
        "stream": False,
    }

    response = requests.post(host, headers=headers, json=payload)

    if response.status_code == 200:
        return response

    else:
        raise SnowflakeException(
            tool="Cortex Analyst",
            status_code=response.status_code,
            message=response.text,
        )


def initialize_cortex_agent_tool(server: FastMCP, snowflake_service):
    if snowflake_service.agent_services:

        @server.tool(
            name="cortex_agent",
            description=get_cortex_agent_description(snowflake_service.agent_services),
        )
        def run_cortex_agent_tool(
            service_name: Annotated[
                str,
                Field(description="Name of the Cortex Agent Service"),
            ],
            database_name: Annotated[
                str,
                Field(description="Target database containing the agent service"),
            ],
            schema_name: Annotated[
                str,
                Field(description="Target schema containing the agent service"),
            ],
            query: Annotated[
                str,
                Field(description="User query to submit to Cortex Agent"),
            ],
        ):
            return query_cortex_agent(
                snowflake_service=snowflake_service,
                service_name=service_name,
                database_name=database_name,
                schema_name=schema_name,
                query=query,
            )


def initialize_cortex_search_tool(server: FastMCP, snowflake_service):
    if snowflake_service.search_services:

        @server.tool(
            name="cortex_search",
            description=get_cortex_search_description(
                snowflake_service.search_services
            ),
        )
        def run_cortex_search_tool(
            service_name: Annotated[
                str,
                Field(description="Name of the Cortex Search Service"),
            ],
            database_name: Annotated[
                str,
                Field(description="Target database containing the search service"),
            ],
            schema_name: Annotated[
                str,
                Field(description="Target schema containing the search service"),
            ],
            query: Annotated[
                str,
                Field(description="User query to search in search service"),
            ],
            columns: Annotated[
                list[str],
                Field(
                    description="Optional list of columns to return for each relevant result in the response"
                ),
            ] = [],
            filter_query: Annotated[
                dict,
                Field(description=cortex_search_filter_description),
            ] = {},
            limit: Annotated[
                int,
                Field(description="Optional limit on the number of results to return"),
            ] = 10,
        ):
            return query_cortex_search(
                snowflake_service=snowflake_service,
                service_name=service_name,
                database_name=database_name,
                schema_name=schema_name,
                query=query,
                columns=columns,
                filter_query=filter_query,
                limit=limit,
            )


def initialize_cortex_analyst_tool(server: FastMCP, snowflake_service):
    if snowflake_service.analyst_services:

        @server.tool(
            name="cortex_analyst",
            description=get_cortex_analyst_description(
                snowflake_service.analyst_services
            ),
        )
        def run_cortex_analyst_tool(
            # service_name isn't required for Cortex Analyst
            # adding it so specific service selected can be identified in client
            service_name: Annotated[
                str,
                Field(description="Name of the Cortex Analyst Service"),
            ],
            semantic_model: Annotated[
                str,
                Field(
                    description="Fully qualified path to YAML semantic file or Snowflake Semantic View"
                ),
            ],
            query: Annotated[
                str,
                Field(description="Natural language query to submit to Cortex Analyst"),
            ],
        ):
            return query_cortex_analyst(
                snowflake_service=snowflake_service,
                semantic_model=semantic_model,
                query=query,
            )
