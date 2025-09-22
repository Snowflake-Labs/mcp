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
from pathlib import Path
from urllib.parse import urljoin

from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


def is_running_in_spcs_container() -> bool:
    """
    Check if the application is running inside a Snowflake SPCS (Snowpark Container Services) container.

    Returns
    -------
    bool
        True if running in a Snowflake SPCS container, False otherwise
    """
    token_path = Path("/snowflake/session/token")
    return token_path.exists() and token_path.is_file()


def construct_snowflake_post(service, api_path: str) -> tuple[str, dict[str, str]]:
    """
    Construct a Snowflake API URL based on the environment (SPCS container vs external).

    Parameters
    ----------
    service : SnowflakeService
        Snowflake service instance
    api_path : str
        The API path to append to the base URL (e.g., "/api/v2/cortex/analyst/message")

    Returns
    -------
    tuple[str, dict[str, str]]
        Complete API URL for the Snowflake service and headers

    Examples
    --------
    >>> # External environment
    >>> construct_snowflake_post(service, "/api/v2/cortex/analyst/message")
    ('https://myaccount.snowflakecomputing.com/api/v2/cortex/analyst/message', {...})

    >>> # SPCS container environment (with SNOWFLAKE_HOST set)
    >>> construct_snowflake_post(service, "/api/v2/cortex/analyst/message")
    ('https://some-host.snowflakecomputing.com/api/v2/cortex/analyst/message', {...})
    """
    host = service.get_api_host()
    headers = service.get_api_headers()

    if host.startswith(("http://", "https://")):
        base_url = host
    else:
        if not host.endswith(".snowflakecomputing.com"):
            host = f"{host}.snowflakecomputing.com"
        base_url = f"https://{host}"

    return urljoin(base_url, api_path), headers


def get_spcs_container_token() -> str:
    """
    Read the OAuth token from the SPCS container environment.

    Returns
    -------
    str
        The OAuth token for SPCS container authentication

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
