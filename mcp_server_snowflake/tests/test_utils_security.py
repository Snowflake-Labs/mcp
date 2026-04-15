# Copyright 2026 Snowflake Inc.
# SPDX-License-Identifier: Apache-2.0

import pytest

from mcp_server_snowflake.utils import (
    SnowflakeException,
    validate_starts_with_filter,
)


def test_validate_starts_with_filter_accepts_safe_prefix():
    assert validate_starts_with_filter("ORDERS_2026", "list_objects") == "ORDERS_2026"


@pytest.mark.parametrize("prefix", ["foo'; DROP TABLE x;--", "bad/slash", "emoji_😀"])
def test_validate_starts_with_filter_rejects_unsafe_prefix(prefix):
    with pytest.raises(SnowflakeException) as exc_info:
        validate_starts_with_filter(prefix, "list_objects")

    assert "Invalid starts_with filter" in str(exc_info.value)


def test_snowflake_exception_hides_raw_message_by_default(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_MCP_VERBOSE", raising=False)

    error = SnowflakeException(
        tool="query_manager",
        message="SQL compilation error: secret schema name leaked",
    )

    rendered = str(error)
    assert "secret schema name leaked" not in rendered
    assert "Detailed diagnostics are hidden" in rendered


def test_snowflake_exception_shows_raw_message_when_verbose(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_MCP_VERBOSE", "true")

    error = SnowflakeException(
        tool="query_manager",
        message="SQL compilation error: missing table DEMO.PUBLIC.T1",
    )

    rendered = str(error)
    assert "missing table DEMO.PUBLIC.T1" in rendered
