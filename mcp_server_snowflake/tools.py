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
import requests
from typing import Optional
from collections import OrderedDict

import mcp.types as types
from bs4 import BeautifulSoup

from mcp_server_snowflake.utils import SnowflakeResponse, SnowflakeException
from mcp_server_snowflake.connection import SnowflakeConnectionManager


sfse = SnowflakeResponse()  # For parsing Snowflake responses


# Cortex Search Service
@sfse.snowflake_response(api="search")
async def query_cortex_search(
    account_identifier: str,
    service_name: str,
    database_name: str,
    schema_name: str,
    query: str,
    PAT: str,
    columns: Optional[list[str]] = None,
    filter_query: Optional[dict] = {},
) -> dict:
    """
    Query a Cortex Search Service using the REST API.

    Performs semantic search against a configured Cortex Search service using
    Snowflake's REST API. Supports filtering and column selection for refined
    search results.

    Parameters
    ----------
    account_identifier : str
        Snowflake account identifier
    service_name : str
        Name of the Cortex Search Service
    database_name : str
        Target database containing the search service
    schema_name : str
        Target schema containing the search service
    query : str
        The search query string to submit to Cortex Search
    PAT : str
        Programmatic Access Token for authentication
    columns : list[str], optional
        List of columns to return for each relevant result, by default None
    filter_query : dict, optional
        Filter query to apply to search results, by default {}

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
    base_url = f"https://{account_identifier}.snowflakecomputing.com/api/v2/databases/{database_name}/schemas/{schema_name}/cortex-search-services/{service_name}:query"

    headers = {
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
        "Authorization": f"Bearer {PAT}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    payload = {
        "query": query,
        "filter": filter_query,
    }

    if isinstance(columns, list) and len(columns) > 0:
        payload["columns"] = columns

    response = requests.post(base_url, headers=headers, json=payload)

    if response.status_code == 200:
        return response
    else:
        raise SnowflakeException(
            tool="Cortex Search",
            status_code=response.status_code,
            message=response.text,
        )


def get_cortex_search_tool_types(search_services: list[dict]) -> list[types.Tool]:
    """
    Generate MCP tool definitions for configured search services.

    Creates tool specifications for each configured Cortex Search service,
    including input schemas with query parameters, column selection, and
    filtering options.

    Parameters
    ----------
    search_services : list[dict]
        List of search service configuration dictionaries containing
        service_name, description, and other service metadata

    Returns
    -------
    list[types.Tool]
        List of MCP Tool objects with complete input schemas for search operations

    Notes
    -----
    The generated tools support advanced filtering with operators:
    - @eq: Equality matching for text/numeric values
    - @contains: Array contains matching
    - @gte/@lte: Numeric/date range filtering
    - @and/@or/@not: Logical operators for complex filters
    """

    return [
        types.Tool(
            name=x.get("service_name"),
            description=x.get("description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User query to search in search service",
                    },
                    "columns": {
                        "type": "array",
                        "description": "Optional list of columns to return for each relevant result in the response.",
                    },
                    "filter_query": {
                        "type": "object",
                        "description": """Cortex Search supports filtering on the ATTRIBUTES columns specified in the CREATE CORTEX SEARCH SERVICE command.

Cortex Search supports four matching operators:

1. TEXT or NUMERIC equality: @eq
2. ARRAY contains: @contains
3. NUMERIC or DATE/TIMESTAMP greater than or equal to: @gte
4. NUMERIC or DATE/TIMESTAMP less than or equal to: @lte

These matching operators can be composed with various logical operators:

- @and
- @or
- @not

The following usage notes apply:

Matching against NaN ('not a number') values in the source query are handled as
described in Special values. Fixed-point numeric values with more than 19 digits (not
including leading zeroes) do not work with @eq, @gte, or @lte and will not be returned
by these operators (although they could still be returned by the overall query with the
use of @not).

TIMESTAMP and DATE filters accept values of the form: YYYY-MM-DD and, for timezone
aware dates: YYYY-MM-DD+HH:MM. If the timezone offset is not specified, the date is
interpreted in UTC.

These operators can be combined into a single filter object.

Example:
Filtering on rows where NUMERIC column numeric_col is between 10.5 and 12.5 (inclusive):

