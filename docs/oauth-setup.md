# OAuth2 Multi-Tenant Setup Guide

Set up the MCP server so each user authenticates with their own Redmine account.

**Requirements:** Redmine 6.1+ and admin access to register an OAuth application.

## Step 1: Register an OAuth App in Redmine

1. Log in as admin → **Administration → Applications** → **New Application**
2. Fill in:
   - **Name:** `MCP Server`
   - **Redirect URI:** `http://127.0.0.1:PORT/callback` (see redirect URIs below)
   - **Confidential:** Yes
3. Save and note the **Client ID** and **Client Secret**

## Step 2: Configure the MCP Server

```bash
REDMINE_AUTH_MODE=oauth
REDMINE_URL=https://redmine.example.com
REDMINE_MCP_BASE_URL=https://mcp.example.com   # public URL of this server
```

Set these in `.env` (local) or `.env.docker` (Docker). Legacy credentials are not needed in OAuth mode.

## Step 3: Start and Verify

```bash
# Local
uv run python -m redmine_mcp_server.main

# Docker
docker-compose up --build -d
```

Verify discovery endpoints:
```bash
curl http://localhost:8000/.well-known/oauth-protected-resource
curl http://localhost:8000/.well-known/oauth-authorization-server
```

## Step 4: Connect Your MCP Client

MCP clients handle the OAuth flow automatically — when connecting to the server, the client opens a browser for the user to log in to Redmine. No manual token management needed.

### Client Compatibility

| Client | OAuth2 | Notes |
|--------|--------|-------|
| **VS Code** (1.102+) | Yes | Full OAuth 2.1 with PKCE and DCR |
| **Claude Code** | Yes | Auto browser flow on 401. Use `--callback-port` for fixed port |
| **Claude Desktop** | Yes | Via Settings → Connectors. Requires DCR |
| **claude.ai** | Yes | Via Settings → Custom Connectors. |
| **Codex CLI** | Yes | Use `codex mcp login`. Configurable callback port |
| **Kiro** | Yes | Configurable `oauth.redirectUri`. Implementation is newer |
| **Antigravity** | Yes | Full OAuth 2.1 via manual registration. Requires stripping legacy `clientId` from config. |
| **Gemini CLI** | Yes | Via OAuth Proxy (strips `resource` parameter). |

### Redirect URIs

Set this in Redmine's OAuth app (Step 1) to match your client:

| Client | Redirect URI |
|--------|-------------|
| VS Code | `http://127.0.0.1:PORT/callback` |
| Claude Code | `http://127.0.0.1:PORT/oauth/callback` |
| claude.ai | `https://claude.com/api/mcp/auth_callback` |
| Codex CLI | `http://127.0.0.1:PORT/callback` |
| Antigravity | `http://127.0.0.1:33418/` |
| Gemini CLI | `http://127.0.0.1:PORT/` (configurable) |
| Kiro | Configurable via `oauth.redirectUri` |

> **Note on DCR:** Some clients (Claude Desktop, VS Code) expect Dynamic Client Registration. Redmine's Doorkeeper does not support DCR, so you must pre-register the app manually (Step 1) and configure the client with the `client_id`/`client_secret`.

### Gemini CLI & RFC 8707 Compatibility (OAuth Proxy)

The Gemini CLI follows RFC 8707 / RFC 9728 and includes a `resource` parameter in its OAuth handshake. Redmine 6.1 (using Doorkeeper) strictly rejects any unknown parameters, including `resource`, with a `400 Bad Request` error.

To resolve this, the MCP server includes a built-in **OAuth Proxy**:
1. It intercepts the authorization request at `/proxy/authorize`, strips the `resource` field, and redirects to Redmine.
2. It intercepts the token exchange at `/proxy/token`, strips the `resource` field from the POST body, and forwards it to Redmine.

> **Note for Gemini CLI:** You must explicitly define the `redirectUri` in your `mcp_config.json` (e.g., `"redirectUri": "http://127.0.0.1:7777/"`) and ensure this matches the Redirect URI registered in Redmine.

This is handled automatically when `REDMINE_AUTH_MODE=oauth` is enabled.


