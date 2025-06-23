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


def test_valid_config_loads_successfully(valid_config_yaml):
    """Test that a valid configuration file loads without errors"""
    service = SnowflakeService(
        account_identifier="",
        username="",
        pat="",
        service_config_file=str(valid_config_yaml),
        transport="",
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


def test_missing_fields_handled_gracefully(missing_required_fields):
    """Test that missing required fields are handled gracefully by returning None values"""

    service = SnowflakeService(
        account_identifier="",
        username="",
        pat="",
        service_config_file=str(missing_required_fields),
        transport="",
    )

    # Service should load but search service should have missing fields
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
            account_identifier="",
            username="",
            pat="",
            service_config_file=Path("nonexistent_config.yaml"),
            transport="",
        )
