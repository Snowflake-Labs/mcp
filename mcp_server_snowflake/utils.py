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
from functools import wraps
from typing import Awaitable, Callable, TypeVar, Optional, Union
from typing_extensions import ParamSpec
import json
from pydantic import BaseModel
import ast
from textwrap import dedent

from mcp_server_snowflake.connection import SnowflakeConnectionManager

P = ParamSpec("P")
R = TypeVar("R")


class AnalystResponse(BaseModel):
    """
    Response model for Cortex Analyst API results.

    Represents the structured response from Cortex Analyst containing
    natural language text, generated SQL, and query execution results.

    Attributes
    ----------
    text : str
        Natural language response text from the analyst
    sql : str, optional
        Generated SQL query, by default None
    results : dict | list, optional
        Query execution results if SQL was executed, by default None
    """

    text: str
    sql: Optional[str] = None
    results: Optional[Union[dict, list]] = None


class SearchResponse(BaseModel):
    """
    Response model for Cortex Search API results.

    Represents the structured response from Cortex Search containing
    search results and metadata.

    Attributes
    ----------
    results : str | dict | list
        Search results in various formats depending on query and configuration
    """

    results: Union[str, dict, list]


class CompleteResponse(BaseModel):
    """
    Response model for Cortex Complete API results.

    Represents the response from Cortex Complete for unstructured text generation.

    Attributes
    ----------
    results : str | dict | list
        Generated text or content from the language model
    """

    results: Union[str, dict, list]


class CompleteResponseStructured(BaseModel):
    """
    Response model for structured Cortex Complete API results.

    Represents the response from Cortex Complete when using structured
    JSON output with a defined schema.

    Attributes
    ----------
    results : dict | list
        Structured data conforming to the provided JSON schema
    """

    results: Union[dict, list]


class SnowflakeResponse:
    """
    Response parser and decorator provider for Snowflake Cortex APIs.

    This class provides decorators and parsing methods for handling responses
    from different Snowflake Cortex services. It processes Server-Sent Events (SSE),
    executes SQL queries, and formats responses consistently across all services.

    The class supports three main API types:
    - complete: Language model completion responses
    - analyst: Cortex Analyst responses
    - search: Cortex search responses

    Examples
    --------
    Basic usage with decorator:

    >>> sfse = SnowflakeResponse()
    >>> @sfse.snowflake_response(api="complete")
    ... async def my_complete_function():
    ...     # Function implementation
    ...     pass

    Methods
    -------
    fetch_results(statement, **kwargs)
        Execute SQL statement and fetch results
    parse_analyst_response(response, **kwargs)
        Parse Cortex Analyst API responses
    parse_search_response(response)
        Parse Cortex Search API responses
    parse_llm_response(response, structured=False)
        Parse Cortex Complete API responses
    snowflake_response(api)
        Decorator factory for response parsing
    """

    def fetch_results(self, statement: str, **kwargs):
        """
        Execute SQL statement and fetch all results using Snowflake connector.

        Establishes a connection to Snowflake, executes the provided SQL statement,
        and returns all results using a dictionary cursor for easier data access.

        Parameters
        ----------
        statement : str
            SQL statement to execute
        **kwargs
            Connection parameters including account, user, password, and any additional
            connection parameters (e.g., role, warehouse)

        Returns
        -------
        list[dict]
            List of dictionaries containing query results with column names as keys

        Raises
        ------
        snowflake.connector.errors.Error
            If connection fails or SQL execution encounters an error
        """
        required_params = {
            "account_identifier": kwargs.pop("account"),
            "username": kwargs.pop("user"),
            "pat": kwargs.pop("password"),
        }

        connection_manager = SnowflakeConnectionManager(**required_params)

        # Forward any remaining kwargs to get_connection
        with connection_manager.get_connection(use_dict_cursor=True, **kwargs) as (
            con,
            cur,
        ):
            cur.execute(statement)
            return cur.fetchall()

    def parse_analyst_response(
        self, response: requests.Response | dict, **kwargs
    ) -> str:
        """
        Parse Cortex Analyst API response and execute any generated SQL.

        Processes the analyst response to extract natural language text and
        SQL statements. If SQL is present, executes it against Snowflake
        and includes the results in the parsed response.

        Parameters
        ----------
        response : requests.Response | dict
            Raw response from Cortex Analyst API
        **kwargs
            Connection parameters for SQL execution (account, user, password)

        Returns
        -------
        str
            JSON string containing parsed analyst response with text, SQL, and results
        """
        content = response.json().get("message", {"content": []}).get("content", [])
        res = {}
        for item in content:
            if item.get("type") == "text":
                res["text"] = item.get("text", "")

            elif item.get("type") == "sql":
                res["sql"] = item.get("statement", "")
                if item.get("statement"):
                    res["results"] = self.fetch_results(statement=res["sql"], **kwargs)
        response = AnalystResponse(**res)
        return response.model_dump_json()

    def parse_search_response(self, response: requests.Response | dict) -> str:
        """
        Parse Cortex Search API response into structured format.

        Extracts search results from the API response and formats them
        using the SearchResponse model for consistent output structure.

        Parameters
        ----------
        response : requests.Response | dict
            Raw response from Cortex Search API

        Returns
        -------
        str
            JSON string containing formatted search results
        """
        content = response.json()
        ret = SearchResponse(results=content.get("results", []))
        return ret.model_dump_json()

    def parse_llm_response(
        self, response: requests.models.Response | dict, structured: bool = False
    ) -> str | list | dict:
        """
        Parse Cortex Complete LLM API response from Server-Sent Events.

        Processes streaming SSE response from the Cortex Complete API,
        extracting text content and optionally parsing structured JSON
        responses based on provided schemas.

        Parameters
        ----------
        response : requests.models.Response | dict
            Raw streaming response from Cortex Complete API
        structured : bool, optional
            Whether to parse response as structured JSON, by default False

        Returns
        -------
        str | list | dict
            JSON string containing either plain text or structured data
            depending on the structured parameter

        Raises
        ------
        json.JSONDecodeError
            If SSE event data cannot be parsed as JSON
        SyntaxError
            If structured response cannot be parsed as valid Python literal
        """
        sse_events = dict(events=[])
        content_text = []
        for event in response.iter_lines():
            if not event.strip():
                continue

            decoded = event.decode("utf-8")
            if not decoded.startswith("data: "):
                continue

            event_row = decoded.removeprefix("data: ")
            try:
                sse_events["events"].append(json.loads(event_row))
            except json.JSONDecodeError as e:
                raise e

        for event in sse_events["events"]:
            delta = event.get("choices")[0].get("delta", {})
            if delta.get("type") == "text":
                if content := delta.get("content"):
                    content_text.append(content)

        if structured:
            ret = CompleteResponseStructured(
                results=ast.literal_eval("".join(content_text))
            )
        else:
            ret = CompleteResponse(results="".join(content_text))

        return ret.model_dump_json()

    def snowflake_response(
        self,
        api: str,
    ) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
        """
        Decorator factory for consistent response parsing across Cortex APIs.

        Creates a decorator that automatically parses responses from different
        Cortex API endpoints based on the specified API type. The decorator
        handles the raw API response and returns formatted, structured data.

        Parameters
        ----------
        api : str
            API type to handle. Must be one of: "complete", "analyst", "search"

        Returns
        -------
        Callable
            Decorator function that wraps async functions to provide response parsing

        Examples
        --------
        Decorating a function for Cortex Complete API:

        >>> @sfse.snowflake_response(api="complete")
        ... async def my_completion_function(prompt, **kwargs):
        ...     # Make API call
        ...     return raw_response
        """

        def cortex_wrapper(
            func: Callable[P, Awaitable[R]],
        ) -> Callable[P, Awaitable[R]]:
            @wraps(func)
            async def response_parsers(*args: P.args, **kwargs: P.kwargs) -> R:
                raw_sse = await func(*args, **kwargs)
                conn_kwargs = dict(
                    account=kwargs.get("account_identifier", ""),
                    user=kwargs.get("username", ""),
                    password=kwargs.get("PAT", ""),
                )
                match api:
                    case "complete":
                        structured = kwargs.get("response_format", {})
                        parsed = self.parse_llm_response(
                            response=raw_sse, structured=bool(structured)
                        )
                    case "analyst":
                        parsed = self.parse_analyst_response(
                            response=raw_sse, **conn_kwargs
                        )
                    case "search":
                        parsed = self.parse_search_response(response=raw_sse)
                return parsed

            return response_parsers

        return cortex_wrapper


