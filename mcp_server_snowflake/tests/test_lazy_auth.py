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

from unittest.mock import MagicMock, patch

import pytest
import yaml

from mcp_server_snowflake.server import SnowflakeService, parse_arguments


@pytest.fixture
def minimal_config_file(tmp_path):
    config = {"search_services": []}
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config))
    return config_file


@pytest.fixture
def mock_snowflake_connect():
    with (
        patch("mcp_server_snowflake.server.connect") as mock_connect,
        patch("mcp_server_snowflake.server.Root") as mock_root,
    ):
        mock_connect.return_value = MagicMock()
        mock_root.return_value = MagicMock()
        yield mock_connect


# --- lazy_auth CLI argument tests ---


def test_parse_arguments_default_lazy_auth(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_MCP_LAZY_AUTH", raising=False)
    with patch("sys.argv", ["prog"]):
        args = parse_arguments()
    assert args.lazy_auth is False


def test_parse_arguments_lazy_auth_flag():
    with patch("sys.argv", ["prog", "--lazy-auth"]):
        args = parse_arguments()
    assert args.lazy_auth is True


def test_parse_arguments_lazy_auth_from_env(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_MCP_LAZY_AUTH", "1")
    with patch("sys.argv", ["prog"]):
        args = parse_arguments()
    assert args.lazy_auth is True


# --- SnowflakeService lazy_auth behavior tests ---


def test_snowflake_service_eager_auth_connects_on_init(
    mock_snowflake_connect, minimal_config_file
):
    """Without lazy_auth, connection is established during __init__."""
    service = SnowflakeService(
        service_config_file=str(minimal_config_file),
        transport="stdio",
        connection_params={},
        lazy_auth=False,
    )
    mock_snowflake_connect.assert_called_once()
    assert service.connection is not None
    assert service.root is not None


def test_snowflake_service_lazy_auth_defers_connection(minimal_config_file):
    """With lazy_auth=True, connect is NOT called during __init__."""
    with (
        patch("mcp_server_snowflake.server.connect") as mock_connect,
        patch("mcp_server_snowflake.server.Root") as mock_root,
    ):
        mock_connect.return_value = MagicMock()
        mock_root.return_value = MagicMock()

        service = SnowflakeService(
            service_config_file=str(minimal_config_file),
            transport="stdio",
            connection_params={},
            lazy_auth=True,
        )
        mock_connect.assert_not_called()
        assert service.connection is None
        assert service.root is None


def test_snowflake_service_lazy_auth_connects_on_ensure(minimal_config_file):
    """With lazy_auth=True, _ensure_connection() triggers the connection."""
    with (
        patch("mcp_server_snowflake.server.connect") as mock_connect,
        patch("mcp_server_snowflake.server.Root") as mock_root,
    ):
        mock_connection = MagicMock()
        mock_root_instance = MagicMock()
        mock_connect.return_value = mock_connection
        mock_root.return_value = mock_root_instance

        service = SnowflakeService(
            service_config_file=str(minimal_config_file),
            transport="stdio",
            connection_params={},
            lazy_auth=True,
        )
        mock_connect.assert_not_called()

        service._ensure_connection()

        mock_connect.assert_called_once()
        assert service.connection is mock_connection
        assert service.root is mock_root_instance


def test_snowflake_service_ensure_connection_idempotent(minimal_config_file):
    """_ensure_connection() called twice only creates one connection."""
    with (
        patch("mcp_server_snowflake.server.connect") as mock_connect,
        patch("mcp_server_snowflake.server.Root"),
    ):
        mock_connect.return_value = MagicMock()

        service = SnowflakeService(
            service_config_file=str(minimal_config_file),
            transport="stdio",
            connection_params={},
            lazy_auth=True,
        )
        service._ensure_connection()
        service._ensure_connection()

        mock_connect.assert_called_once()
