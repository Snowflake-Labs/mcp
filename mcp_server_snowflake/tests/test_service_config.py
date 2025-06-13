import pytest
import yaml
from pathlib import Path
from mcp_server_snowflake.server import SnowflakeService


@pytest.fixture
def base_config():
    return {"cortex_complete": {"default_model": "snowflake-llama-3.3-70b"}}


@pytest.fixture
def valid_config_yaml(tmp_path, base_config):
    config = base_config.copy()
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
def invalid_yaml(tmp_path):
    config_file = tmp_path / "invalid_service_config.yaml"
    with open(config_file, "w") as f:
        f.write("""
        cortex_complete:
          default_model: "snowflake-llama-3.3-70b"
          search_services: - invalid yaml format
        """)
    return config_file


@pytest.fixture
def missing_required_fields(tmp_path, base_config):
    config = base_config.copy()
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
    service = SnowflakeService(config_path=str(valid_config_yaml))
    assert service.default_complete_model == "snowflake-llama-3.3-70b"
    assert len(service.search_services) == 1
    assert len(service.analyst_services) == 1

    search_service = service.search_services[0]
    assert search_service["service_name"] == "test_search"
    assert search_service["database_name"] == "TEST_DB"
    assert search_service["schema_name"] == "TEST_SCHEMA"

    analyst_service = service.analyst_services[0]
    assert analyst_service["service_name"] == "test_analyst"
    assert analyst_service["semantic_model"] == "test_model.yaml"


def test_invalid_yaml_raises_error(invalid_yaml):
    """Test that invalid YAML format raises YAMLError"""
    with pytest.raises(yaml.YAMLError):
        SnowflakeService(config_path=str(invalid_yaml))


def test_missing_fields_handled_gracefully(missing_required_fields):
    """Test that missing required fields are handled gracefully by returning None values"""
    service = SnowflakeService(config_path=str(missing_required_fields))

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
        SnowflakeService(config_path=Path("nonexistent_config.yaml"))
