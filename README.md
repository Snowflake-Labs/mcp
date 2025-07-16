# Snowflake Cortex AI Model Context Protocol (MCP) Server

<a href="https://emerging-solutions-toolbox.streamlit.app/">
    <img src="https://github.com/user-attachments/assets/aa206d11-1d86-4f32-8a6d-49fe9715b098" alt="image" width="150" align="right";">
</a>

This Snowflake MCP server provides tooling for Snowflake Cortex AI features, bringing these capabilities to the MCP ecosystem. When connected to an MCP Client (e.g. [Claude for Desktop](https://claude.ai/download), [fast-agent](https://fast-agent.ai/), [Agentic Orchestration Framework](https://github.com/Snowflake-Labs/orchestration-framework/blob/main/README.md)), users can leverage these Cortex AI features.

The MCP server currently supports the below Cortex AI capabilities:
- **[Cortex Search](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)**: Query unstructured data in Snowflake as commonly used in Retrieval Augmented Generation (RAG) applications.
- **[Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)**: Query structured data in Snowflake via rich semantic modeling.
- **[Cortex Agent](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)**: (**Coming Soon**) Agentic orchestrator across structured and unstructured data retrieval

# Getting Started

## Service Configuration

A simple configuration file is used to create tooling for the various Cortex AI features. An example can be seen at [services/tools_config.yaml](services/tools_config.yaml) and a template is below. Many Cortex Search and Cortex Analyst services can be added. Ideal descriptions are both highly descriptive and mutually exclusive. The path to this configuration file will be passed to the server and the contents used to create MCP server tools at startup.

```
search_services: # List all Cortex Search services
  - service_name: "<service_name>"
    description: > # Should start with "Search service that ..."
      "<Search services that ...>"
    database_name: "<database_name>"
    schema_name: "<schema_name>"
    columns: [] # Optional: List of columns to return for each relevant result (default: [])
    limit: 10 # Optional: Limit on the number of results to return (default: 10)
  - service_name: "<service_name>"
    description: > # Should start with "Search service that ..."
      "<Search services that ...>"
    database_name: "<database_name>"
    schema_name: "<schema_name>"
    columns: [] # Optional: List of columns to return for each relevant result (default: [])
    limit: 10 # Optional: Limit on the number of results to return (default: 10)
analyst_services: # List all Cortex Analyst semantic models/views
  - service_name: "<service_name>" # Create descriptive name for the service
    semantic_model: "<semantic_yaml_or_view>" # Fully-qualify semantic YAML model or Semantic View
    description: > # Should start with "Analyst service that ..."
      "<Analyst service that ...>"
  - service_name: "<service_name>" # Create descriptive name for the service
    semantic_model: "<semantic_yaml_or_view>" # Fully-qualify semantic YAML model or Semantic View
    description: > # Should start with "Analyst service that ..."
      "<Analyst service that ...>"
```

## Connecting to Snowflake

The MCP server uses the [Snowflake Python Connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect) for all authentication and connection methods. **Please refer to the official Snowflake documentation for comprehensive authentication options and best practices.**

Connection parameters can be passed as CLI arguments and/or environment variables. The server supports all authentication methods available in the Snowflake Python Connector, including:

- Username/password authentication
- Key pair authentication
- OAuth authentication
- Single Sign-On (SSO)
- Multi-factor authentication (MFA)

### Connection Parameters

Connection parameters can be passed as CLI arguments and/or environment variables:

| Parameter | CLI Arguments | Environment Variable | Description |
|-----------|--------------|---------------------|-------------|
| Account | --account | SNOWFLAKE_ACCOUNT | Account identifier (e.g. xy12345.us-east-1) |
| Host | --host | SNOWFLAKE_HOST | Snowflake host URL |
| User | --user, --username | SNOWFLAKE_USER | Username for authentication |
| Password | --password | SNOWFLAKE_PASSWORD | Password or programmatic access token |
| Role | --role | SNOWFLAKE_ROLE | Role to use for connection |
| Warehouse | --warehouse | SNOWFLAKE_WAREHOUSE | Warehouse to use for queries |
| Passcode in Password | --passcode-in-password | - | Whether passcode is embedded in password |
| Passcode | --passcode | SNOWFLAKE_PASSCODE | MFA passcode for authentication |
| Private Key | --private-key | SNOWFLAKE_PRIVATE_KEY | Private key for key pair authentication |
| Private Key File | --private-key-file | SNOWFLAKE_PRIVATE_KEY_FILE | Path to private key file |
| Private Key Password | --private-key-pwd | SNOWFLAKE_PRIVATE_KEY_PWD | Password for encrypted private key |
| Authenticator | --authenticator | - | Authentication type (default: snowflake) |
| Connection Name | --connection-name | - | Name of connection from connections.toml (or config.toml) file |

> [!WARNING]
> **Deprecation Notice**: The CLI arguments `--account-identifier` and `--pat`, as well as the environment variable `SNOWFLAKE_PAT`, are deprecated and will be removed in a future release. Please use `--account` and `--password` (or `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_PASSWORD`) instead.

# Using with MCP Clients

The MCP server is client-agnostic and will work with most MCP Clients that support basic functionality for MCP tools and (optionally) resources. Below are some examples.

## [Claude Desktop](https://support.anthropic.com/en/articles/10065433-installing-claude-for-desktop)
To integrate this server with Claude Desktop as the MCP Client, add the following to your app's server configuration. By default, this is located at
- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
- Windows: %APPDATA%\Claude\claude_desktop_config.json

Set the path to the service configuration file and configure your connection method.

```
{
  "mcpServers": {
    "mcp-server-snowflake": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Snowflake-Labs/mcp",
        "mcp-server-snowflake",
        "--service-config-file",
        "<path to file>/tools_config.yaml",
        "--connection-name",
        "default"
      ]
    }
  }
}
```
## [Cursor](https://www.cursor.com/)
Register the MCP server in cursor by opening Cursor and navigating to Settings -> Cursor Settings ->  MCP. Add the below.
```
{
  "mcpServers": {
    "mcp-server-snowflake": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Snowflake-Labs/mcp",
        "mcp-server-snowflake",
        "--service-config-file",
        "<path to file>/tools_config.yaml",
        "--connection-name",
        "default"
      ]
    }
  }
}
```

Add the MCP server as context in the chat.

<img src="https://sfquickstarts.s3.us-west-1.amazonaws.com/misc/mcp/Cursor.gif" width="800"/>

For troubleshooting Cursor server issues, view the logs by opening the Output panel and selecting Cursor MCP from the dropdown menu.

## [fast-agent](https://fast-agent.ai/)

Update the `fastagent.config.yaml` mcp server section with the configuration file path and connection name.
```
# MCP Servers
mcp:
    servers:
        mcp-server-snowflake:
            command: "uvx"
            args: ["--from", "git+https://github.com/Snowflake-Labs/mcp", "mcp-server-snowflake", "--service-config-file", "<path to file>/tools_config.yaml", "--connection-name", "default"]
```

<img src="https://sfquickstarts.s3.us-west-1.amazonaws.com/misc/mcp/fast-agent.gif" width="800"/>

## Microsoft Visual Studio Code + GitHub Copilot

For prerequisites, environment setup, step-by-step guide and instructions, please refer to this [blog](https://medium.com/snowflake/build-a-natural-language-data-assistant-in-vs-code-with-copilot-mcp-and-snowflake-cortex-ai-04a22a3b0f17).

<img src="https://sfquickstarts.s3.us-west-1.amazonaws.com/misc/mcp/dash-dark-mcp-copilot.gif"/>

# Troubleshooting

## Running MCP Inspector

The [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is suggested for troubleshooting the MCP server. Run the below to launch the inspector.

`npx @modelcontextprotocol/inspector uvx --from "git+https://github.com/Snowflake-Labs/mcp" mcp-server-snowflake --service-config-file "<path_to_file>/tools_config.yaml" --connection-name "default"`

# FAQs

#### How do I connect to Snowflake?

- The MCP server supports all connection methods supported by the Snowflake Python Connector.
See [Connecting to Snowflake with the Python Connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect) for more information.

#### Can I use a Programmatic Access Token (PAT) instead of a password?

- Yes. Pass it to the CLI flag --password or set as environment variable SNOWFLAKE_PASSWORD.

#### How do I try this?

- The MCP server is intended to be used as one part of the MCP ecosystem. Think of it as a collection of tools. You'll need an MCP Client to act as an orchestrator. See the [MCP Introduction](https://modelcontextprotocol.io/introduction) for more information.

#### Where is this deployed? Is this in Snowpark Container Services?

- All tools in this MCP server are managed services, accessible via REST API. No separate remote service deployment is necessary. Instead, the current version of the server is intended to be started by the MCP client, such as Claude Desktop, Cursor, fast-agent, etc. By configuring these MCP client with the server, the application will spin up the server service for you. Future versions of the MCP server may be deployed as a remote service in the future.

#### I'm receiving permission errors from my tool calls.

- If using a Programmatic Access Tokens, note that they do not evaluate secondary roles. When creating them, please select a single role that has access to all services and their underlying objects OR select any role. A new PAT will need to be created to alter this property.

#### How many Cortex Search or Cortex Analysts can I add?

- You may add multiple instances of both services. The MCP Client will determine the appropriate one(s) to use based on the user's prompt.

#### Help! I'm getting an SSLError?

- If your account name contains underscores, try using the dashed version of the URL.
  - Account identifier with underscores: `acme-marketing_test_account`
  - Account identifier with dashes: `acme-marketing-test-account`

# Bug Reports, Feedback, or Other Questions

Please add issues to the GitHub repository.
