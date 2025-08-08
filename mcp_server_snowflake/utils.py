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
import json
import logging
import os
import re
from functools import wraps
from textwrap import dedent
from typing import Awaitable, Callable, Optional, TypeVar, Union

import requests
import yaml
from pydantic import BaseModel
from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def sanitize_tool_name(service_name: str) -> str:
    """Sanitize service name to create a valid Python identifier for MCP tool name."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", service_name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"service_{sanitized}"
    return sanitized


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


class SnowflakeResponse:
    """
    Response parser and decorator provider for Snowflake Cortex APIs.

    This class provides decorators and parsing methods for handling responses
    from different Snowflake Cortex services. It processes Server-Sent Events (SSE),
    executes SQL queries, and formats responses consistently across all services.

    The class supports three main API types:
    - analyst: Cortex Analyst responses
    - search: Cortex search responses

    Examples
    --------
    Basic usage with decorator:

    >>> sfse = SnowflakeResponse()
    >>> @sfse.snowflake_response(api="analyst")
    ... async def my_analyst_function():
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
    snowflake_response(api)
        Decorator factory for response parsing
    """

    def fetch_results(self, statement: str, service, **kwargs):
        """
        Execute SQL statement and fetch all results using Snowflake connector.

        Establishes a connection to Snowflake, executes the provided SQL statement,
        and returns all results using a dictionary cursor for easier data access.

        Parameters
        ----------
        statement : str
            SQL statement to execute
        service : SnowflakeService
            The Snowflake service instance to use for connection
        **kwargs
            Additional connection parameters (e.g., role, warehouse)

        Returns
        -------
        list[dict]
            List of dictionaries containing query results with column names as keys

        Raises
        ------
        snowflake.connector.errors.Error
            If connection fails or SQL execution encounters an error
        """
        # Forward any remaining kwargs to get_connection
        with service.get_connection(
            use_dict_cursor=True, session_parameters=service.get_query_tag_param()
        ) as (
            con,
            cur,
        ):
            cur.execute(statement)
            return cur.fetchall()

    def parse_analyst_response(
        self, response: requests.Response | dict, service, **kwargs
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
        service : SnowflakeService
            The Snowflake service instance to use for connection
        **kwargs
            Additional connection parameters for SQL execution

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
                    res["results"] = self.fetch_results(
                        statement=res["sql"], service=service, **kwargs
                    )
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

    def snowflake_response(
        self,
        api: str,
    ) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
        """
        Create decorator factory for consistent response parsing across Cortex APIs.

        Creates a decorator that automatically parses responses from different
        Cortex API endpoints based on the specified API type. The decorator
        handles the raw API response and returns formatted, structured data.

        Parameters
        ----------
        api : str
            API type to handle. Must be one of: "analyst", "search"

        Returns
        -------
        Callable
            Decorator function that wraps async functions to provide response parsing

        Examples
        --------
        Decorating a function for Cortex Analyst:

        >>> @sfse.snowflake_response(api="analyst")
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
                snowflake_service = kwargs.get("snowflake_service")
                match api:
                    case "analyst":
                        parsed = self.parse_analyst_response(
                            response=raw_sse, service=snowflake_service
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
    ...     tool="Cortex Analyst", message="Model not found", status_code=400
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
        missing_str = "\n\t\t".join([f"{i}" for i in self.missing])
        message = f"""
        -----------------------------------------------------------------------------------
        Required arguments missing:
        \t{missing_str}
        These values must be specified as command-line arguments or environment variables
        -----------------------------------------------------------------------------------"""

        return dedent(message)


def cleanup_snowflake_service(snowflake_service):
    """
    Clean up Snowflake service resources.

    Parameters
    ----------
    snowflake_service : SnowflakeService
        The service instance to clean up
    """
    # This if for the case if the service fails to initialize it will not need to cleanup.
    if not snowflake_service:
        return

    try:
        if hasattr(snowflake_service, "connection") and snowflake_service.connection:
            logger.info("Closing Snowflake connection...")
            snowflake_service.connection.close()
    except Exception as e:
        logger.error(f"Error closing Snowflake connection: {e}")


async def load_tools_config_resource(file_path: str) -> str:
    """
    Load tools configuration from YAML file as JSON string.

    Parameters
    ----------
    file_path : str
        Path to the YAML configuration file

    Returns
    -------
    str
        JSON string representation of the configuration

    Raises
    ------
    FileNotFoundError
        If the configuration file cannot be found
    yaml.YAMLError
        If the YAML file is malformed
    """
    with open(file_path, "r") as file:
        tools_config = yaml.safe_load(file)

    return json.dumps(tools_config)


def get_login_params() -> dict:
    """
    Get Snowflake login parameters configuration.

    Returns a dictionary mapping Snowflake connection parameter names to their
    corresponding command line argument names and default values from environment
    variables.

    Returns
    -------
    dict
        Dictionary with structure {param_name: [arg_names, default_value]}
        where arg_names are the command line argument flags and default_value
        is pulled from environment variables

    Examples
    --------
    >>> params = get_login_params()
    >>> params["account"]
    ['--account', '--account-identifier', os.getenv("SNOWFLAKE_ACCOUNT"), "Your account identifier."]
    """
    # Dict of login params supported by snowflake connector api to establish connection
    # {Key value name : [argparse argument name(s), default value, help]}
    # Each argument can have 1-2 flag values. All arguments must have a default value and help.
    login_params = {  # TODO: Add help for each argument
        "account": [
            "--account",
            "--account-identifier",
            os.getenv("SNOWFLAKE_ACCOUNT"),
            "Your account identifier. The account identifier does not include the snowflakecomputing.com suffix.",
        ],
        "host": ["--host", os.getenv("SNOWFLAKE_HOST"), "Host name."],
        "user": [
            "--user",
            "--username",
            os.getenv("SNOWFLAKE_USER"),
            "Login name for the user.",
        ],
        "password": [
            "--password",
            "--pat",
            os.getenv("SNOWFLAKE_PASSWORD") or os.getenv("SNOWFLAKE_PAT"),
            "Password for the user.",
        ],
        "role": [
            "--role",
            os.getenv("SNOWFLAKE_ROLE"),
            "Name of the role to use.",
        ],
        "warehouse": [
            "--warehouse",
            os.getenv("SNOWFLAKE_WAREHOUSE"),
            "Name of the warehouse to use.",
        ],
        "passcode_in_password": [
            "--passcode-in-password",
            False,
            "False by default. Set this to True if the MFA (Multi-Factor Authentication) passcode is embedded in the login password.",
        ],
        "passcode": [
            "--passcode",
            os.getenv("SNOWFLAKE_PASSCODE"),
            "The passcode provided by Duo when using MFA (Multi-Factor Authentication) for login.",
        ],
        "private_key": [
            "--private-key",
            os.getenv("SNOWFLAKE_PRIVATE_KEY"),
            "The private key used for authentication.",
        ],
        "private_key_file": [
            "--private-key-file",
            os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE"),
            "Specifies the path to the private key file for the specified user.",
        ],
        "private_key_pwd": [
            "--private-key-pwd",
            os.getenv("SNOWFLAKE_PRIVATE_KEY_PWD"),
            "Specifies the passphrase to decrypt the private key file for the specified user.",
        ],
        "authenticator": [
            "--authenticator",
            "snowflake",
            """Authenticator for Snowflake:

snowflake (default) to use the internal Snowflake authenticator.

externalbrowser to authenticate using your web browser and Okta, AD FS, or any other SAML 2.0-compliant identity provider (IdP) that has been defined for your account.

https://<okta_account_name>.okta.com (i.e. the URL endpoint for your Okta account) to authenticate through native Okta.

oauth to authenticate using OAuth. You must also specify the token parameter and set its value to the OAuth access token.

username_password_mfa to authenticate with MFA token caching. For more details, see Using MFA token caching to minimize the number of prompts during authentication — optional.

OAUTH_AUTHORIZATION_CODE to use the OAuth 2.0 Authorization Code flow.

OAUTH_CLIENT_CREDENTIALS to use the OAuth 2.0 Client Credentials flow.

If the value is not snowflake, the user and password parameters must be your login credentials for the IdP.""",
        ],
        "connection_name": [
            "--connection-name",
            None,
            "Name of the connection in Snowflake configuration file to use.",
        ],
    }
    return login_params
