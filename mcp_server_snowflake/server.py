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
    cleanup_snowflake_service,
    load_tools_config_resource,
)

# Used to quantify Snowflake usage
server_name = "mcp-server-snowflake"
tag_major_version = 0
tag_minor_version = 4
query_tag = {"origin": "sf_sit", "name": "mcp_server"}

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
    service_config_file : str
        Path to the service configuration YAML file
    transport : str
        Transport for the MCP server
    connection_params : dict
        Connection parameters for Snowflake connector

    Attributes
    ----------
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
    connection : snowflake.connector.Connection
        Snowflake connection object
    """

    def __init__(
        self,
        service_config_file: str,
        transport: str,
        connection_params: dict,
    ):
        self.service_config_file = str(Path(service_config_file).expanduser().resolve())
        self.config_path_uri = Path(self.service_config_file).as_uri()
        self.transport = cast(Literal["stdio", "sse", "streamable-http"], transport)
        self.connection_params = connection_params
        self.search_services = []
        self.analyst_services = []
        self.agent_services = []
        self.default_session_parameters: Dict[str, Any] = {}
        self.query_tag = query_tag if query_tag is not None else None
        self.tag_major_version = (
            tag_major_version if tag_major_version is not None else None
        )
        self.tag_minor_version = (
            tag_minor_version if tag_minor_version is not None else None
        )

        # Environment detection for authentication
        self._is_spcs_container = is_running_in_spcs_container()

        self.unpack_service_specs()
        # Persist connection to avoid closing it after each request
        self.connection = self._get_persistent_connection()

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
            # For external environments, we need to use the connection token
            return {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f'Snowflake Token="{self.connection.rest.token}"',
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
            return os.getenv(
                "SNOWFLAKE_HOST", self.connection_params.get("account", "")
            )
        else:
            return self.connection.host

    @staticmethod
    def send_initial_query(connection: Any) -> None:
        """
        Send an initial query to the Snowflake service.
        """
        with connection.cursor() as cur:
            cur.execute("SELECT 'MCP Server Snowflake'").fetchone()

    def _get_persistent_connection(
        self,
        session_parameters: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Get a persistent Snowflake connection.

        This method creates a connection that will be kept alive and should be
        explicitly closed when no longer needed.

        Parameters
        ----------
        session_parameters : dict, optional
            Additional session parameters to add to connection
        major_version : int, optional
            Major version of the query tag
        minor_version : int, optional
            Minor version of the query tag

        Returns
        -------
        connection
            A Snowflake connection object
        """
        try:
            query_tag_params = self.get_query_tag_param()

            if session_parameters is not None:
                if query_tag_params:
                    session_parameters.update(query_tag_params)
            else:
                session_parameters = query_tag_params

            # Get connection parameters based on environment
            if self._is_spcs_container:
                logger.info("Using SPCS container OAuth authentication")
                connection_params = {
                    "host": os.getenv("SNOWFLAKE_HOST"),
                    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
                    "token": get_spcs_container_token(),
                    "authenticator": "oauth",
                }
                connection_params = {
                    k: v for k, v in connection_params.items() if v is not None
                }
            else:
                logger.info("Using external authentication")
                connection_params = self.connection_params.copy()

            connection = connect(
                **connection_params,
                session_parameters=session_parameters,
                client_session_keep_alive=True,
            )
            if connection:  # Send zero compute query to capture query tag
                self.send_initial_query(connection)
                return connection
        except Exception as e:
            logger.error(f"Error establishing persistent Snowflake connection: {e}")
            raise

    @contextmanager
    def get_connection(
        self,
        use_dict_cursor: bool = False,
        session_parameters: Optional[Dict[str, Any]] = None,
    ) -> Generator[Tuple[Any, Any], None, None]:
        """
        Get a Snowflake connection with the specified configuration.

        This context manager ensures proper connection handling and cleanup.
        It automatically detects the environment and uses appropriate authentication.

        If the connection is not established, it will be established with the specified parameters.
        If the connection is already established, it will be used and session_parameters ignored.

        Parameters
        ----------
        use_dict_cursor : bool, default=False
            Whether to use DictCursor instead of regular cursor
        session_parameters : dict, optional
            Additional session parameters to add to connection such as query tag

        Yields
        ------
        tuple
            A tuple containing (connection, cursor)

        Examples
        --------
        >>> with service.get_connection(use_dict_cursor=True) as (con, cur):
        ...     cur.execute("SELECT current_version()")
        ...     result = cur.fetchone()
        """

        try:
            if self.connection is None:
                # Get connection parameters based on environment
                if self._is_spcs_container:
                    logger.info("Using SPCS container OAuth authentication")
                    connection_params = {
                        "host": os.getenv("SNOWFLAKE_HOST"),
                        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
                        "token": get_spcs_container_token(),
                        "authenticator": "oauth",
                    }
                    connection_params = {
                        k: v for k, v in connection_params.items() if v is not None
                    }
                else:
                    logger.info("Using external authentication")
                    connection_params = self.connection_params.copy()

                self.connection = connect(
                    **connection_params,
                    session_parameters=session_parameters,
                    client_session_keep_alive=False,
                )

            cursor = (
                self.connection.cursor(DictCursor)
                if use_dict_cursor
                else self.connection.cursor()
            )

            try:
                yield self.connection, cursor
            finally:
                cursor.close()
                # connection.close()

        except Exception as e:
            logger.error(f"Error establishing Snowflake connection: {e}")
            raise

    def get_query_tag_param(
        self,
    ) -> Optional[Dict[str, Any]] | None:
        """
        Get the query tag parameters for the Snowflake service.

        Parameters
        ----------
        query_tag : dict[str, str], optional
            Query tag dictionary
        major_version : int, optional
            Major version of the query tag
        minor_version : int, optional
            Minor version of the query tag
        """
        if self.query_tag is not None:
            query_tag = self.query_tag.copy()
            if (
                self.tag_major_version is not None
                and self.tag_minor_version is not None
            ):
                query_tag["version"] = {
                    "major": self.tag_major_version,
                    "minor": self.tag_minor_version,
                }

            # Set the query tag in default session parameters
            session_parameters = {"QUERY_TAG": json.dumps(query_tag)}

            return session_parameters
        else:
            return None


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
    The server uses the Snowflake Python connector to establish a connection to Snowflake.
    - See https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect
    for connection parameters.
    - service_config_file is also required as the path to the service configuration file

    """
    parser = argparse.ArgumentParser(description="Snowflake MCP Server")

    # Dict of login params supported by snowflake connector api to establish connection
    # {Key value name : [argparse argument name, default value]}
    login_params = {  # TODO: Add help for each argument
        "account": [
            "--account",
            "--account-identifier",
            os.getenv("SNOWFLAKE_ACCOUNT"),
        ],
        "host": ["--host", os.getenv("SNOWFLAKE_HOST")],
        "user": ["--user", "--username", os.getenv("SNOWFLAKE_USER")],
        "password": [
            "--password",
            "--pat",
            os.getenv("SNOWFLAKE_PASSWORD") or os.getenv("SNOWFLAKE_PAT"),
        ],
        "role": ["--role", os.getenv("SNOWFLAKE_ROLE")],
        "warehouse": ["--warehouse", os.getenv("SNOWFLAKE_WAREHOUSE")],
        "passcode_in_password": ["--passcode-in-password", False],
        "passcode": ["--passcode", os.getenv("SNOWFLAKE_PASSCODE")],
        "private_key": ["--private-key", os.getenv("SNOWFLAKE_PRIVATE_KEY")],
        "private_key_file": [
            "--private-key-file",
            os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE"),
        ],
        "private_key_pwd": [
            "--private-key-pwd",
            os.getenv("SNOWFLAKE_PRIVATE_KEY_PWD"),
        ],
        "authenticator": ["--authenticator", "snowflake"],
        "connection_name": ["--connection-name", None],
    }

    for value in login_params.values():
        parser.add_argument(*value[:-1], required=False, default=value[-1])

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
    connection_params = {
        key: getattr(args, key)
        for key in login_params.keys()
        if getattr(args, key) is not None
    }
    service_config_file = get_var("service_config_file", "SERVICE_CONFIG_FILE", args)

    if not service_config_file:
        raise MissingArgumentsException(missing=["service_config_file"]) from None
    try:
        snowflake_service = SnowflakeService(
            service_config_file=service_config_file,
            transport=args.transport,
            connection_params=connection_params,
        )
        return snowflake_service
    except Exception as e:
        logger.error(f"Error creating Snowflake service: {e}")
        raise


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
    try:
        logger.info("Creating Snowflake service...")
        snowflake_service = create_snowflake_service()

        try:
            logger.info("Initializing tools and resources...")
            initialize_tools(snowflake_service)
            initialize_resources(snowflake_service)

            logger.info(
                f"Starting server with transport: {snowflake_service.transport}"
            )
            if snowflake_service.transport in ["sse", "streamable-http"]:
                server.run(
                    transport=snowflake_service.transport, host="0.0.0.0", port=9000
                )
            else:
                server.run(transport=snowflake_service.transport)

        finally:
            cleanup_snowflake_service(snowflake_service)

    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        raise


if __name__ == "__main__":
    main()
