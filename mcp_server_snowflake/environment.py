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
from pathlib import Path
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def is_running_in_container() -> bool:
    """
    Check if the application is running inside a Snowflake container.

    Returns
    -------
    bool
        True if running in a Snowflake container, False otherwise
    """
    token_path = Path("/snowflake/session/token")
    return token_path.exists() and token_path.is_file()


def construct_snowflake_post(
    account_identifier: str, api_path: str, **kwargs
) -> tuple[str, dict[str, str]]:
    """
    Construct a Snowflake API URL based on the environment (container vs external).

    Parameters
    ----------
    account_identifier : str
        Snowflake account identifier (used when running externally)
    api_path : str
        The API path to append to the base URL (e.g., "/api/v2/cortex/analyst/message")

    Returns
    -------
    tuple[str, dict[str, str]]
        Complete API URL for the Snowflake service and headers

    Examples
    --------
    >>> # External environment
    >>> construct_snowflake_api_url("myaccount", "/api/v2/cortex/analyst/message")
    'https://myaccount.snowflakecomputing.com/api/v2/cortex/analyst/message'

    >>> # Container environment (with SNOWFLAKE_HOST set)
    >>> construct_snowflake_api_url("myaccount", "/api/v2/cortex/analyst/message")
    'https://some-host.snowflakecomputing.com/api/v2/cortex/analyst/message'
    """
    if is_running_in_container():
        host = os.getenv("SNOWFLAKE_HOST", account_identifier)
        headers = {
            "Authorization": f"Bearer {get_container_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
    else:
        host = account_identifier
        headers = {
            "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
            "Authorization": f"Bearer {kwargs.get('PAT')}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    base_url = f"https://{host}"
    return urljoin(base_url, api_path.lstrip("/")), headers


def get_container_token() -> str:
    """
    Read the OAuth token from the container environment.

    Returns
    -------
    str
        The OAuth token for container authentication

    Raises
    ------
    FileNotFoundError
        If the token file is not found
    """
    token_path = Path("/snowflake/session/token")
    try:
        with open(token_path, "r") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading container token: {e}")
        raise
