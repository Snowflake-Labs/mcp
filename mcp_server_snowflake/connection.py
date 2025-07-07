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
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional, Tuple

from snowflake.connector import DictCursor, connect

from mcp_server_snowflake.auth import SnowflakeAuthManager

logger = logging.getLogger(__name__)


class SnowflakeConnectionManager:
    """
    Manages Snowflake connections with consistent configuration and error handling.

    This class provides a centralized way to establish connections to Snowflake
    with consistent configuration, session parameters, and error handling.
    It automatically detects when running inside a Snowflake container to use OAuth
    authentication.

    Attributes
    ----------
    auth_manager : SnowflakeAuthManager
        Authentication manager for handling credentials
    default_session_parameters : dict
        Default session parameters to apply to all connections
    """

    def __init__(
        self,
        account_identifier: str,
        username: str,
        pat: str,
        default_session_parameters: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the connection manager.

        Parameters
        ----------
        account_identifier : str
            Snowflake account identifier
        username : str
            Snowflake username for authentication (not used in container environment)
        pat : str
            Programmatic Access Token for authentication (not used in container environment)
        default_session_parameters : dict, optional
            Default session parameters to apply to all connections
        """
        self.auth_manager = SnowflakeAuthManager(
            account_identifier=account_identifier,
            username=username,
            pat=pat,
        )
        self.default_session_parameters = default_session_parameters or {}

    def _get_connection_params(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Get connection parameters based on the environment (container vs external).

        Parameters
        ----------
        **kwargs : Any
            Additional connection parameters

        Returns
        -------
        dict
            Connection parameters for snowflake.connector.connect()
        """
        return self.auth_manager.get_connection_params(**kwargs)

    def set_query_tag(self, query_tag: dict) -> None:
        """
        Set the query tag in default session parameters.

        Parameters
        ----------
        query_tag : dict
            Query tag to set in session parameters
        """
        self.default_session_parameters["QUERY_TAG"] = json.dumps(query_tag)

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
        >>> with connection_manager.get_connection(
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
            connection_params = self._get_connection_params(**kwargs)
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
