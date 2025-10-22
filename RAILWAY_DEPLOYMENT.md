# Railway.com Deployment Guide for Snowflake MCP Server

This guide provides step-by-step instructions for deploying the Snowflake MCP Server on Railway.com and connecting it to MCP clients like Claude Desktop, Cursor, or any other MCP-compatible application.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Part 1: Deploy to Railway.com](#part-1-deploy-to-railwaycom)
- [Part 2: Configure Your MCP Server](#part-2-configure-your-mcp-server)
- [Part 3: Connect MCP Clients](#part-3-connect-mcp-clients)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)

---

## Prerequisites

Before you begin, ensure you have:

1. **Railway.com Account**: Sign up at [railway.app](https://railway.app) (free tier available)
2. **Snowflake Account**: Active Snowflake account with appropriate permissions
3. **Snowflake Credentials**: One of the following authentication methods:
   - Username and password (or Programmatic Access Token)
   - Private key for key pair authentication
4. **MCP Client**: Claude Desktop, Cursor, or another MCP-compatible application

---

## Part 1: Deploy to Railway.com

### Step 1: Fork or Clone the Repository

1. Fork this repository to your GitHub account, or
2. Clone it locally if you prefer to deploy from your local machine

### Step 2: Create a New Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authenticate with GitHub if prompted
5. Select this repository (`Snowflake-Labs/mcp`)

### Step 3: Configure Environment Variables

Railway will automatically detect the `Dockerfile` and configuration. Now you need to set your Snowflake credentials as environment variables.

In your Railway project dashboard:

1. Click on your service
2. Go to the **"Variables"** tab
3. Add the following environment variables:

#### Required Variables (Choose one authentication method)

**Option A: Username/Password Authentication**
```
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password_or_pat
```

**Option B: Key Pair Authentication**
```
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PRIVATE_KEY=your_private_key_content
SNOWFLAKE_PRIVATE_KEY_FILE_PWD=your_key_password
```

#### Optional Variables
```
SNOWFLAKE_ROLE=your_snowflake_role
SNOWFLAKE_WAREHOUSE=your_warehouse_name
SNOWFLAKE_MCP_ENDPOINT=/snowflake-mcp
```

**Important Notes:**
- **Account Identifier**: Use the format `orgname-accountname` or `accountname.region` (e.g., `xy12345.us-east-1`)
- **Private Key**: If using key pair auth, paste the entire private key content (including `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----`)
- **Programmatic Access Token (PAT)**: Can be used instead of password in the `SNOWFLAKE_PASSWORD` variable

### Step 4: Deploy

1. After setting environment variables, Railway will automatically deploy your service
2. Wait for the deployment to complete (usually 2-5 minutes)
3. Once deployed, you'll see a **"Deployment Live"** status

### Step 5: Get Your Service URL

1. In the Railway dashboard, click on your service
2. Go to the **"Settings"** tab
3. Scroll down to **"Networking"**
4. Click **"Generate Domain"** to create a public URL
5. Copy the generated URL (e.g., `https://your-service-name.railway.app`)

**Your MCP server endpoint will be:**
```
https://your-service-name.railway.app/snowflake-mcp
```

---

## Part 2: Configure Your MCP Server

### Customize the Tools Configuration

The MCP server uses a configuration file (`services/tools_config.yaml`) to define which Snowflake Cortex services and tools are available. You have two options to customize this:

#### Option A: Edit Before Deployment (Recommended)

1. Before deploying, edit the `services/tools_config.yaml` file in your repository
2. Add your Cortex Agent, Search, and Analyst services
3. Enable or disable tool groups as needed
4. Commit and push changes to trigger a new deployment

#### Option B: Use Railway Volume (Advanced)

1. In Railway, go to your service settings
2. Add a volume mount for custom configuration
3. Upload your customized `tools_config.yaml`

### Configuration File Structure

```yaml
agent_services: # Cortex Agent services
  - service_name: "customer_support_agent"
    description: "Handles customer support inquiries with context"
    database_name: "SUPPORT_DB"
    schema_name: "AGENT_SCHEMA"

search_services: # Cortex Search services
  - service_name: "product_search"
    description: "Searches product catalog with semantic understanding"
    database_name: "PRODUCTS_DB"
    schema_name: "SEARCH_SCHEMA"

analyst_services: # Cortex Analyst services
  - service_name: "sales_analyst"
    semantic_model: "ANALYTICS_DB.PUBLIC.SALES_SEMANTIC_VIEW"
    description: "Analyzes sales data with natural language queries"

other_services: # Tool groups
  object_manager: True    # Enable Snowflake object management
  query_manager: True     # Enable SQL execution
  semantic_manager: True  # Enable semantic view querying

sql_statement_permissions: # SQL permissions
  - Select: True
  - Create: True
  - Insert: True
  - Update: True
  - Delete: True
  - Drop: True
  # ... see full configuration for all options
```

---

## Part 3: Connect MCP Clients

Once deployed, you can connect any MCP client to your hosted server using the Railway URL.

### Claude Desktop

**Location of config file:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "snowflake-mcp": {
      "url": "https://your-service-name.railway.app/snowflake-mcp"
    }
  }
}
```

**Steps:**
1. Open the config file in a text editor
2. Add the configuration above (replace `your-service-name` with your actual Railway domain)
3. Save the file
4. Restart Claude Desktop
5. Look for the 🔌 icon in Claude Desktop to verify connection

### Cursor

**Steps:**
1. Open Cursor
2. Go to **Settings** → **Cursor Settings** → **MCP**
3. Add the following configuration:

```json
{
  "mcpServers": {
    "snowflake-mcp": {
      "url": "https://your-service-name.railway.app/snowflake-mcp"
    }
  }
}
```

4. Save and restart Cursor
5. Add the MCP server as context in your chat

### fast-agent

**Configuration in `fastagent.config.yaml`:**
```yaml
mcp:
  servers:
    snowflake-mcp:
      url: "https://your-service-name.railway.app/snowflake-mcp"
```

### Any MCP Client (Generic Instructions)

For any MCP client that supports remote servers:

1. Find the MCP server configuration section
2. Add a new server with:
   - **Type**: URL/HTTP/Remote
   - **URL**: `https://your-service-name.railway.app/snowflake-mcp`
   - **Name**: `snowflake-mcp` (or any name you prefer)
3. Save and restart the client

---

## Testing Your Connection

### Method 1: Direct HTTP Test

Use `curl` to test if your server is responding:

```bash
curl https://your-service-name.railway.app/snowflake-mcp
```

**Expected Response:** JSON response with MCP server information

### Method 2: MCP Inspector

Use the MCP Inspector tool to test your deployment:

```bash
npx @modelcontextprotocol/inspector --url https://your-service-name.railway.app/snowflake-mcp
```

The inspector will open a web interface where you can:
- View all available tools
- Test tool execution
- Debug connection issues
- Validate your configuration

### Method 3: Check Railway Logs

1. Go to your Railway project dashboard
2. Click on your service
3. Go to the **"Logs"** tab
4. Look for connection attempts and any errors

---

## Troubleshooting

### Server Not Responding

**Problem**: The MCP server endpoint returns errors or doesn't respond

**Solutions:**
1. Check Railway deployment logs for errors
2. Verify all environment variables are set correctly
3. Ensure your Snowflake account identifier is in the correct format
4. Check that your Snowflake credentials are valid

### Authentication Errors

**Problem**: Getting authentication errors when using tools

**Solutions:**
1. Verify `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and password/key are correct
2. For key pair auth, ensure the private key is properly formatted
3. Check that your Snowflake user has the necessary permissions
4. If using PAT, ensure it has the correct role assigned

### Tools Not Appearing

**Problem**: Expected tools don't show up in MCP client

**Solutions:**
1. Verify `tools_config.yaml` is properly formatted (use YAML validator)
2. Check that Cortex services exist in your Snowflake account
3. Ensure database and schema names are correct
4. Verify your Snowflake role has access to these services
5. Check Railway logs for configuration parsing errors

### Connection Timeout

**Problem**: MCP client can't connect or times out

**Solutions:**
1. Verify the Railway URL is correct and accessible
2. Check that Railway service is running (not sleeping)
3. Ensure Railway has generated a public domain
4. Test the endpoint with `curl` first

### Permission Errors

**Problem**: Tools execute but return permission errors

**Solutions:**
1. Check your Snowflake role has necessary grants
2. If using PAT, note they don't evaluate secondary roles - create PAT with a role that has all needed permissions
3. Verify `sql_statement_permissions` in config allows the operations you need

---

## Security Best Practices

### 1. Use Strong Authentication

- **Prefer Key Pair Authentication** over password authentication for production
- **Rotate credentials regularly** (especially passwords/PATs)
- **Use Programmatic Access Tokens** instead of user passwords when possible

### 2. Limit SQL Permissions

In `tools_config.yaml`, only enable SQL statement types you actually need:

```yaml
sql_statement_permissions:
  - Select: True      # For read operations
  - Describe: True    # For metadata queries
  - Create: False     # Disable if not needed
  - Drop: False       # Disable for safety
  - Delete: False     # Disable if not needed
  - Unknown: False    # Always keep this False
```

### 3. Use Least-Privilege Roles

- Create a dedicated Snowflake role for the MCP server
- Grant only the minimum required permissions
- Don't use ACCOUNTADMIN or other high-privilege roles

### 4. Monitor Usage

- Review Railway logs regularly
- Monitor Snowflake query history for MCP server activity
- Set up alerts for unusual activity

### 5. Protect Environment Variables

- Never commit credentials to Git
- Use Railway's built-in secret management
- Rotate credentials if exposed

### 6. Network Security

- Railway provides HTTPS by default - always use it
- Consider using Railway's private networking for additional security
- Don't expose unnecessary endpoints

---

## Updating Your Deployment

### Update Configuration Only

If you only need to change environment variables:

1. Go to Railway dashboard
2. Update variables in the **"Variables"** tab
3. Railway will automatically restart your service

### Update Code or Configuration File

If you need to update the code or `tools_config.yaml`:

1. Make changes to your repository
2. Commit and push to GitHub
3. Railway will automatically detect changes and redeploy

### Manual Redeploy

To force a redeploy:

1. Go to Railway dashboard
2. Click on your service
3. Click the **"..."** menu
4. Select **"Redeploy"**

---

## Scaling and Performance

### Railway Tiers

- **Free Tier**: Good for testing and personal use
  - $5 credit per month
  - Sleeps after 30 minutes of inactivity

- **Hobby Plan**: $5/month
  - No sleeping
  - More resources

- **Pro Plan**: $20/month
  - Higher limits
  - Better performance

### Preventing Sleep (Free Tier)

If using the free tier, your service may sleep after inactivity. To prevent this:

1. Upgrade to Hobby or Pro plan, or
2. Use a service like UptimeRobot to ping your endpoint periodically

### Performance Tips

- Choose a Railway region close to your Snowflake account region
- Monitor Railway metrics for CPU and memory usage
- Consider upgrading your Railway plan if experiencing performance issues

---

## Cost Estimation

### Railway Costs

- **Free Tier**: $5 credit/month (suitable for light testing)
- **Hobby**: $5/month (recommended for personal use)
- **Pro**: $20/month+ (for production/team use)

### Snowflake Costs

The MCP server will consume Snowflake credits based on:
- Query complexity and frequency
- Cortex AI features used (Search, Analyst, Agent)
- Warehouse size and runtime

**Cost-Saving Tips:**
- Use X-Small warehouses for the MCP server
- Enable auto-suspend on warehouses
- Monitor query patterns and optimize

---

## Additional Resources

- **Snowflake MCP Documentation**: See main [README.md](./README.md)
- **Railway Documentation**: [docs.railway.app](https://docs.railway.app)
- **MCP Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **Snowflake Cortex**: [docs.snowflake.com/cortex](https://docs.snowflake.com/en/user-guide/snowflake-cortex)

---

## Support and Feedback

- **Issues**: Report bugs at [github.com/Snowflake-Labs/mcp/issues](https://github.com/Snowflake-Labs/mcp/issues)
- **Railway Support**: [railway.app/help](https://railway.app/help)
- **Snowflake Support**: Contact your Snowflake account team

---

## Quick Reference

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SNOWFLAKE_ACCOUNT` | Yes | Account identifier | `xy12345.us-east-1` |
| `SNOWFLAKE_USER` | Yes | Username | `my_user` |
| `SNOWFLAKE_PASSWORD` | Yes* | Password or PAT | `mySecureP@ssw0rd` |
| `SNOWFLAKE_PRIVATE_KEY` | Yes* | Private key for auth | `-----BEGIN PRIVATE KEY-----...` |
| `SNOWFLAKE_PRIVATE_KEY_FILE_PWD` | No | Key password | `keyPassword123` |
| `SNOWFLAKE_ROLE` | No | Snowflake role | `MCP_SERVER_ROLE` |
| `SNOWFLAKE_WAREHOUSE` | No | Default warehouse | `COMPUTE_WH` |

\* Either password or private key is required, not both

### Client Configuration Templates

**Claude Desktop:**
```json
{"mcpServers": {"snowflake-mcp": {"url": "https://your-service.railway.app/snowflake-mcp"}}}
```

**Cursor:**
```json
{"mcpServers": {"snowflake-mcp": {"url": "https://your-service.railway.app/snowflake-mcp"}}}
```

**fast-agent:**
```yaml
mcp:
  servers:
    snowflake-mcp:
      url: "https://your-service.railway.app/snowflake-mcp"
```

---

**Congratulations!** You now have a production-ready Snowflake MCP server running on Railway.com. You can access your Snowflake account through any MCP client with the convenience of a centrally hosted service.
