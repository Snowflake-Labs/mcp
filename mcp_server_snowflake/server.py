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
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Literal, Optional, Tuple, cast

import yaml
from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger
from snowflake.connector import DictCursor, connect
from snowflake.core import Root

from mcp_server_snowflake.cortex_services.tools import (
    initialize_cortex_agent_tool,
    initialize_cortex_analyst_tool,
    initialize_cortex_search_tool,
)
from mcp_server_snowflake.environment import (
    get_spcs_container_token,
    is_running_in_spcs_container,
)
from mcp_server_snowflake.object_manager.tools import initialize_object_manager_tools
from mcp_server_snowflake.query_manager.tools import initialize_query_manager_tool
from mcp_server_snowflake.semantic_manager.tools import (
    initialize_semantic_manager_tools,
)
from mcp_server_snowflake.server_utils import initialize_middleware
from mcp_server_snowflake.utils import (
    cleanup_snowflake_service,
    get_login_params,
    load_tools_config_resource,
    unpack_sql_statement_permissions,
    warn_deprecated_params,
)

# Used to quantify Snowflake usage
server_name = "mcp-server-snowflake"
tag_major_version = 1
tag_minor_version = 3
query_tag = {"origin": "sf_sit", "name": "mcp_server"}

logger = get_logger(server_name)


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
    endpoint : str, default="/mcp"
        Custom endpoint path for HTTP transports

    Attributes
    ----------
    service_config_file : str
        Path to configuration file
    transport : Literal["stdio", "http", "sse", "streamable-http"]
        Transport for the MCP server
    endpoint : str
        Custom endpoint path for HTTP transports
    search_services : list
        List of configured search service specifications
    analyst_services : list
        List of configured analyst service specifications
    agent_services : list
        List of configured agent service specifications
    sql_statement_allowed : list
        List of allowed SQL statement types
    sql_statement_disallowed : list
        List of disallowed SQL statement types
    connection : snowflake.connector.Connection
        Snowflake connection object
    """

    def __init__(
        self,
        service_config_file: str,
        transport: str,
        connection_params: dict,
        endpoint: str = "/mcp",
    ):
        if service_config_file is None:
            raise ValueError(
                "service_config_file cannot be None. Please provide a path to the service configuration file."
            )

        self.service_config_file = str(Path(service_config_file).expanduser().resolve())
        self.config_path_uri = Path(self.service_config_file).as_uri()
        self.transport = cast(
            Literal["stdio", "http", "sse", "streamable-http"], transport
        )
        self.connection_params = connection_params
        self.endpoint = endpoint
        self.search_services = []
        self.analyst_services = []
        self.agent_services = []
        self.sql_statement_allowed = []
        self.sql_statement_disallowed = []
        self.object_manager = False
        self.query_manager = False
        self.semantic_manager = False
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
        self.root = Root(self.connection)

    def unpack_service_specs(self) -> None:
        """
        Load and parse service specifications from configuration file.

        Reads the YAML configuration file and extracts service specifications
        for all services managed by YAML configuration.
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
            self.sql_statement_allowed, self.sql_statement_disallowed = (
                unpack_sql_statement_permissions(
                    service_config.get("sql_statement_permissions", [])
                )
            )
            other_services = service_config.get("other_services", {})
            if other_services is not None:
                self.object_manager = other_services.get("object_manager", False)
                self.query_manager = other_services.get("query_manager", False)
                self.semantic_manager = other_services.get("semantic_manager", False)

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

            # We are passing session_parameters and client_session_keep_alive
            # so we cannot rely on the connection to infer default connection name.
            # So instead, if no explicit values passed via CLI, we replicate the same logic here
            if not connection_params:
                connection_params = {
                    "connection_name": os.getenv(
                        "SNOWFLAKE_DEFAULT_CONNECTION_NAME", "default"
                    ),
                }

            connection = connect(
                **connection_params,
                session_parameters=session_parameters,
                client_session_keep_alive=True,
                paramstyle="qmark",
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
                    paramstyle="qmark",
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

    >>> args = parser.parse_args(["--account", "myaccount"])
    >>> get_var("account", "SNOWFLAKE_ACCOUNT", args)
    'myaccount'

    >>> os.environ["SNOWFLAKE_ACCOUNT"] = "myaccount"
    >>> args = parser.parse_args([])
    >>> get_var("account", "SNOWFLAKE_ACCOUNT", args)
    'myaccount'
    """

    if getattr(args, var_name):
        return getattr(args, var_name)
    if env_var_name in os.environ:
        return os.environ[env_var_name]
    return None


def parse_arguments():
    """Parse command line arguments once at startup."""
    parser = argparse.ArgumentParser(description="Snowflake MCP Server")

    login_params = get_login_params()

    for value in login_params.values():
        parser.add_argument(
            *value[:-2], required=False, default=value[-2], help=value[-1]
        )

    parser.add_argument(
        "--service-config-file",
        required=False,
        help="Path to service specification file",
    )
    parser.add_argument(
        "--transport",
        required=False,
        choices=["stdio", "http", "sse", "streamable-http"],
        help="Transport for the MCP server",
        default="stdio",
    )
    parser.add_argument(
        "--server-host",  # Avoid using simply host here as it conflicts with the host argument in the Snowflake Python Connector
        required=False,
        help="Host address to bind the server to (default: 0.0.0.0)",
        default="0.0.0.0",
    )
    # These left as simply port and endpoint for backward compatibility with existing deployments
    parser.add_argument(
        "--port",
        required=False,
        type=int,
        help="Port number for the server to listen on (default: 9000)",
        default=9000,
    )
    parser.add_argument(
        "--endpoint",
        required=False,
        help="Endpoint path for the MCP server (default: /mcp)",
        default="/mcp",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        required=False,
        help="Enable verbose/debug logging",
        default=False,
    )

    return parser.parse_args()


def create_lifespan(args):
    """Create a lifespan function with captured arguments."""

    @asynccontextmanager
    async def create_snowflake_service(
        server: FastMCP,
    ) -> AsyncIterator[SnowflakeService]:
        """
        Create main entry point for the Snowflake MCP server package.

        Uses pre-parsed command line arguments to create and configure the Snowflake service.
        """
        connection_params = {
            key: getattr(args, key)
            for key in get_login_params().keys()
            if getattr(args, key) is not None
        }
        service_config_file = get_var(
            "service_config_file", "SERVICE_CONFIG_FILE", args
        )

        endpoint = os.environ.get("SNOWFLAKE_MCP_ENDPOINT", args.endpoint)

        snowflake_service = None
        try:
            snowflake_service = SnowflakeService(
                service_config_file=service_config_file,
                transport=args.transport,
                connection_params=connection_params,
                endpoint=endpoint or args.endpoint,
            )

            # Initialize tools and resources now that we have the service
            logger.info("Initializing tools and resources...")
            initialize_tools(snowflake_service, server)
            initialize_middleware(server, snowflake_service)
            initialize_resources(snowflake_service, server)

            yield snowflake_service
        except Exception as e:
            logger.error(f"Error creating Snowflake service: {e}")
            raise

        finally:
            if snowflake_service is not None:
                cleanup_snowflake_service(snowflake_service)

    return create_snowflake_service


def initialize_resources(snowflake_service: SnowflakeService, server: FastMCP):
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


def initialize_tools(snowflake_service: SnowflakeService, server: FastMCP):
    if snowflake_service is not None:
        # Add tools for object manager
        if snowflake_service.object_manager:
            initialize_object_manager_tools(server, snowflake_service)

        # Add tools for query manager
        if snowflake_service.query_manager:
            initialize_query_manager_tool(server, snowflake_service)

        # Add tools for semantic manager
        if snowflake_service.semantic_manager:
            initialize_semantic_manager_tools(server, snowflake_service)

        # Add tool for agent service
        if snowflake_service.agent_services:
            initialize_cortex_agent_tool(server, snowflake_service)

        # Add tool for search service
        if snowflake_service.search_services:
            initialize_cortex_search_tool(server, snowflake_service)

        if snowflake_service.analyst_services:
            initialize_cortex_analyst_tool(server, snowflake_service)


def main():
    args = parse_arguments()

    # Configure logging level based on verbose flag or environment variable
    if args.verbose or os.getenv("SNOWFLAKE_MCP_VERBOSE", "").lower() in (
        "true",
        "1",
        "yes",
    ):
        import logging

        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("fastmcp").setLevel(logging.DEBUG)
        logging.getLogger(server_name).setLevel(logging.DEBUG)
        logger.debug("Verbose/debug logging enabled")

    warn_deprecated_params()

    # Create server with lifespan that has access to args
    server = FastMCP("Snowflake MCP Server", lifespan=create_lifespan(args))

    try:
        logger.info("Starting Snowflake MCP Server...")

        if args.transport and args.transport in [
            "http",
            "sse",
            "streamable-http",
        ]:
            host = os.environ.get("SNOWFLAKE_MCP_HOST", args.server_host)
            port = int(os.environ.get("SNOWFLAKE_MCP_PORT", str(args.port)))
            endpoint = os.environ.get("SNOWFLAKE_MCP_ENDPOINT", args.endpoint)
            logger.info(f"Starting server with transport: {args.transport}")
            server.run(transport=args.transport, host=host, port=port, path=endpoint)
        else:
            logger.info(f"Starting server with transport: {args.transport or 'stdio'}")
            server.run(transport=args.transport or "stdio")

    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        raise


if __name__ == "__main__":
    main()
