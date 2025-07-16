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
"""
Snowflake MCP Server Package.

This package provides a Model Context Protocol (MCP) server implementation for
interacting with Snowflake's Cortex AI services. The server enables seamless
integration with Snowflake's machine learning and AI capabilities through a
standardized protocol interface.

The package supports:
- Cortex Search: Semantic search across Snowflake data
- Cortex Analyst: Natural language to SQL query generation

The server can be configured through command-line arguments or environment
variables and uses a YAML configuration file to define service specifications.

Environment Variables
---------------------
SNOWFLAKE_ACCOUNT : str
    Snowflake account identifier (alternative to --account)
SNOWFLAKE_USER : str
    Snowflake username (alternative to --username)
SNOWFLAKE_PASSWORD : str
    Password or Programmatic Access Token (alternative to --password)
SERVICE_CONFIG_FILE : str
    Path to service configuration file (alternative to --service-config-file)
"""

from mcp_server_snowflake.server import main

__all__ = ["main"]
