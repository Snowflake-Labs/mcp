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
import os
import argparse
from typing import Optional
import yaml
import logging
import json
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.tools import Tool

from mcp_server_snowflake.connection import SnowflakeConnectionManager
from mcp_server_snowflake.utils import (
    MissingArgumentsException,
    load_tools_config_resource,
)
import mcp_server_snowflake.tools as tools

server_name = "mcp-server-snowflake"
tag_major_version = 1
tag_minor_version = 1

logger = logging.getLogger(server_name)


class SnowflakeService:
    """
    Snowflake service configuration and management.

    This class handles the configuration and setup of Snowflake Cortex services
    including search, analyst, and agent services. It loads service specifications
    from a YAML configuration file and provides access to service parameters.

    Parameters
    ----------
    account_identifier : str, optional
        Snowflake account identifier
    username : str, optional
        Snowflake username for authentication
    pat : str, optional
        Programmatic Access Token for Snowflake authentication
    config_path : str, optional
        Path to the service configuration YAML file

    Attributes
    ----------
    account_identifier : str
        Snowflake account identifier
    username : str
        Snowflake username
    pat : str
        Programmatic Access Token
    config_path : str
        Path to configuration file
    default_complete_model : str
        Default model for Cortex Complete operations
    search_services : list
        List of configured search service specifications
    analyst_services : list
        List of configured analyst service specifications
    agent_services : list
        List of configured agent service specifications
    """

    def __init__(
        self,
        account_identifier: Optional[str] = None,
        username: Optional[str] = None,
        pat: Optional[str] = None,
        config_path: Optional[str] = None,
    ):
        self.account_identifier = account_identifier
        self.username = username
        self.pat = pat
        self.config_path = config_path
        self.config_path_uri = Path(config_path).resolve().as_uri()
        self.default_complete_model = None
        self.search_services = []
        self.analyst_services = []
        self.agent_services = []

        self.connection_manager = SnowflakeConnectionManager(
            account_identifier=account_identifier, username=username, pat=pat
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
            # Load the service configuration from a YAML file
            with open(self.config_path, "r") as file:
                service_config = yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"Service configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading service config: {e}")
            raise

        # Extract the service specifications
        try:
            self.search_services = service_config.get("search_services", [])
            self.analyst_services = service_config.get("analyst_services", [])
            self.agent_services = service_config.get(
                "agent_services", []
            )  # Not supported yet
            self.default_complete_model = service_config.get("cortex_complete", {}).get(
                "default_model", None
            )
        except Exception as e:
            logger.error(f"Error extracting service specifications: {e}")
            raise

        if self.default_complete_model is None:
            logger.warning(
                "No default model found in the service specification. Using snowflake-llama-3.3-70b as default."
            )
            self.default_complete_model = "snowflake-llama-3.3-70b"

    def set_query_tag(
        self,
        query_tag: dict[str, str] = {"origin": "sf_sit", "name": "mcp_server"},
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

        try:
            # Use connection manager to set query tag and test connection
            self.connection_manager.set_query_tag(query_tag)
            with self.connection_manager.get_connection() as (con, cur):
                cur.execute("SELECT 1").fetchone()
        except Exception as e:
            logger.warning(f"Error setting query tag: {e}")


def get_var(var_name: str, env_var_name: str, args) -> str | None:
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
    str | None
        The variable value if found in either source, None otherwise

    Examples
    --------
    Get account identifier from args or environment:

    >>> args = parser.parse_args(['--account-identifier', 'myaccount'])
    >>> get_var('account_identifier', 'SNOWFLAKE_ACCOUNT', args)
    'myaccount'

    >>> os.environ['SNOWFLAKE_ACCOUNT'] = 'myaccount'
    >>> args = parser.parse_args([])
    >>> get_var('account_identifier', 'SNOWFLAKE_ACCOUNT', args)
    'myaccount'
    """

    if getattr(args, var_name):
        return getattr(args, var_name)
    elif env_var_name in os.environ:
        return os.environ[env_var_name]
    else:
        return None


def create_snowflake_service():
    """
    Main entry point for the Snowflake MCP server package.

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
    - service-config-file: Path to service configuration file

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
    )

    if not all(parameters.values()):
        raise MissingArgumentsException(
            missing=[k for k, v in parameters.items() if not v]
        ) from None

    snowflake_service = SnowflakeService(
        account_identifier=account_identifier,
        username=username,
        pat=pat,
        config_path=service_config_file,
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
        tools_config = await load_tools_config_resource(snowflake_service.config_path)
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

        chat_complete_wrapper = tools.create_chat_complete_wrapper(
            snowflake_service=snowflake_service
        )
        server.add_tool(
            Tool.from_function(
                fn=chat_complete_wrapper,
                name="cortex_complete",
                description="Generate text completions using Snowflake Cortex Complete API.",
            )
        )

        get_cortex_models_wrapper = tools.create_get_cortex_models_wrapper(
            snowflake_service=snowflake_service
        )
        server.add_tool(
            Tool.from_function(
                fn=get_cortex_models_wrapper,
                name="get_cortex_models",
                description="Retrieves available Cortex Complete models and their regional availability.",
            )
        )


def main():
    snowflake_service = create_snowflake_service()
    initialize_tools(snowflake_service)
    initialize_resources(snowflake_service)

    server.run()


if __name__ == "__main__":
    main()