## Antigravity
### Managing MCP OAuth Credentials in Antigravity

## Adding a Custom MCP Server

1. Click the **"…"** dropdown in the Agent side panel
2. Select **MCP Servers** → **Manage MCP Servers** → **View raw config**
3. Edit `mcp_config.json`:

```json
{
    "mcpServers": {
        "your-server": {
            "serverUrl": "https://your-mcp-server.com/mcp",
            "oauth": {
                "redirectUri": "http://127.0.0.1:33418/",
                "scopes": ["scope1", "scope2"]
            },
            "disabled": false
        }
    }
}
```

4. Save and restart Antigravity — it will prompt for Client ID and Secret on first connect.

> **Note:** The `clientId` and `clientSecret` fields in `mcp_config.json` are **not supported** in the top-level `oauth` object schema for Antigravity. Instead, Antigravity prompts for these credentials in the UI upon the first connection attempt and securely caches them in its internal database.

---

## Resetting / Updating Cached OAuth Credentials

Antigravity stores OAuth credentials in a SQLite database. If you need to change credentials (e.g. you entered wrong ones), you must clear them manually.

### Step 1 — Fully close Antigravity

Make sure Antigravity is not running before editing the database.

### Step 2 — Delete cached credentials

```bash
sqlite3 ~/.config/Antigravity/User/globalStorage/state.vscdb \
  "DELETE FROM ItemTable WHERE key LIKE '%dynamicAuthProvider%';"

sqlite3 ~/.config/Antigravity/User/globalStorage/state.vscdb.backup \
  "DELETE FROM ItemTable WHERE key LIKE '%dynamicAuthProvider%';"
```

### Step 3 — Verify they are gone

```bash
sqlite3 ~/.config/Antigravity/User/globalStorage/state.vscdb \
  "SELECT key FROM ItemTable WHERE key LIKE '%dynamicAuthProvider%';"
```

Should return empty output.

### Step 4 — Restart Antigravity

Antigravity will prompt for Client ID and Secret again on next MCP connect.

---

## Inspecting Cached Credentials

To see all MCP/OAuth related entries currently cached:

```bash
sqlite3 ~/.config/Antigravity/User/globalStorage/state.vscdb \
  "SELECT key FROM ItemTable WHERE key LIKE '%mcp%' OR key LIKE '%oauth%' OR key LIKE '%dynamicAuthProvider%';"
```

---

## Notes

- **Antigravity flows:** Unlike some clients that attempt Dynamic Client Registration (DCR), Antigravity requires manual app registration in Redmine (Step 1). It ignores `clientId`/`clientSecret` keys if manually added to `mcp_config.json` (as they are not part of its recognized schema) and will prompt the user to input them during the initial handshake.
- Cached credentials persist across restarts until manually cleared from the SQLite DB.
- On **macOS**, the database is at `~/Library/Application Support/Antigravity/User/globalStorage/state.vscdb`.
- On **Windows**, it is at `%APPDATA%\Antigravity\User\globalStorage\state.vscdb`.

## Migrating from Legacy Mode

1. Set `REDMINE_AUTH_MODE=oauth` and restart — no downtime needed
2. Remove legacy credentials from `.env` once confirmed working
3. To rollback: set `REDMINE_AUTH_MODE=legacy` (or remove the variable)

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `{"error": "unauthorized"}` | Missing Bearer token | Check client is sending `Authorization` header |
| `{"error": "invalid_token"}` | Token expired/revoked | Test directly: `curl -H "Authorization: Bearer <token>" REDMINE_URL/users/current.json` |
| Discovery endpoints 404 | Not in OAuth mode | Ensure `REDMINE_AUTH_MODE=oauth` is set |
| `400 Bad Request` from Redmine | Parameter mismatch | Usually caused by `resource` parameter; fixed by the built-in Proxy |
| Token works in Redmine but not MCP | Wrong `REDMINE_URL` | In Docker, use internal hostname (e.g., `http://redmine:3000`) |
| "Applications" menu missing | Redmine too old | Requires Redmine 6.1+ |
