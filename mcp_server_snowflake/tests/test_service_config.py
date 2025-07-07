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

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from mcp_server_snowflake.server import SnowflakeService


@pytest.fixture
def valid_config_yaml(tmp_path):
    config = {}
    config.update(
        {
            "search_services": [
                {
                    "service_name": "test_search",
                    "description": "Search service that finds test data",
                    "database_name": "TEST_DB",
                    "schema_name": "TEST_SCHEMA",
                }
            ],
            "analyst_services": [
                {
                    "service_name": "test_analyst",
                    "semantic_model": "test_model.yaml",
                    "description": "Analyst service that analyzes test data",
                }
            ],
        }
    )

    config_file = tmp_path / "test_service_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    return config_file


@pytest.fixture
def config_with_optional_fields(tmp_path):
    config = {}
    config.update(
        {
            "search_services": [
                {
                    "service_name": "test_search_with_options",
                    "description": "Search service that finds test data with custom options",
                    "database_name": "TEST_DB",
                    "schema_name": "TEST_SCHEMA",
                    "columns": ["col1", "col2", "col3"],
                    "limit": 25,
                }
            ],
        }
    )

    config_file = tmp_path / "test_optional_fields_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    return config_file


@pytest.fixture
def missing_required_fields(tmp_path):
    config = {}
    config.update(
        {
            "search_services": [
                {
                    "service_name": "test_search",
                }
            ]
        }
    )

    config_file = tmp_path / "missing_fields_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    return config_file


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config = {
        "search_services": [
            {
                "service_name": "test_search",
                "description": "Search service for testing path resolution",
                "database_name": "TEST_DB",
                "schema_name": "TEST_SCHEMA",
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        yaml.dump(config, tmp)
        temp_file = tmp.name

    yield temp_file

    if os.path.exists(temp_file):
        os.unlink(temp_file)


def test_valid_config_loads_successfully(valid_config_yaml):
    """Test that a valid configuration file loads without errors"""
    service = SnowflakeService(
        account_identifier="test_account",
        username="test_user",
        pat="test_pat",
        service_config_file=str(valid_config_yaml),
        transport="stdio",
    )
    assert len(service.search_services) == 1
    assert len(service.analyst_services) == 1

    search_service = service.search_services[0]
    assert search_service["service_name"] == "test_search"
    assert search_service["database_name"] == "TEST_DB"
    assert search_service["schema_name"] == "TEST_SCHEMA"

    analyst_service = service.analyst_services[0]
    assert analyst_service["service_name"] == "test_analyst"
    assert analyst_service["semantic_model"] == "test_model.yaml"


def test_optional_fields_loaded_correctly(config_with_optional_fields):
    """Test that optional columns and limit fields are loaded correctly"""
    service = SnowflakeService(
        account_identifier="test_account",
        username="test_user",
        pat="test_pat",
        service_config_file=str(config_with_optional_fields),
        transport="stdio",
    )

    assert len(service.search_services) == 1
    search_service = service.search_services[0]
    assert search_service["service_name"] == "test_search_with_options"
    assert search_service["columns"] == ["col1", "col2", "col3"]
    assert search_service["limit"] == 25


def test_missing_fields_handled_gracefully(missing_required_fields):
    """Test that missing required fields are handled gracefully by returning None values"""

    service = SnowflakeService(
        account_identifier="test_account",
        username="test_user",
        pat="test_pat",
        service_config_file=str(missing_required_fields),
        transport="stdio",
    )

    assert len(service.search_services) == 1
    search_service = service.search_services[0]
    assert search_service["service_name"] == "test_search"
    assert "description" not in search_service
    assert "database_name" not in search_service
    assert "schema_name" not in search_service


def test_config_file_not_found():
    """Test that non-existent config file raises FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        SnowflakeService(
            account_identifier="test_account",
            username="test_user",
            pat="test_pat",
            service_config_file=str(Path("nonexistent_config.yaml")),
            transport="stdio",
        )


@pytest.mark.parametrize(
    "path_type,path_modifier",
    [
        ("absolute", lambda p: p),  # Use path as-is (already absolute)
        ("relative", lambda p: os.path.relpath(p)),  # Convert to relative path
    ],
)
def test_path_resolution(temp_config_file, path_type, path_modifier):
    """Test that different path types (absolute, relative) are resolved correctly."""
    test_path = path_modifier(temp_config_file)

    service = SnowflakeService(
        account_identifier="test_account",
        username="test_user",
        pat="test_pat",
        service_config_file=test_path,
        transport="stdio",
    )

    assert len(service.search_services) == 1
    assert service.search_services[0]["service_name"] == "test_search"

    assert os.path.isabs(service.service_config_file)
    assert os.path.exists(service.service_config_file)


def test_tilde_path_resolution():
    """Test that tilde (~) paths are expanded correctly."""
    home_dir = Path.home()
    test_config = home_dir / "test_mcp_config.yaml"

    config = {
        "search_services": [
            {
                "service_name": "home_test_search",
                "description": "Search service for testing tilde expansion",
                "database_name": "HOME_TEST_DB",
                "schema_name": "HOME_TEST_SCHEMA",
            }
        ]
    }

    test_config.write_text(yaml.dump(config))

    try:
        tilde_path = "~/test_mcp_config.yaml"

        service = SnowflakeService(
            account_identifier="test_account",
            username="test_user",
            pat="test_pat",
            service_config_file=tilde_path,
            transport="stdio",
        )

        assert len(service.search_services) == 1
        assert service.search_services[0]["service_name"] == "home_test_search"

        assert os.path.isabs(service.service_config_file)
        assert os.path.exists(service.service_config_file)
        assert service.service_config_file == str(test_config)

    finally:
        if test_config.exists():
            test_config.unlink()


@pytest.mark.parametrize(
    "nonexistent_path",
    [
        "./nonexistent_config.yaml",
        "~/nonexistent_config.yaml",
    ],
)
def test_nonexistent_path_raises_error(nonexistent_path):
    """Test that non-existent paths raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        SnowflakeService(
            account_identifier="test_account",
            username="test_user",
            pat="test_pat",
            service_config_file=nonexistent_path,
            transport="stdio",
        )
