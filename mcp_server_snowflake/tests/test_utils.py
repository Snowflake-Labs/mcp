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

import pytest

from mcp_server_snowflake.utils import SnowflakeException


class TestSnowflakeException:
    """Test cases for SnowflakeException class."""

    def test_init_with_all_parameters(self):
        """Test SnowflakeException initialization with all parameters."""
        exception = SnowflakeException(
            tool="Cortex Search", message="Service not found", status_code=404
        )

        assert exception.tool == "Cortex Search"
        assert exception.message == "Service not found"
        assert exception.status_code == 404

    @pytest.mark.parametrize(
        "tool,message,status_code,expected",
        [
            (
                "Cortex Search",
                "Invalid service name",
                400,
                "Cortex Search Error: The resource cannot be found or the request is invalid.\n\nError Message: Invalid service name ",
            ),
            (
                "Cortex Analyst",
                "unknown model xyz not found",
                400,
                "Cortex Analyst Error: The resource cannot be found or the request is invalid.\n\nError Message: unknown model xyz not found ",
            ),
            (
                "Cortex Analyst",
                "Authentication failed",
                401,
                "Cortex Analyst Error: An authorization error occurred.\n\nError Message: Authentication failed ",
            ),
            (
                "Cortex Search",
                "Access denied",
                403,
                "Cortex Search Error: An error has occurred.\n\nError Message: Access denied \n Code: 403",
            ),
            (
                "Cortex Analyst",
                "Service not found",
                404,
                "Cortex Analyst Error: An error has occurred.\n\nError Message: Service not found \n Code: 404",
            ),
            (
                "Cortex Search",
                "Internal server error",
                500,
                "Cortex Search Error: An error has occurred.\n\nError Message: Internal server error \n Code: 500",
            ),
            (
                "Cortex Search",
                "Service unavailable",
                503,
                "Cortex Search Error: An error has occurred.\n\nError Message: Service unavailable \n Code: 503",
            ),
        ],
    )
    def test_str_representation(self, tool, message, status_code, expected):
        """Test string representation for various realistic error scenarios."""
        exception = SnowflakeException(
            tool=tool, message=message, status_code=status_code
        )
        assert str(exception) == expected

    def test_inheritance_and_raise(self):
        """Test that SnowflakeException properly inherits from Exception and can be raised."""
        exception = SnowflakeException(
            tool="Cortex Search", message="Test error", status_code=400
        )

        assert isinstance(exception, Exception)

        with pytest.raises(SnowflakeException) as exc_info:
            raise exception

        assert exc_info.value.tool == "Cortex Search"
        assert exc_info.value.message == "Test error"
        assert exc_info.value.status_code == 400
