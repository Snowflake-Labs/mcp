# Quick Start: Deploy Snowflake MCP Server to Railway.com

Get your Snowflake MCP server running on Railway.com in under 10 minutes!

## Prerequisites

- Railway.com account (sign up at [railway.app](https://railway.app))
- Snowflake account credentials
- GitHub account (for repository deployment)

## Step 1: Deploy to Railway (2 minutes)

### Option A: One-Click Deploy (Easiest)

Click the button below to deploy directly to Railway:

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/deploy)

**Note:** If the button doesn't work, use Option B below.

### Option B: Manual Deploy

1. Go to [railway.app](https://railway.app) and sign in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Fork this repository first, then select your fork
6. Railway will automatically detect the configuration and start building

## Step 2: Configure Environment Variables (3 minutes)

Once the project is created:

1. Click on your service in the Railway dashboard
2. Go to the **"Variables"** tab
3. Click **"+ New Variable"** and add the following:

### Minimum Required Variables:

```
SNOWFLAKE_ACCOUNT     =  your_account_identifier
SNOWFLAKE_USER        =  your_username
SNOWFLAKE_PASSWORD    =  your_password_or_pat
```

**Example:**
```
SNOWFLAKE_ACCOUNT     =  xy12345.us-east-1
SNOWFLAKE_USER        =  john_doe
SNOWFLAKE_PASSWORD    =  MySecurePassword123
```

### Optional But Recommended:

```
SNOWFLAKE_ROLE        =  your_role_name
SNOWFLAKE_WAREHOUSE   =  your_warehouse_name
```

4. Click **"Deploy"** or wait for automatic deployment

## Step 3: Get Your Server URL (1 minute)

1. In Railway dashboard, click on your service
2. Go to **"Settings"** tab
3. Scroll to **"Networking"** section
4. Click **"Generate Domain"**
5. Copy the generated URL (e.g., `https://snowflake-mcp-production.railway.app`)

Your MCP server endpoint is:
```
https://your-domain.railway.app/snowflake-mcp
```

## Step 4: Connect Your MCP Client (2 minutes)

### For Claude Desktop:

1. Open config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add this configuration (replace with your Railway URL):
```json
{
  "mcpServers": {
    "snowflake": {
      "url": "https://your-domain.railway.app/snowflake-mcp"
    }
  }
}
```

3. Save and restart Claude Desktop
4. Look for the 🔌 icon to verify connection

### For Cursor:

1. Open Cursor
2. Go to **Settings** → **Cursor Settings** → **MCP**
3. Add the same configuration as above
4. Save and restart Cursor

## Step 5: Test Your Connection (1 minute)

Test your deployment with curl:

```bash
curl https://your-domain.railway.app/snowflake-mcp
```

You should see a JSON response with MCP server information.

## Troubleshooting

### Build Failed
- Check Railway logs in the "Deployments" tab
- Verify all required files are in your repository
- Ensure `railway.json` is present

### Can't Connect to Snowflake
- Verify your `SNOWFLAKE_ACCOUNT` format is correct
- Check username and password are accurate
- Ensure your Snowflake user has necessary permissions

### MCP Client Can't Connect
- Verify the Railway domain is accessible in browser
- Check that `/snowflake-mcp` is added to the URL
- Ensure Railway service is running (not sleeping)

### No Tools Appearing
- Check `services/tools_config.yaml` is configured
- Verify Cortex services exist in your Snowflake account
- Check Railway logs for configuration errors

## Next Steps

1. **Customize Configuration**: Edit `services/tools_config.yaml` to add your Cortex services
2. **Secure Your Deployment**: Review security best practices in [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md)
3. **Monitor Usage**: Check Railway logs and Snowflake query history
4. **Scale Up**: Upgrade Railway plan if needed for better performance

## Getting Help

- **Detailed Guide**: See [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md) for comprehensive instructions
- **General Documentation**: See [README.md](./README.md) for MCP server features
- **Issues**: Report problems at [GitHub Issues](https://github.com/Snowflake-Labs/mcp/issues)

## Cost Estimate

- **Railway Free Tier**: $5 credit/month (good for testing)
- **Railway Hobby**: $5/month (recommended for personal use)
- **Snowflake**: Varies by usage (use X-Small warehouse to minimize costs)

---

**You're all set!** Your Snowflake MCP server is now running in the cloud and accessible from any MCP client.

For production deployments, see the complete [Railway Deployment Guide](./RAILWAY_DEPLOYMENT.md) for security best practices and advanced configuration.
