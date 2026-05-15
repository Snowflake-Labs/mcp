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

import asyncio
from unittest.mock import MagicMock, patch, call

import pytest
import yaml

from mcp_server_snowflake.server import SnowflakeService, _TOKEN_EXPIRED_ERROR_CODES
from mcp_server_snowflake.utils import SnowflakeException


@pytest.fixture
def mock_connection_params():
    return {
        "account": "test_account",
        "user": "test_user",
        "password": "test_pass",
    }


@pytest.fixture
def valid_config_yaml(tmp_path):
    config = {
        "search_services": [
            {
                "service_name": "test_search",
                "description": "Test search service",
                "database_name": "TEST_DB",
                "schema_name": "TEST_SCHEMA",
            }
        ],
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    return config_file


@pytest.fixture
def snowflake_service(mock_connection_params, valid_config_yaml):
    with (
        patch("mcp_server_snowflake.server.connect") as mock_connect,
        patch("mcp_server_snowflake.server.Root") as mock_root,
    ):
        mock_connect.return_value = MagicMock()
        mock_root.return_value = MagicMock()
        service = SnowflakeService(
            service_config_file=str(valid_config_yaml),
            transport="stdio",
            connection_params=mock_connection_params,
        )
        yield service


class TestIsTokenExpiredError:
    def test_matching_errno_390114(self):
        exc = Exception("token expired")
        exc.errno = 390114
        assert SnowflakeService._is_token_expired_error(exc) is True

    def test_matching_errno_390112(self):
        exc = Exception("token expired")
        exc.errno = 390112
        assert SnowflakeService._is_token_expired_error(exc) is True

    def test_non_matching_errno(self):
        exc = Exception("some other error")
        exc.errno = 12345
        assert SnowflakeService._is_token_expired_error(exc) is False

    def test_no_errno_attribute(self):
        exc = Exception("generic error")
        assert SnowflakeService._is_token_expired_error(exc) is False

    def test_chained_cause_with_matching_errno(self):
        cause = Exception("token expired")
        cause.errno = 390114
        exc = Exception("wrapper error")
        exc.__cause__ = cause
        assert SnowflakeService._is_token_expired_error(exc) is True

    def test_chained_context_with_matching_errno(self):
        context = Exception("token expired")
        context.errno = 390112
        exc = Exception("wrapper error")
        exc.__context__ = context
        assert SnowflakeService._is_token_expired_error(exc) is True

    def test_chained_cause_with_non_matching_errno(self):
        cause = Exception("other error")
        cause.errno = 99999
        exc = Exception("wrapper error")
        exc.__cause__ = cause
        assert SnowflakeService._is_token_expired_error(exc) is False


class TestReconnect:
    def test_reconnect_closes_old_and_creates_new(self, snowflake_service):
        old_connection = snowflake_service.connection
        old_root = snowflake_service.root

        with (
            patch("mcp_server_snowflake.server.connect") as mock_connect,
            patch("mcp_server_snowflake.server.Root") as mock_root,
        ):
            new_connection = MagicMock()
            new_root = MagicMock()
            mock_connect.return_value = new_connection
            mock_root.return_value = new_root

            snowflake_service._reconnect()

            old_connection.close.assert_called_once()
            assert snowflake_service.connection is new_connection
            assert snowflake_service.root is new_root
            mock_root.assert_called_once_with(new_connection)

    def test_reconnect_handles_close_error(self, snowflake_service):
        snowflake_service.connection.close.side_effect = Exception("close failed")

        with (
            patch("mcp_server_snowflake.server.connect") as mock_connect,
            patch("mcp_server_snowflake.server.Root") as mock_root,
        ):
            mock_connect.return_value = MagicMock()
            mock_root.return_value = MagicMock()

            # Should not raise despite close() failing
            snowflake_service._reconnect()

            assert snowflake_service.connection is mock_connect.return_value


class TestRunQueryRetry:
    def test_retry_on_token_expired(self, snowflake_service):
        from mcp_server_snowflake.query_manager.tools import run_query

        token_error = Exception("token expired")
        token_error.errno = 390114

        mock_cursor = MagicMock()
        call_count = 0

        def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise token_error
            return None

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchall.return_value = [{"result": 1}]

        snowflake_service.connection.cursor.return_value = mock_cursor

        with (
            patch("mcp_server_snowflake.server.connect") as mock_connect,
            patch("mcp_server_snowflake.server.Root") as mock_root,
        ):
            new_conn = MagicMock()
            new_cursor = MagicMock()
            new_cursor.fetchall.return_value = [{"result": 1}]
            new_conn.cursor.return_value = new_cursor
            mock_connect.return_value = new_conn
            mock_root.return_value = MagicMock()

            result = run_query("SELECT 1", snowflake_service)
            assert result == [{"result": 1}]

    def test_no_retry_on_non_token_error(self, snowflake_service):
        from mcp_server_snowflake.query_manager.tools import run_query
        from mcp_server_snowflake.utils import SnowflakeException

        generic_error = Exception("syntax error")
        generic_error.errno = 1003

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = generic_error
        snowflake_service.connection.cursor.return_value = mock_cursor

        with pytest.raises(SnowflakeException):
            run_query("SELECT BAD", snowflake_service)


class TestExecuteQueryRetry:
    def test_retry_on_token_expired(self, snowflake_service):
        from mcp_server_snowflake.utils import execute_query

        token_error = Exception("token expired")
        token_error.errno = 390114

        mock_cursor = MagicMock()
        call_count = 0

        def execute_side_effect(stmt, bindvars):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise token_error
            return None

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchall.return_value = [{"col": "val"}]

        snowflake_service.connection.cursor.return_value = mock_cursor

        with (
            patch("mcp_server_snowflake.server.connect") as mock_connect,
            patch("mcp_server_snowflake.server.Root") as mock_root,
        ):
            new_conn = MagicMock()
            new_cursor = MagicMock()
            new_cursor.fetchall.return_value = [{"col": "val"}]
            new_conn.cursor.return_value = new_cursor
            mock_connect.return_value = new_conn
            mock_root.return_value = MagicMock()

            result = execute_query("SHOW TABLES", snowflake_service)
            assert result == [{"col": "val"}]

    def test_no_retry_on_non_token_error(self, snowflake_service):
        from mcp_server_snowflake.utils import execute_query

        generic_error = Exception("syntax error")
        generic_error.errno = 1003

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = generic_error
        snowflake_service.connection.cursor.return_value = mock_cursor

        with pytest.raises(Exception, match="syntax error"):
            execute_query("SELECT BAD", snowflake_service)


def _make_mock_response(status_code, json_data=None, text="error"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    resp.iter_lines.return_value = []
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestCortexAgentRetry:
    def test_retry_on_401(self, snowflake_service):
        from mcp_server_snowflake.cortex_services.tools import query_cortex_agent

        resp_401 = _make_mock_response(401)
        resp_200 = _make_mock_response(200, json_data={"message": {"content": []}})

        snowflake_service._reconnect = MagicMock()

        with (
            patch(
                "mcp_server_snowflake.cortex_services.tools.construct_snowflake_post",
                return_value=("http://host", {"Authorization": "Bearer token"}),
            ) as mock_construct,
            patch(
                "mcp_server_snowflake.cortex_services.tools.requests.post",
                side_effect=[resp_401, resp_200],
            ) as mock_post,
        ):
            asyncio.run(
                query_cortex_agent(
                    snowflake_service=snowflake_service,
                    service_name="agent1",
                    database_name="DB",
                    schema_name="SCHEMA",
                    query="hello",
                )
            )

        snowflake_service._reconnect.assert_called_once()
        assert mock_construct.call_count == 2
        assert mock_post.call_count == 2

    def test_no_retry_on_500(self, snowflake_service):
        from mcp_server_snowflake.cortex_services.tools import query_cortex_agent

        resp_500 = _make_mock_response(500)
        snowflake_service._reconnect = MagicMock()

        with (
            patch(
                "mcp_server_snowflake.cortex_services.tools.construct_snowflake_post",
                return_value=("http://host", {"Authorization": "Bearer token"}),
            ),
            patch(
                "mcp_server_snowflake.cortex_services.tools.requests.post",
                return_value=resp_500,
            ),
        ):
            with pytest.raises(SnowflakeException):
                asyncio.run(
                    query_cortex_agent(
                        snowflake_service=snowflake_service,
                        service_name="agent1",
                        database_name="DB",
                        schema_name="SCHEMA",
                        query="hello",
                    )
                )

        snowflake_service._reconnect.assert_not_called()

    def test_401_on_both_attempts_raises(self, snowflake_service):
        from mcp_server_snowflake.cortex_services.tools import query_cortex_agent

        resp_401_first = _make_mock_response(401)
        resp_401_second = _make_mock_response(401)
        snowflake_service._reconnect = MagicMock()

        with (
            patch(
                "mcp_server_snowflake.cortex_services.tools.construct_snowflake_post",
                return_value=("http://host", {"Authorization": "Bearer token"}),
            ),
            patch(
                "mcp_server_snowflake.cortex_services.tools.requests.post",
                side_effect=[resp_401_first, resp_401_second],
            ),
        ):
            with pytest.raises(SnowflakeException):
                asyncio.run(
                    query_cortex_agent(
                        snowflake_service=snowflake_service,
                        service_name="agent1",
                        database_name="DB",
                        schema_name="SCHEMA",
                        query="hello",
                    )
                )

        snowflake_service._reconnect.assert_called_once()


class TestCortexSearchRetry:
    def test_retry_on_401(self, snowflake_service):
        from mcp_server_snowflake.cortex_services.tools import query_cortex_search

        resp_401 = _make_mock_response(401)
        resp_200 = _make_mock_response(200, json_data={"results": []})

        snowflake_service._reconnect = MagicMock()

        with (
            patch(
                "mcp_server_snowflake.cortex_services.tools.construct_snowflake_post",
                return_value=("http://host", {"Authorization": "Bearer token"}),
            ) as mock_construct,
            patch(
                "mcp_server_snowflake.cortex_services.tools.requests.post",
                side_effect=[resp_401, resp_200],
            ),
        ):
            asyncio.run(
                query_cortex_search(
                    snowflake_service=snowflake_service,
                    service_name="search1",
                    database_name="DB",
                    schema_name="SCHEMA",
                    query="hello",
                )
            )

        snowflake_service._reconnect.assert_called_once()
        assert mock_construct.call_count == 2

    def test_no_retry_on_500(self, snowflake_service):
        from mcp_server_snowflake.cortex_services.tools import query_cortex_search

        resp_500 = _make_mock_response(500)
        snowflake_service._reconnect = MagicMock()

        with (
            patch(
                "mcp_server_snowflake.cortex_services.tools.construct_snowflake_post",
                return_value=("http://host", {"Authorization": "Bearer token"}),
            ),
            patch(
                "mcp_server_snowflake.cortex_services.tools.requests.post",
                return_value=resp_500,
            ),
        ):
            with pytest.raises(SnowflakeException):
                asyncio.run(
                    query_cortex_search(
                        snowflake_service=snowflake_service,
                        service_name="search1",
                        database_name="DB",
                        schema_name="SCHEMA",
                        query="hello",
                    )
                )

        snowflake_service._reconnect.assert_not_called()


class TestCortexAnalystRetry:
    def test_retry_on_401(self, snowflake_service):
        from mcp_server_snowflake.cortex_services.tools import query_cortex_analyst

        resp_401 = _make_mock_response(401)
        resp_200 = _make_mock_response(
            200,
            json_data={"message": {"content": [{"type": "text", "text": "answer"}]}},
        )

        snowflake_service._reconnect = MagicMock()

        with (
            patch(
                "mcp_server_snowflake.cortex_services.tools.construct_snowflake_post",
                return_value=("http://host", {"Authorization": "Bearer token"}),
            ) as mock_construct,
            patch(
                "mcp_server_snowflake.cortex_services.tools.requests.post",
                side_effect=[resp_401, resp_200],
            ),
        ):
            asyncio.run(
                query_cortex_analyst(
                    snowflake_service=snowflake_service,
                    semantic_model="MY_DB.MY_SCH.MY_VIEW",
                    query="what is revenue",
                )
            )

        snowflake_service._reconnect.assert_called_once()
        assert mock_construct.call_count == 2

    def test_no_retry_on_500(self, snowflake_service):
        from mcp_server_snowflake.cortex_services.tools import query_cortex_analyst

        resp_500 = _make_mock_response(500)
        snowflake_service._reconnect = MagicMock()

        with (
            patch(
                "mcp_server_snowflake.cortex_services.tools.construct_snowflake_post",
                return_value=("http://host", {"Authorization": "Bearer token"}),
            ),
            patch(
                "mcp_server_snowflake.cortex_services.tools.requests.post",
                return_value=resp_500,
            ),
        ):
            with pytest.raises(SnowflakeException):
                asyncio.run(
                    query_cortex_analyst(
                        snowflake_service=snowflake_service,
                        semantic_model="MY_DB.MY_SCH.MY_VIEW",
                        query="what is revenue",
                    )
                )

        snowflake_service._reconnect.assert_not_called()


class TestObjectManagerRetry:
    """Tests for token-expiration retry in object manager tool wrappers."""

    def _get_tool_functions(self, snowflake_service):
        """Register tools via initialize_object_manager_tools and return them."""
        from mcp_server_snowflake.object_manager.tools import (
            initialize_object_manager_tools,
        )

        mock_server = MagicMock()
        registered_tools = {}

        def capture_tool(name, description):
            def decorator(func):
                registered_tools[name] = func
                return func
            return decorator

        mock_server.tool = capture_tool
        initialize_object_manager_tools(mock_server, snowflake_service)
        return registered_tools

    def _make_token_error(self):
        err = Exception("token expired")
        err.errno = 390114
        return err

    def test_create_object_retry_on_token_expired(self, snowflake_service):
        tools = self._get_tool_functions(snowflake_service)
        token_error = self._make_token_error()

        with (
            patch(
                "mcp_server_snowflake.object_manager.tools.create_object",
                side_effect=[token_error, "Created Database mydb."],
            ) as mock_create,
            patch(
                "mcp_server_snowflake.object_manager.tools.parse_object",
                return_value=MagicMock(),
            ),
            patch.object(snowflake_service, "_reconnect") as mock_reconnect,
        ):
            result = tools["create_object"](
                object_type="database", target_object=MagicMock()
            )
            assert result == "Created Database mydb."
            mock_reconnect.assert_called_once()
            assert mock_create.call_count == 2

    def test_create_object_no_retry_on_other_error(self, snowflake_service):
        tools = self._get_tool_functions(snowflake_service)
        other_error = SnowflakeException(tool="create_object", message="already exists")

        with (
            patch(
                "mcp_server_snowflake.object_manager.tools.create_object",
                side_effect=other_error,
            ),
            patch(
                "mcp_server_snowflake.object_manager.tools.parse_object",
                return_value=MagicMock(),
            ),
            patch.object(snowflake_service, "_reconnect") as mock_reconnect,
        ):
            with pytest.raises(SnowflakeException):
                tools["create_object"](
                    object_type="database", target_object=MagicMock()
                )
            mock_reconnect.assert_not_called()

    def test_drop_object_retry_on_token_expired(self, snowflake_service):
        tools = self._get_tool_functions(snowflake_service)
        token_error = self._make_token_error()

        with (
            patch(
                "mcp_server_snowflake.object_manager.tools.drop_object",
                side_effect=[token_error, "Dropped Database mydb."],
            ) as mock_drop,
            patch(
                "mcp_server_snowflake.object_manager.tools.parse_object",
                return_value=MagicMock(),
            ),
            patch.object(snowflake_service, "_reconnect") as mock_reconnect,
        ):
            result = tools["drop_object"](
                object_type="database", target_object=MagicMock()
            )
            assert result == "Dropped Database mydb."
            mock_reconnect.assert_called_once()
            assert mock_drop.call_count == 2

    def test_create_or_alter_retry_on_token_expired(self, snowflake_service):
        tools = self._get_tool_functions(snowflake_service)
        token_error = self._make_token_error()

        with (
            patch(
                "mcp_server_snowflake.object_manager.tools.create_or_alter_object",
                side_effect=[token_error, "Created or altered Database mydb."],
            ) as mock_alter,
            patch(
                "mcp_server_snowflake.object_manager.tools.parse_object",
                return_value=MagicMock(),
            ),
            patch.object(snowflake_service, "_reconnect") as mock_reconnect,
        ):
            result = tools["create_or_alter_object"](
                object_type="database", target_object=MagicMock()
            )
            assert result == "Created or altered Database mydb."
            mock_reconnect.assert_called_once()
            assert mock_alter.call_count == 2

    def test_describe_object_retry_on_token_expired(self, snowflake_service):
        tools = self._get_tool_functions(snowflake_service)
        token_error = self._make_token_error()

        with (
            patch(
                "mcp_server_snowflake.object_manager.tools.describe_object",
                side_effect=[token_error, {"name": "mydb"}],
            ) as mock_describe,
            patch(
                "mcp_server_snowflake.object_manager.tools.parse_object",
                return_value=MagicMock(),
            ),
            patch.object(snowflake_service, "_reconnect") as mock_reconnect,
        ):
            result = tools["describe_object"](
                object_type="database", target_object=MagicMock()
            )
            assert result == {"name": "mydb"}
            mock_reconnect.assert_called_once()
            assert mock_describe.call_count == 2
