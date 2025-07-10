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
import argparse
import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Literal, Optional, Tuple, cast

import yaml
from fastmcp import FastMCP
from fastmcp.tools import Tool
from snowflake.connector import DictCursor, connect

import mcp_server_snowflake.tools as tools
from mcp_server_snowflake.environment import (
    get_spcs_container_token,
    is_running_in_spcs_container,
)
from mcp_server_snowflake.utils import (
    MissingArgumentsException,
    load_tools_config_resource,
)

server_name = "mcp-server-snowflake"
tag_major_version = 0
tag_minor_version = 3

logger = logging.getLogger(server_name)


class SnowflakeService:
    """
    Snowflake service configuration and management.

    This class handles the configuration and setup of Snowflake Cortex services
    including search, and analyst. It loads service specifications from a
    YAML configuration file and provides access to service parameters.

    It also handles all Snowflake authentication and connection logic,
    automatically detecting the environment (container vs external) and
    providing appropriate authentication parameters for both database
    connections and REST API calls.

    Parameters
    ----------
    account_identifier : str
        Snowflake account identifier
    username : str
        Snowflake username for authentication
    pat : str
        Programmatic Access Token for Snowflake authentication
    service_config_file : str
        Path to the service configuration YAML file
    transport : str
        Transport for the MCP server

    Attributes
    ----------
    account_identifier : str
        Snowflake account identifier
    username : str
        Snowflake username
    pat : str
        Programmatic Access Token
    service_config_file : str
        Path to configuration file
    transport : Literal["stdio", "sse", "streamable-http"]
        Transport for the MCP server
    search_services : list
        List of configured search service specifications
    analyst_services : list
        List of configured analyst service specifications
    agent_services : list
        List of configured agent service specifications
    default_session_parameters : dict
        Default session parameters to apply to all connections
    """

    def __init__(
        self,
        account_identifier: str,
        username: str,
        pat: str,
        service_config_file: str,
        transport: str,
    ):
        self.account_identifier = account_identifier
        self.username = username
        self.pat = pat
        self.service_config_file = str(Path(service_config_file).expanduser().resolve())
        self.config_path_uri = Path(self.service_config_file).as_uri()
        self.transport = cast(Literal["stdio", "sse", "streamable-http"], transport)
        self.search_services = []
        self.analyst_services = []
        self.agent_services = []
        self.default_session_parameters: Dict[str, Any] = {}

        # Environment detection for authentication
        self._is_spcs_container = is_running_in_spcs_container()

        # Validate required parameters for external environment
        if not self._is_spcs_container:
            if not all([account_identifier, username, pat]):
                raise ValueError(
                    "When running outside a Snowflake SPCS container, "
                    "account_identifier, username, and pat are required"
                )

        self.unpack_service_specs()
        self.set_query_tag(
            major_version=tag_major_version, minor_version=tag_minor_version
        )

    def unpack_service_specs(self) -> None:
        """
        Load and parse service specifications from configuration file.

        Reads the YAML configuration file and extracts service specifications
        for search, analyst, and agent services. Also sets the default
        completion model.
        """
        try:
            with open(self.service_config_file, "r") as file:
                service_config = yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(
                f"Service configuration file not found: {self.service_config_file}"
            )
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading service config: {e}")
            raise

        try:
            self.search_services = service_config.get("search_services", [])
            self.analyst_services = service_config.get("analyst_services", [])
            self.agent_services = service_config.get(
                "agent_services", []
            )  # Not supported yet
        except Exception as e:
            logger.error(f"Error extracting service specifications: {e}")
            raise

    def get_connection_params(self, **kwargs) -> Dict[str, Any]:
        """
        Get connection parameters for snowflake.connector.connect().

        Parameters
        ----------
        **kwargs
            Additional connection parameters

        Returns
        -------
        Dict[str, Any]
            Connection parameters
        """
        if self._is_spcs_container:
            logger.info("Using SPCS container OAuth authentication")
            params = {
                "host": os.getenv("SNOWFLAKE_HOST"),
                "account": os.getenv("SNOWFLAKE_ACCOUNT"),
                "token": get_spcs_container_token(),
                "authenticator": "oauth",
            }
            params = {k: v for k, v in params.items() if v is not None}
        else:
            logger.info("Using external PAT authentication")
            params = {
                "account": self.account_identifier,
                "user": self.username,
                "password": self.pat,
            }

        params.update(kwargs)
        return params

    def get_api_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for REST API calls.

        Returns
        -------
        Dict[str, str]
            HTTP headers with authentication
        """
        if self._is_spcs_container:
            return {
                "Authorization": f"Bearer {get_spcs_container_token()}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
        else:
            return {
                "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
                "Authorization": f"Bearer {self.pat}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }

    def get_api_host(self) -> str:
        """
        Get the API host for REST API calls.

        Returns
        -------
        str
            API host URL
        """
        if self._is_spcs_container:
            return os.getenv("SNOWFLAKE_HOST", self.account_identifier)
        else:
            return self.account_identifier

    @property
    def is_spcs_container_environment(self) -> bool:
        """Check if running in SPCS container environment."""
        return self._is_spcs_container

    @contextmanager
    def get_connection(
        self,
        session_parameters: Optional[Dict[str, Any]] = None,
        use_dict_cursor: bool = False,
        **kwargs: Any,
    ) -> Generator[Tuple[Any, Any], None, None]:
        """
        Get a Snowflake connection with the specified configuration.

        This context manager ensures proper connection handling and cleanup.
        It automatically detects the environment and uses appropriate authentication.

        Parameters
        ----------
        session_parameters : dict, optional
            Additional session parameters to merge with defaults
        use_dict_cursor : bool, default=False
            Whether to use DictCursor instead of regular cursor
        **kwargs : Any
            Additional connection parameters (e.g., role, warehouse) to pass to connect()

        Yields
        ------
        tuple
            A tuple containing (connection, cursor)

        Examples
        --------
        >>> with service.get_connection(
        ...     role="ANALYST", warehouse="COMPUTE_WH", use_dict_cursor=True
        ... ) as (con, cur):
        ...     cur.execute("SELECT current_version()")
        ...     result = cur.fetchone()
        """
        # Merge default and provided session parameters
        merged_params = self.default_session_parameters.copy()
        if session_parameters:
            merged_params.update(session_parameters)

        try:
            # Get connection parameters based on environment
            connection_params = self.get_connection_params(**kwargs)
            connection_params["session_parameters"] = merged_params

            connection = connect(**connection_params)

            cursor = (
                connection.cursor(DictCursor)
                if use_dict_cursor
                else connection.cursor()
            )

            try:
                yield connection, cursor
            finally:
                cursor.close()
                connection.close()

        except Exception as e:
            logger.error(f"Error establishing Snowflake connection: {e}")
            raise

    def set_query_tag(
        self,
        query_tag: dict[str, str | dict] = {"origin": "sf_sit", "name": "mcp_server"},
        major_version: Optional[int] = None,
        minor_version: Optional[int] = None,
    ) -> None:
        """
        Set the query tag for the Snowflake service.

        Parameters
        ----------
        query_tag : dict[str, str], optional
            Query tag dictionary
        major_version : int, optional
            Major version of the query tag
        minor_version : int, optional
            Minor version of the query tag
        """
        if major_version is not None and minor_version is not None:
            query_tag["version"] = {"major": major_version, "minor": minor_version}

        # Set the query tag in default session parameters
        self.default_session_parameters["QUERY_TAG"] = json.dumps(query_tag)

        try:
            # Test connection with the query tag
            with self.get_connection() as (con, cur):
                cur.execute("SELECT 1").fetchone()
        except Exception as e:
            logger.warning(f"Error setting query tag: {e}")


def get_var(var_name: str, env_var_name: str, args) -> Optional[str]:
    """
    Retrieve variable value from command line arguments or environment variables.

    Checks for a variable value first in command line arguments, then falls back
    to environment variables. This provides flexible configuration options for
    the MCP server.

    Parameters
    ----------
    var_name : str
        The attribute name to check in the command line arguments object
    env_var_name : str
        The environment variable name to check if command line arg is not provided
    args : argparse.Namespace
        Parsed command line arguments object

    Returns
    -------
    Optional[str]
        The variable value if found in either source, None otherwise

    Examples
    --------
    Get account identifier from args or environment:

    >>> args = parser.parse_args(["--account-identifier", "myaccount"])
    >>> get_var("account_identifier", "SNOWFLAKE_ACCOUNT", args)
    'myaccount'

    >>> os.environ["SNOWFLAKE_ACCOUNT"] = "myaccount"
    >>> args = parser.parse_args([])
    >>> get_var("account_identifier", "SNOWFLAKE_ACCOUNT", args)
    'myaccount'
    """

    if getattr(args, var_name):
        return getattr(args, var_name)
    if env_var_name in os.environ:
        return os.environ[env_var_name]
    return None


def create_snowflake_service():
    """
    Create main entry point for the Snowflake MCP server package.

    Parses command line arguments, retrieves configuration from arguments or
    environment variables, validates required parameters, and starts the
    asyncio-based MCP server. The server handles Model Context Protocol
    communications over stdin/stdout streams.

    The function sets up argument parsing for Snowflake connection parameters
    and service configuration, then delegates to the main server implementation.

    Raises
    ------
    MissingArgumentException
        If required parameters (account_identifier and pat) are not provided
        through either command line arguments or environment variables
    SystemExit
        If argument parsing fails or help is requested

    Notes
    -----
    The server requires these minimum parameters:
    - account_identifier: Snowflake account identifier
    - username: Snowflake username
    - pat: Programmatic Access Token for authentication
    - service_config_file: Path to service configuration file

    """
    parser = argparse.ArgumentParser(description="Snowflake MCP Server")

    parser.add_argument(
        "--account-identifier", required=False, help="Snowflake account identifier"
    )
    parser.add_argument(
        "--username", required=False, help="Username for Snowflake account"
    )
    parser.add_argument(
        "--pat", required=False, help="Programmatic Access Token (PAT) for Snowflake"
    )
    parser.add_argument(
        "--service-config-file",
        required=False,
        help="Path to service specification file",
    )
    parser.add_argument(
        "--transport",
        required=False,
        choices=["stdio", "sse", "streamable-http"],
        help="Transport for the MCP server",
        default="stdio",
    )

    args = parser.parse_args()
    account_identifier = get_var("account_identifier", "SNOWFLAKE_ACCOUNT", args)
    username = get_var("username", "SNOWFLAKE_USER", args)
    pat = get_var("pat", "SNOWFLAKE_PAT", args)
    service_config_file = get_var("service_config_file", "SERVICE_CONFIG_FILE", args)

    parameters = dict(
        account_identifier=account_identifier,
        username=username,
        pat=pat,
        service_config_file=service_config_file,
        transport=args.transport,
    )

    if not all(parameters.values()):
        raise MissingArgumentsException(
            missing=[k for k, v in parameters.items() if not v]
        ) from None
    else:
        # Type assertion since we've validated all values are not None
        snowflake_service = SnowflakeService(
            account_identifier=account_identifier or "",
            username=username or "",
            pat=pat or "",
            service_config_file=service_config_file or "",
            transport=args.transport,
        )

        return snowflake_service


server = FastMCP("Snowflake MCP Server")


def initialize_resources(snowflake_service):
    @server.resource(snowflake_service.config_path_uri)
    async def get_tools_config():
        """
        Tools Specification Configuration.

        Provides access to the YAML tools configuration file as JSON.
        """
        tools_config = await load_tools_config_resource(
            snowflake_service.service_config_file
        )
        return json.loads(tools_config)


def initialize_tools(snowflake_service):
    if snowflake_service is not None:
        # Add tools for each configured search service
        if snowflake_service.search_services:
            for service in snowflake_service.search_services:
                search_wrapper = tools.create_search_wrapper(
                    snowflake_service=snowflake_service, service_details=service
                )
                server.add_tool(
                    Tool.from_function(
                        fn=search_wrapper,
                        name=service.get("service_name"),
                        description=service.get(
                            "description",
                            f"Search service: {service.get('service_name')}",
                        ),
                    )
                )

        if snowflake_service.analyst_services:
            for service in snowflake_service.analyst_services:
                cortex_analyst_wrapper = tools.create_cortex_analyst_wrapper(
                    snowflake_service=snowflake_service, service_details=service
                )
                server.add_tool(
                    Tool.from_function(
                        fn=cortex_analyst_wrapper,
                        name=service.get("service_name"),
                        description=service.get(
                            "description",
                            f"Analyst service: {service.get('service_name')}",
                        ),
                    )
                )


def main():
    snowflake_service = create_snowflake_service()
    initialize_tools(snowflake_service)
    initialize_resources(snowflake_service)

    if snowflake_service.transport in ["sse", "streamable-http"]:
        server.run(transport=snowflake_service.transport, host="0.0.0.0", port=9000)
    else:
        server.run(transport=snowflake_service.transport)


if __name__ == "__main__":
    main()
