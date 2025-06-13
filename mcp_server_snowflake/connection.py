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
from typing import Optional, Dict, Any, Tuple
from snowflake.connector import connect, DictCursor

logger = logging.getLogger(__name__)


class SnowflakeConnectionManager:
    """
    Manages Snowflake connections with consistent configuration and error handling.

    This class provides a centralized way to establish connections to Snowflake
    with consistent configuration, session parameters, and error handling.
    It supports both regular and dictionary cursor connections.

    Attributes
    ----------
    account_identifier : str
        Snowflake account identifier
    username : str
        Snowflake username for authentication
    pat : str
        Programmatic Access Token for authentication
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
            Snowflake username for authentication
        pat : str
            Programmatic Access Token for authentication
        default_session_parameters : dict, optional
            Default session parameters to apply to all connections
        """
        self.account_identifier = account_identifier
        self.username = username
        self.pat = pat
        self.default_session_parameters = default_session_parameters or {}

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
    ) -> Tuple[Any, Any]:
        """
        Get a Snowflake connection with the specified configuration.

        This context manager ensures proper connection handling and cleanup.

        Parameters
        ----------
        session_parameters : dict, optional
            Additional session parameters to merge with defaults
        use_dict_cursor : bool, default=False
            Whether to use DictCursor instead of regular cursor

        Yields
        ------
        tuple
            A tuple containing (connection, cursor)

        Examples
        --------
        >>> with connection_manager.get_connection(use_dict_cursor=True) as (con, cur):
        ...     cur.execute("SELECT current_version()")
        ...     result = cur.fetchone()
        """
        # Merge default and provided session parameters
        merged_params = self.default_session_parameters.copy()
        if session_parameters:
            merged_params.update(session_parameters)

        try:
            connection = connect(
                account=self.account_identifier,
                user=self.username,
                password=self.pat,
                session_parameters=merged_params,
            )

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
