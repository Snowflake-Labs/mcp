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

from mcp_server_snowflake.query_manager.tools import get_statement_type, validate_sql_type


class TestGetStatementType:
    def test_simple_select(self):
        assert get_statement_type("SELECT 1") == "Select"

    def test_insert(self):
        assert get_statement_type("INSERT INTO t VALUES (1)") == "Insert"

    def test_update(self):
        assert get_statement_type("UPDATE t SET col = 1") == "Update"

    def test_delete(self):
        assert get_statement_type("DELETE FROM t WHERE id = 1") == "Delete"

    def test_create_table(self):
        assert get_statement_type("CREATE TABLE t (id INT)") == "Create"

    def test_drop_table(self):
        assert get_statement_type("DROP TABLE t") == "Drop"

    def test_unparseable_returns_unknown(self):
        assert get_statement_type("NOT VALID SQL !!!") == "Unknown"

    def test_try_parse_json_colon_path_with_cast(self):
        assert get_statement_type("SELECT TRY_PARSE_JSON(col):name::string FROM t") == "Select"

    def test_parse_json_colon_path_with_cast(self):
        assert get_statement_type("SELECT PARSE_JSON(col):name::string FROM t") == "Select"

    def test_column_colon_path_with_cast(self):
        assert get_statement_type("SELECT v:city::string FROM t") == "Select"


class TestValidateSqlType:
    def test_select_allowed(self):
        allow = ["select"]
        deny: list[str] = []
        stmt_type, valid = validate_sql_type("SELECT 1", allow, deny)
        assert stmt_type == "Select"
        assert valid is True

    def test_select_disallowed(self):
        allow: list[str] = []
        deny = ["select"]
        stmt_type, valid = validate_sql_type("SELECT 1", allow, deny)
        assert stmt_type == "Select"
        assert valid is False

    def test_all_escape_hatch(self):
        _, valid = validate_sql_type("DROP TABLE t", ["all"], [])
        assert valid is True

    def test_unknown_blocked_by_default(self):
        """Unparseable SQL must be blocked when unknown is not in allow list."""
        _, valid = validate_sql_type("NOT VALID SQL !!!", ["select"], [])
        assert valid is False

    def test_unknown_allowed_when_configured(self):
        _, valid = validate_sql_type("NOT VALID SQL !!!", ["select", "unknown"], [])
        assert valid is True

    def test_empty_lists_deny_all(self):
        _, valid = validate_sql_type("SELECT 1", [], [])
        assert valid is False

    def test_try_parse_json_colon_path_is_allowed_as_select(self):
        sql = "SELECT TRY_PARSE_JSON(col):name::string FROM t"
        stmt_type, valid = validate_sql_type(sql, ["select"], [])
        assert stmt_type == "Select", (
            f"Expected 'Select' but got '{stmt_type}' — "
            "dialect='snowflake' is likely missing from sqlglot.parse_one()"
        )
        assert valid is True

    def test_column_colon_path_is_allowed_as_select(self):
        sql = "SELECT v:city::string FROM locations"
        stmt_type, valid = validate_sql_type(sql, ["select"], [])
        assert stmt_type == "Select", (
            f"Expected 'Select' but got '{stmt_type}' — "
            "dialect='snowflake' is likely missing from sqlglot.parse_one()"
        )
        assert valid is True