class SnowflakeException(Exception):
    """
    Custom exception class for Snowflake API errors.

    Provides enhanced error handling for Snowflake Cortex API operations
    with specific error messages based on HTTP status codes and error types.

    Parameters
    ----------
    tool : str
        Name of the Cortex tool that generated the error
    message : str
        Raw error message from the API
    status_code : int, optional
        HTTP status code from the API response, by default None

    Attributes
    ----------
    tool : str
        The Cortex service that generated the error
    message : str
        Original error message from the API
    status_code : int
        HTTP status code associated with the error

    Methods
    -------
    __str__()
        Returns formatted error message based on status code and content

    Examples
    --------
    Raising a Snowflake exception:

    >>> raise SnowflakeException(
    ...     tool="Cortex Complete",
    ...     message="Model not found",
    ...     status_code=400
    ... )
    """

    def __init__(self, tool: str, message, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
        self.tool = tool

    def __str__(self):
        """
        Format error message based on status code and error content.

        Provides user-friendly error messages with specific guidance
        based on common HTTP status codes and error patterns.

        Returns
        -------
        str
            Formatted error message with tool name, description, and guidance

        Notes
        -----
        Status code handling:
        - 400: Bad request errors with model validation
        - 401: Authorization/authentication errors
        - Other codes: Generic error with status code
        """
        if self.status_code == 400:
            if "unknown model" in self.message:
                return f"{self.tool} Error: Selected model not available or invalid.\n\nError Message: {self.message} "
            else:
                return f"{self.tool} Error: The resource cannot be found.\n\nError Message: {self.message} "

        elif self.status_code == 401:
            return f"{self.tool} Error: An authorization error occurred.\n\nError Message: {self.message} "
        else:
            return f"{self.tool} Error: An error has occurred.\n\nError Message: {self.message} \n Code: {self.status_code}"


class MissingArgumentsException(Exception):
    def __init__(self, missing: list):
        self.missing = missing
        super().__init__(missing)

    def __str__(self):
        missing_str = "\n\t\t".join([f"--{i}" for i in self.missing])
        message = f"""
        -----------------------------------------------------------------------------------
        Required arguments missing:
        \t{missing_str}
        These values must be specified as command-line arguments or environment variables
        -----------------------------------------------------------------------------------"""

        return dedent(message)
