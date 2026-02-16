# Tools Gateway Testing Guide

This guide helps you test the Composio Tools integration with Agenta.

## Prerequisites

1. **Composio API Key**: Sign up at [composio.dev](https://composio.dev) and get your API key
2. **Agenta running locally**: Ensure the API is running on `http://localhost`
3. **HTTP client**: Use VS Code REST Client extension or similar

## Environment Setup

### 1. Set Composio API Key

Add to your environment variables or `.env` file:

```bash
export COMPOSIO_API_KEY="your-composio-api-key-here"
```

### 2. Configure Agenta

The Composio adapter will be automatically initialized with your API key. Verify in:
- `api/entrypoints/routers.py` - Tools router should be mounted
- Adapter registry should include Composio

## Integration Options

Here are the best integrations to test with, ranked by ease of use:

### ⭐ Recommended for Testing

#### 1. **GitHub** (Easiest to test)
- **Why**: Free, no trial limits, well-documented actions
- **Popular Actions**:
  - `CREATE_ISSUE` - Create GitHub issues
  - `LIST_REPOS` - List your repositories
  - `CREATE_PR` - Create pull requests
  - `GET_REPO` - Get repository details
- **Setup**: Just OAuth with your GitHub account

#### 2. **Slack** (Great for notifications)
- **Why**: Free tier, instant feedback, useful for workflows
- **Popular Actions**:
  - `SEND_MESSAGE` - Send messages to channels
  - `LIST_CHANNELS` - List Slack channels
  - `CREATE_CHANNEL` - Create new channels
- **Setup**: OAuth with your Slack workspace

#### 3. **Google Drive** (File operations)
- **Why**: Free tier, useful for document workflows
- **Popular Actions**:
  - `UPLOAD_FILE` - Upload files
  - `LIST_FILES` - List files in Drive
  - `CREATE_FOLDER` - Create folders
  - `SHARE_FILE` - Share files
- **Setup**: OAuth with Google account

### 🎯 Good for Advanced Testing

#### 4. **Gmail** (Email automation)
- **Why**: Free, real-world use case
- **Popular Actions**:
  - `SEND_EMAIL` - Send emails
  - `SEARCH_EMAIL` - Search inbox
  - `READ_EMAIL` - Read email content
- **Setup**: OAuth with Gmail account
- **Note**: May trigger security alerts on first use

#### 5. **Notion** (Knowledge base)
- **Why**: Free tier available, popular tool
- **Popular Actions**:
  - `CREATE_PAGE` - Create pages
  - `SEARCH_PAGES` - Search Notion workspace
  - `UPDATE_PAGE` - Update page content
- **Setup**: OAuth with Notion workspace

#### 6. **Linear** (Project management)
- **Why**: Developer-friendly, clean API
- **Popular Actions**:
  - `CREATE_ISSUE` - Create issues
  - `LIST_ISSUES` - List issues
  - `UPDATE_ISSUE` - Update issue status
- **Setup**: OAuth with Linear workspace

### 💼 Enterprise/Paid Services

#### 7. **Salesforce** (CRM)
- **Requirement**: Salesforce account (trial available)
- **Actions**: Create/update leads, contacts, opportunities

#### 8. **HubSpot** (Marketing)
- **Requirement**: HubSpot account (free tier available)
- **Actions**: Manage contacts, deals, emails

## Testing Workflow

### Step 1: Browse Catalog

```http
GET {{base_url}}/catalog/providers/composio/integrations?search=github&limit=10
```

This shows available integrations with:
- `actions_count` - Number of available actions
- `auth_schemes` - Required authentication methods
- `connections_count` - Your existing connections

### Step 2: Explore Actions

```http
GET {{base_url}}/catalog/providers/composio/integrations/github/actions?important=true
```

Set `important=true` to see only the most commonly used actions.

### Step 3: Get Action Schema

```http
GET {{base_url}}/catalog/providers/composio/integrations/github/actions/CREATE_ISSUE
```

Returns:
- `input_schema` - Required parameters
- `output_schema` - Expected response format
- `description` - What the action does

### Step 4: Create Connection

```http
POST {{base_url}}/connections/
{
  "connection": {
    "slug": "my-github",
    "name": "My GitHub Account",
    "provider_key": "composio",
    "integration_key": "github",
    "data": {
      "callback_url": "http://localhost/api/preview/tools/connections/callback"
    }
  }
}
```

Response includes:
- `connection.id` - Connection ID
- `connection.status.redirect_url` - OAuth URL (open in browser)

### Step 5: Complete OAuth

1. Copy the `redirect_url` from the response
2. Open it in your browser
3. Authorize the integration
4. You'll be redirected back (callback URL)

### Step 6: Poll Connection Status

```http
GET {{base_url}}/connections/{connection_id}
```

Wait until:
- `connection.flags.is_active` = `true`
- `connection.flags.is_valid` = `true`

### Step 7: Execute Tool

```http
POST {{base_url}}/call
{
  "id": "unique-call-id",
  "name": "tools.composio.github.CREATE_ISSUE.my-github",
  "arguments": {
    "owner": "your-username",
    "repo": "your-repo",
    "title": "Test Issue",
    "body": "Created via Agenta Tools!"
  }
}
```

Tool name format: `tools.{provider}.{integration}.{action}.{connection_slug}`

## Common Issues & Solutions

### OAuth Redirect Not Working

**Problem**: Callback URL returns 404

**Solution**:
1. Ensure the tools router is mounted at `/api/preview/tools`
2. Check that `callback_connection` endpoint is registered
3. Use the full URL including protocol: `http://localhost:port/...`

### Connection Stays Invalid

**Problem**: `is_valid` remains `false` after OAuth

**Solution**:
1. Check Composio dashboard for connection status
2. Verify API key is correct
3. Try refreshing: `POST /connections/{id}/refresh`
4. Some integrations need manual approval in their settings

### Tool Execution Fails

**Problem**: Tool call returns error

**Solution**:
1. Verify connection is active: `GET /connections/{id}`
2. Check action schema: `GET /catalog/.../actions/{action}`
3. Ensure all required arguments are provided
4. Check argument types match schema

## Example Test Sequence

Here's a complete test with GitHub (recommended first test):

```bash
# 1. List GitHub actions
GET /catalog/providers/composio/integrations/github/actions?important=true

# 2. Create connection
POST /connections/
# Copy redirect_url and open in browser

# 3. Poll until active
GET /connections/{connection_id}
# Wait for is_valid=true

# 4. List your repos (read-only, safe to test)
POST /call
{
  "id": "test-001",
  "name": "tools.composio.github.LIST_REPOS.my-github",
  "arguments": {
    "type": "owner"
  }
}

# 5. Create test issue (creates real data)
POST /call
{
  "id": "test-002",
  "name": "tools.composio.github.CREATE_ISSUE.my-github",
  "arguments": {
    "owner": "your-username",
    "repo": "test-repo",
    "title": "Test from Agenta",
    "body": "This is a test"
  }
}
```

## API Endpoints Summary

### Catalog
- `GET /catalog/providers` - List providers
- `GET /catalog/providers/{provider}` - Get provider details
- `GET /catalog/providers/{provider}/integrations` - List integrations
- `GET /catalog/providers/{provider}/integrations/{integration}/actions` - List actions
- `GET /catalog/providers/{provider}/integrations/{integration}/actions/{action}` - Get action schema

### Connections
- `POST /connections/` - Create connection (initiates OAuth)
- `GET /connections/{id}` - Get connection status
- `POST /connections/query` - Query connections with filters
- `POST /connections/{id}/refresh` - Refresh connection
- `DELETE /connections/{id}` - Delete connection
- `GET /connections/callback` - OAuth callback handler

### Tools
- `POST /query` - Query available tools (actions × connections)
- `POST /call` - Execute a tool action

## Next Steps

1. **Start with GitHub**: Easiest to test, no trial limits
2. **Test Slack**: Great for seeing immediate results
3. **Try Gmail**: Real-world email automation use case
4. **Explore more**: Browse the catalog for 100+ integrations

## Need Help?

- Check Composio docs: https://docs.composio.dev
- View action schemas via the catalog endpoints
- Test with `important=true` to see only common actions
