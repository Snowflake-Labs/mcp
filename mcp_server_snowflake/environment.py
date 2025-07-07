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


def construct_snowflake_api_url(account_identifier: str, api_path: str) -> str:
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
    str
        Complete API URL for the Snowflake service

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
    else:
        host = account_identifier

    base_url = f"https://{host}"
    return urljoin(base_url, api_path.lstrip("/"))
