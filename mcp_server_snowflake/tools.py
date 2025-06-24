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
from collections import OrderedDict
from typing import Annotated, Optional

import requests
from bs4 import BeautifulSoup
from pydantic import Field

import mcp_server_snowflake.prompts as prompts
from mcp_server_snowflake.connection import SnowflakeConnectionManager
from mcp_server_snowflake.utils import SnowflakeException, SnowflakeResponse

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

    if filter_query is None:
        filter_query = {}

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


def create_search_wrapper(**kwargs):
    async def search_wrapper(
        query: Annotated[
            str, Field(description="User query to search in search service")
        ],
        columns: Annotated[
            list[str],
            Field(
                description="Optional list of columns to return for each relevant result in the response"
            ),
        ] = [],
        filter_query: Annotated[
            dict, Field(description=prompts.cortex_search_filter_description)
        ] = {},
    ):
        """
        Search using Cortex Search Service.

        Parameters
        ----------
        query : str
            The search query string to submit to Cortex Search
        columns : list[str], optional
            List of columns to return for each relevant result, by default []
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
        """

        if kwargs.get("snowflake_service") and kwargs.get("service_details"):
            snowflake_service = kwargs.get("snowflake_service")
            service_details = kwargs.get("service_details")

            return await query_cortex_search(
                query=query,
                columns=columns,
                filter_query=filter_query,
                account_identifier=snowflake_service.account_identifier,
                service_name=service_details.get("service_name"),
                database_name=service_details.get("database_name"),
                schema_name=service_details.get("schema_name"),
                PAT=snowflake_service.pat,
            )

    return search_wrapper


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


def create_chat_complete_wrapper(**kwargs):
    async def chat_complete_wrapper(
        prompt: Annotated[
            str, Field(description="User prompt message to send to the language model")
        ],
        model: Annotated[
            str,
            Field(
                description="Optional Snowflake Cortex LLM model name to use for completion"
            ),
        ] = "",
        response_format: Optional[
            Annotated[
                dict,
                Field(description=prompts.cortex_complete_response_format_description),
            ]
        ] = {},
    ):
        """
        Generate text completions using Snowflake Cortex Complete API.

        Sends a chat completion request to Snowflake's Cortex Complete service
        using the specified language model. Supports structured JSON responses
        when a response format is provided.

        Parameters
        ----------
        prompt : str
            User prompt message to send to the language model
        model : str, optional
            Snowflake Cortex LLM model name to use for completion, by default ""
        response_format : dict, optional
            JSON schema for structured response format, by default {}

        Returns
        -------
        dict
            JSON response from the Cortex Complete API containing the generated text

        Raises
        ------
        SnowflakeException
            If the API request fails or returns an error status code
        """

        if kwargs.get("snowflake_service"):
            snowflake_service = kwargs.get("snowflake_service")

            # Use default model if none provided
            if not model:
                model = (
                    getattr(snowflake_service, "default_complete_model")
                    or "snowflake-llama-3.3-70b"
                )

            return await cortex_complete(
                prompt=prompt,
                model=model,
                response_format=response_format,
                account_identifier=snowflake_service.account_identifier,
                PAT=snowflake_service.pat,
            )

    return chat_complete_wrapper


# Get model availability
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


def create_get_cortex_models_wrapper(**kwargs):
    async def get_cortex_models_wrapper():
        """
        Retrieve available Cortex Complete models and their regional availability.

        This async wrapper is designed to be used as a tool in the MCP server, allowing
        clients to fetch the list of available Snowflake Cortex Complete models and their
        availability in the current Snowflake region.

        Parameters
        ----------
        None

        Returns
        -------
        OrderedDict
            An ordered dictionary containing:
                - current_region: The current Snowflake region for the account, by default None
                - model_availability: A list of dictionaries, each representing a model and its availability, by default None

        Raises
        ------
        Exception
            If the underlying get_cortex_models function fails to retrieve or parse the model information

        """
        if kwargs.get("snowflake_service"):
            snowflake_service = kwargs.get("snowflake_service")

            return await get_cortex_models(
                account_identifier=snowflake_service.account_identifier,
                username=snowflake_service.username,
                PAT=snowflake_service.pat,
            )

    return get_cortex_models_wrapper


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
        Snowflake username for authentication.
        This is used in the decorator to execute the query via SnowflakeConnectionManager.
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

    response = requests.post(base_url, headers=headers, json=payload)

    if response.status_code == 200:
        return response

    else:
        raise SnowflakeException(
            tool="Cortex Analyst",
            status_code=response.status_code,
            message=response.text,
        )


def create_cortex_analyst_wrapper(**kwargs):
    async def cortex_analyst_wrapper(
        query: Annotated[
            str,
            Field(
                description="Rephrased natural language query to submit to Cortex Analyst"
            ),
        ],
    ):
        """
        Query Snowflake Cortex Analyst service for natural language to SQL conversion.

        Parameters
        ----------
        query : str
            The natural language query string to submit to Cortex Analyst

        Returns
        -------
        dict
            JSON response from the Cortex Analyst API containing the generated SQL and related information

        Raises
        ------
        SnowflakeException
            If the API request fails or returns an error status code
        """

        if kwargs.get("snowflake_service") and kwargs.get("service_details"):
            snowflake_service = kwargs.get("snowflake_service")
            service_details = kwargs.get("service_details")

            return await query_cortex_analyst(
                account_identifier=snowflake_service.account_identifier,
                semantic_model=service_details.get("semantic_model"),
                query=query,
                username=snowflake_service.username,
                PAT=snowflake_service.pat,
            )

    return cortex_analyst_wrapper
