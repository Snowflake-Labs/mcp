# Snowflake Cortex AI Model Context Protocol (MCP) Server

<a href="https://emerging-solutions-toolbox.streamlit.app/">
    <img src="https://github.com/user-attachments/assets/aa206d11-1d86-4f32-8a6d-49fe9715b098" alt="image" width="150" align="right";">
</a>

This Snowflake MCP server provides tooling for Snowflake Cortex AI features, bringing these capabilities to the MCP ecosystem. When connected to an MCP Client (e.g. [Claude for Desktop](https://claude.ai/download), [fast-agent](https://fast-agent.ai/), [Agentic Orchestration Framework](https://github.com/Snowflake-Labs/orchestration-framework/blob/main/README.md)), users can leverage these Cortex AI features.

The MCP server currently supports the below Cortex AI capabilities:
- **[Cortex Search](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)**: Query unstructured data in Snowflake as commonly used in Retrieval Augmented Generation (RAG) applications.
- **[Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)**: Query structured data in Snowflake via rich semantic modeling.
- **[Cortex Complete](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex)**: Simple chat-completion with optional parameters using a number of available LLMs
- **[Cortex Agent](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)**: (**Coming Soon**) Agentic orchestrator across structured and unstructured data retrieval

# Getting Started

## Service Configuration

A simple configuration file is used to create tooling for the various Cortex AI features. An example can be seen at [services/tools_config.yaml](services/tools_config.yaml) and a template is below. Many Cortex Search and Cortex Analyst services can be added. Ideal descriptions are both highly descriptive and mutually exclusive. The path to this configuration file will be passed to the server and the contents used to create MCP server tools at startup.

```
cortex_complete: # Set default model if one is not specified by user in Cortex Complete tool
  default_model: "snowflake-llama-3.3-70b"
search_services: # List all Cortex Search services
  - service_name: "<service_name>"
    description: > # Should start with "Search service that ..."
      "<Search services that ...>"
    database_name: "<database_name>"
    schema_name: "<schema_name>"
  - service_name: "<service_name>"
    description: > # Should start with "Search service that ..."
      "<Search services that ...>"
    database_name: "<database_name>"
    schema_name: "<schema_name>"
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

## Snowflake Account Identifier

A Snowflake username and account identifier will be necessary to connect. From Snowsight, select your user name and [Connect a tool to Snowflake](https://docs.snowflake.com/user-guide/gen-conn-config#using-sf-web-interface-to-get-connection-settings) to obtain your Snowflake account identifier. This will be passed to the server at startup.

## Programmatic Access Token Authentication

The MCP server uses [Snowflake Programmatic Access Token (PAT)](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) for authentication. Follow the [instructions](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens#generating-a-programmatic-access-token) to generate a new PAT for a given user. Be sure to copy the token - it will be passed to the server at startup.

> [!IMPORTANT]
> PATs do not use secondary roles. Either select a specific role that has access to all desired services and their related objects OR select Any of my roles.

# Using with MCP Clients

The MCP server is client-agnostic and will work with most MCP Clients that support basic functionality for MCP tools and (optionally) resources. Below are some examples.

## [Claude Desktop](https://support.anthropic.com/en/articles/10065433-installing-claude-for-desktop)
To integrate this server with Claude Desktop as the MCP Client, add the following to your app's server configuration. By default, this is located at
- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
- Windows: %APPDATA%\Claude\claude_desktop_config.json

Set the path to the service configuration file and values for environment variables SNOWFLAKE_PAT, SNOWFLAKE_ACCOUNT, and SNOWFLAKE_USER.

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
        "<path to file>/tools_config.yaml"
      ],
      "env": {
        "SNOWFLAKE_PAT": "<programmatic_access_token>",
        "SNOWFLAKE_ACCOUNT": "<account-identifier>",
        "SNOWFLAKE_USER": "<username>"
      }
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
        "--account-identifier",
        "<account-identifier>",
        "--username",
        "<username>",
        "--pat",
        "<programmatic_access_token>"
      ]
    }
  }
}
```

Add the MCP server as context in the chat.

<img src="/images/Cursor.gif" width="800" height="500"/>

For troubleshooting Cursor server issues, view the logs by opening the Output panel and selecting Cursor MCP from the dropdown menu.

## [fast-agent](https://fast-agent.ai/)

Update the `fastagent.config.yaml` mcp server section with an updated path to the configuration file.
```
# MCP Servers
mcp:
    servers:
        mcp-server-snowflake:
            command: "uvx"
            args: ["--from", "git+https://github.com/Snowflake-Labs/mcp", "mcp-server-snowflake", "--service-config-file", "<path to file>/tools_config.yaml"]
```

Update the `fastagent.secrets.yaml` mcp server section with environment variables.
```
mcp:
    servers:
        mcp-server-snowflake:
            env:
                SNOWFLAKE_PAT: <add-PAT>
                SNOWFLAKE_ACCOUNT: <add-snowflake-account-identifier>
                SNOWFLAKE_USER: <add-snowflake-username>
```

<img src="/images/fast-agent.gif" width="800" height="500"/>


# Troubleshooting

## Running MCP Inspector

MCP Inspector is suggested for troubleshooting the MCP server. Run the below to launch the inspector. Be sure to set values for service config file, SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_PAT are set accordingly.

`npx @modelcontextprotocol/inspector uvx --from "git+https://github.com/Snowflake-Labs/mcp" mcp-server-snowflake --service-config-file "<path_to_file>/tools_config.yaml" --account-identifier $SNOWFLAKE_ACCOUNT --username $SNOWFLAKE_USER --pat $SNOWFLAKE_PAT`

# FAQs

#### How do I try this?

- The MCP server is intended to be used as one part of the MCP ecosystem. Think of it as a collection of tools. You'll need an MCP Client to act as an orchestrator. See the [MCP Introduction](https://modelcontextprotocol.io/introduction) for more information.

#### Where is this deployed? Is this in Snowpark Container Services?

- All tools in this MCP server are managed services, accessible via REST API. No separate remote service deployment is necessary. Instead, the current version of the server is intended to be started by the MCP client, such as Claude Desktop, Cursor, fast-agent, etc. By configuring these MCP client with the server, the application will spin up the server service for you. Future versions of the MCP server may be deployed as a remote service in the future.

#### I'm receiving permission errors from my tool calls.

- Programmatic Access Tokens do not evaluate secondary roles. When creating them, please select a single role that has access to all services and their underlying objects OR select any role. A new PAT will need to be created to alter this property.

#### How many Cortex Search or Cortex Analysts can I add?

- You may add multiple instances of both services. The MCP Client will determine the appropriate one(s) to use based on the user's prompt.

#### Help! I'm getting an SSLError?

- If your account name contains underscores, try using the dashed version of the URL.
  - Account identifier with underscores: `acme-marketing_test_account`
  - Account identifier with dashes: `acme-marketing-test-account`

# Bug Reports, Feedback, or Other Questions

Please add issues to the GitHub repository.