{ "@and": [
  { "@gte": { "numeric_col": 10.5 } },
  { "@lte": { "numeric_col": 12.5 } }
]}""",
                    },
                },
                "required": ["query"],
            },
        )
        for x in search_services
    ]


# Cortex Complete Service
@sfse.snowflake_response(api="complete")
async def cortex_complete(
    prompt: str,
    model: str,
    account_identifier: str,
    PAT: str,
    response_format: Optional[dict] = None,
) -> dict:
    """
    Generate text completions using Snowflake Cortex Complete API.

    Sends a chat completion request to Snowflake's Cortex Complete service
    using the specified language model. Supports structured JSON responses
    when a response format is provided.

    Parameters
    ----------
    prompt : str
        User prompt message to send to the language model
    model : str
        Snowflake Cortex LLM model name to use for completion
    account_identifier : str
        Snowflake account identifier
    PAT : str
        Programmatic Access Token for authentication
    response_format : dict, optional
        JSON schema for structured response format, by default None

    Returns
    -------
    dict
        JSON response from the Cortex Complete API containing the generated text

    Raises
    ------
    SnowflakeException
        If the API request fails or returns an error status code

    Notes
    -----
    The temperature is set to 0.0 for deterministic responses. The response_format
    parameter allows for structured JSON outputs following a provided schema.
    """
    base_url = f"https://{account_identifier}.snowflakecomputing.com/api/v2/cortex/inference:complete"

    headers = {
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
        "Authorization": f"Bearer {PAT}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }

    # Add response_format to payload if provided
    if response_format is not None:
        payload["response_format"] = response_format

    response = requests.post(base_url, headers=headers, json=payload)

    if response.status_code == 200:
        return response
    else:
        raise SnowflakeException(
            tool="Cortex Complete",
            status_code=response.status_code,
            message=response.text,
        )


def get_cortex_complete_tool_type():
    """
    Generate MCP tool definition for Cortex Complete service.

    Creates a tool specification for the Cortex Complete LLM service with
    support for prompt input, model selection, and structured JSON responses.

    Returns
    -------
    types.Tool
        MCP Tool object with complete input schema for LLM completion operations

    Notes
    -----
    The tool supports optional structured JSON responses through the response_format
    parameter, which accepts a JSON schema defining the expected output structure.
    """
    return types.Tool(
        name="cortex-complete",
        description="""Simple LLM chat completion API using Cortex Complete""",
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "User prompt message to send to the LLM",
                },
                "model": {
                    "type": "string",
                    "description": "Optional Snowflake Cortex LLM Model name to use.",
                },
                "response_format": {
                    "type": "object",
                    "description": """Optional JSON response format to use for the LLM response.
                            Type must be 'json' and schema must be a valid JSON schema.
                            Example:
                            {
                                "type": "json",
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                    "people": {
                                        "type": "array",
                                        "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {
                                            "type": "string"
                                            },
                                            "age": {
                                            "type": "number"
                                            }
                                        },
                                        "required": ["name", "age"]
                                        }
                                    }
                                    },
                                    "required": ["people"]
                                }
                            }
                            """,
                },
            },
            "required": ["prompt"],
        },
    )


def get_region(
    account_identifier: str,
    username: str,
    PAT: str,
) -> str:
    """
    Retrieve the current region of the Snowflake account.

    Executes a SQL query to determine the region where the Snowflake
    account is located using the CURRENT_REGION() function.

    Parameters
    ----------
    account_identifier : str
        Snowflake account identifier
    username : str
        Snowflake username for authentication
    PAT : str
        Programmatic Access Token for authentication

    Returns
    -------
    str
        The region name where the Snowflake account is located

    Raises
    ------
    snowflake.connector.errors.Error
        If connection to Snowflake fails or query execution fails
    """

    statement = "SELECT CURRENT_REGION()"
    connection_manager = SnowflakeConnectionManager(
        account_identifier=account_identifier, username=username, pat=PAT
    )

    with connection_manager.get_connection(use_dict_cursor=True) as (con, cur):
        cur.execute(statement)
        return cur.fetchone().get("CURRENT_REGION()")


async def get_cortex_models(
    account_identifier: str,
    username: str,
    PAT: str,
    url: str = "https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-llm-rest-api#model-availability",
) -> str | dict[str, list[dict[str, str]] | str]:
    """
    Retrieve available Cortex Complete model information from Snowflake documentation.

    Scrapes the Snowflake documentation to get current model availability
    information specifically for the REST API and combines it with the account's region
    information.

    Parameters
    ----------
    account_identifier : str
        Snowflake account identifier
    username : str
        Snowflake username for authentication
    PAT : str
        Programmatic Access Token for authentication
    url : str, optional
        URL to Snowflake Cortex model documentation, by default official docs URL

    Returns
    -------
    str | dict[str, list[dict[str, str]] | str]
        Either an error message string or a dictionary containing:
        - 'current_region': The account's region
        - 'model_availability': List of available models with their details
    """

    # Send HTTP request
    response = requests.get(url)
    if response.status_code != 200:
        return f"Failed to retrieve the page {url} with {response.status_code}"

    # Parse HTML
    soup = BeautifulSoup(response.content, "html.parser")

    # Find the model availability section (could be a table or other format)
    section = soup.find(id="model-availability") or soup.find(
        string="Model availability"
    ).find_parent("section")

    if not section:
        return (
            f"Failed to retrieve model availability from the docs. Please visit {url}."
        )

    else:
        # Process the specific section if found
        tables = section.find_all("table")
        if tables:
            model_data = []
            table = tables[0]

            # Get headers
            headers = []
            for th in table.find_all("th"):
                headers.append(th.text.strip())

            # Extract rows
            for row in table.find_all("tr")[1:]:  # Skip header row
                cells = row.find_all(["td", "th"])
                if cells:
                    row_data = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            row_data[headers[i]] = cell.text.strip()
                    model_data.append(row_data)

            return OrderedDict(
                [
                    ("current_region", get_region(account_identifier, username, PAT)),
                    ("model_availability", model_data),
                ]
            )
        else:
            return f"No model availability table found at {url}."


def get_cortex_models_tool_type():
    """
    Generate MCP tool definition for retrieving Cortex model information.

    Creates a tool specification for fetching available Cortex Complete
    models and their regional availability.

    Returns
    -------
    types.Tool
        MCP Tool object for retrieving model cards and availability information
    """
    return types.Tool(
        name="get-model-cards",
        description="""Retrieves available model cards in Snowflake Cortex REST API""",
        inputSchema={"type": "object", "properties": {}, "required": []},
    )


# Cortex Analyst Service
@sfse.snowflake_response(api="analyst")
async def query_cortex_analyst(
    account_identifier: str,
    semantic_model: str,
    query: str,
    username: str,
    PAT: str,
) -> dict:
    """
    Query Snowflake Cortex Analyst service for natural language to SQL conversion.

    Sends a natural language query to the Cortex Analyst service, which
    interprets the query against a semantic model and generates appropriate
    SQL responses with explanations.

    Parameters
    ----------
    account_identifier : str
        Snowflake account identifier
    semantic_model : str
        Fully qualified path to YAML semantic file or Snowflake Semantic View.
        Examples:
        - "@my_db.my_schema.my_stage/my_semantic_model.yaml"
        - "MY_DB.MY_SCH.MY_SEMANTIC_VIEW"
    query : str
        Natural language query string to submit to Cortex Analyst
    username : str
        Snowflake username for authentication
    PAT : str
        Programmatic Access Token for authentication

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
    base_url = f"https://{account_identifier}.snowflakecomputing.com/api/v2/cortex/analyst/message"

    headers = {
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
        "Authorization": f"Bearer {PAT}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    if semantic_model.startswith("@") and semantic_model.endswith(".yaml"):
        semantic_type = "semantic_model_file"
    else:
        semantic_type = "semantic_model_view"

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

    response = requests.post(base_url, headers=headers, json=payload)

    if response.status_code == 200:
        return response

    else:
        raise SnowflakeException(
            tool="Cortex Analyst",
            status_code=response.status_code,
            message=response.text,
        )


def get_cortex_analyst_tool_types(analyst_services: list[dict]) -> list[types.Tool]:
    """
    Generate MCP tool definitions for configured Cortex Analyst services.

    Creates tool specifications for each configured Cortex Analyst service,
    enabling natural language querying against semantic models.

    Parameters
    ----------
    analyst_services : list[dict]
        List of analyst service configuration dictionaries containing
        service_name, description, and semantic model references

    Returns
    -------
    list[types.Tool]
        List of MCP Tool objects with input schemas for natural language queries
    """

    return [
        types.Tool(
            name=x.get("service_name"),
            description=x.get("description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A rephrased natural language prompt from the user.",
                    },
                },
                "required": ["query"],
            },
        )
        for x in analyst_services
    ]
