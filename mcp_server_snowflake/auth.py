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
import logging
import os
from typing import Dict, Optional

from mcp_server_snowflake.environment import (
    get_spcs_container_token,
    is_running_in_spcs_container,
)

logger = logging.getLogger(__name__)


class SnowflakeAuthManager:
    """
    Centralized authentication manager for Snowflake connections and API calls.

    This class handles all authentication logic, automatically detecting the
    environment (container vs external) and providing appropriate authentication
    parameters for both database connections and REST API calls.
    """

    def __init__(
        self,
        account_identifier: str,
        username: Optional[str] = None,
        pat: Optional[str] = None,
    ):
        """
        Initialize the authentication manager.

        Parameters
        ----------
        account_identifier : str
            Snowflake account identifier
        username : str, optional
            Username for external authentication (not used in container)
        pat : str, optional
            Programmatic Access Token for external authentication (not used in container)
        """
        self.account_identifier = account_identifier
        self.username = username
        self.pat = pat
        self._is_spcs_container = is_running_in_spcs_container()

        # Validate required parameters for external environment
        if not self._is_spcs_container:
            if not all([account_identifier, username, pat]):
                raise ValueError(
                    "When running outside a Snowflake SPCS container, "
                    "account_identifier, username, and pat are required"
                )

    def get_connection_params(self, **kwargs) -> Dict[str, str]:
        """
        Get connection parameters for snowflake.connector.connect().

        Parameters
        ----------
        **kwargs
            Additional connection parameters

        Returns
        -------
        Dict[str, str]
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
