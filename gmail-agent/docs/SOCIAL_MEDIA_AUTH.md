# Social Media Authentication Guide

## Overview

Ada 2 cara untuk handle authentication di sistem ini:

### 1. **In-Chat Authentication (Otomatis - Recommended)**

Agent akan otomatis meminta user untuk connect saat tool membutuhkan authentication.

**Cara Kerja:**
```python
# Di server/tools/social_media_poster.py
session = client.create(
    user_id=user_id,
    toolkits=["twitter", "facebook", "instagram"]
    # manage_connections=True (default)
)

tools = session.tools()  # Includes COMPOSIO_MANAGE_CONNECTIONS meta-tool
```

Saat user minta posting tapi belum connect:
1. Agent detect tidak ada connection
2. Agent call `COMPOSIO_MANAGE_CONNECTIONS` 
3. User dapat redirect URL untuk OAuth
4. User click link, authorize di platform
5. Connection active, agent proceed dengan posting

**Keuntungan:**
- ✅ Seamless user experience
- ✅ No manual endpoint management
- ✅ Agent handle flow otomatis

---

### 2. **Manual Authentication (Custom UI)**

Untuk apps yang ingin pre-authenticate atau custom UI flow.

#### **A. Check Connection Status**

**Endpoint:** `GET /toolkits/{user_id}/status`

**Response:**
```json
{
  "user_id": "default",
  "toolkits": {
    "twitter": {
      "name": "Twitter",
      "connected": true,
      "connection_id": "conn_123abc"
    },
    "facebook": {
      "name": "Facebook",
      "connected": false,
      "connection_id": null
    },
    "instagram": {
      "name": "Instagram",
      "connected": false,
      "connection_id": null
    }
  },
  "summary": {
    "twitter": true,
    "facebook": false,
    "instagram": false
  }
}
```

**Example cURL:**
```bash
curl http://localhost:8000/toolkits/default/status
```

---

#### **B. Authorize Toolkit**

**Endpoint:** `POST /toolkits/{user_id}/authorize/{toolkit}`

**Parameters:**
- `user_id`: User ID (e.g., "default")
- `toolkit`: Toolkit slug (e.g., "twitter", "facebook", "instagram")

**Response:**
```json
{
  "success": true,
  "toolkit": "twitter",
  "redirect_url": "https://connect.composio.dev/link/ln_abc123",
  "message": "Please visit the redirect URL to authorize twitter"
}
```

**Example cURL:**
```bash
# Authorize Twitter
curl -X POST http://localhost:8000/toolkits/default/authorize/twitter

# Authorize Facebook
curl -X POST http://localhost:8000/toolkits/default/authorize/facebook

# Authorize Instagram
curl -X POST http://localhost:8000/toolkits/default/authorize/instagram
```

**Flow:**
1. Call authorize endpoint
2. Get `redirect_url`
3. Redirect user ke URL tersebut
4. User authorize di platform
5. User redirected back ke callback URL
6. Check status lagi untuk confirm connection

---

#### **C. Disable In-Chat Auth (Optional)**

Jika ingin handle authentication sepenuhnya via custom UI:

```python
# server/tools/social_media_poster.py
session = client.create(
    user_id=user_id,
    toolkits=["twitter", "facebook", "instagram"],
    manage_connections=False  # Disable in-chat auth
)
```

Then use manual endpoints above untuk manage connections.

---

## Pre-Authentication Pattern

Untuk verify semua required connections sebelum start agent:

```python
from composio import Composio

composio = Composio(api_key="your-api-key")

required_toolkits = ["twitter", "facebook"]

# Create session
session = composio.create(
    user_id="user_123",
    manage_connections=False  # We'll handle auth manually
)

# Check status
toolkits = session.toolkits()
connected = {t.slug for t in toolkits.items if t.connection.is_active}
pending = [slug for slug in required_toolkits if slug not in connected]

print(f"Connected: {connected}")
print(f"Pending: {pending}")

# Authorize pending
for slug in pending:
    connection_request = session.authorize(slug)
    print(f"Authorize {slug}: {connection_request.redirect_url}")
    # Wait for user to complete auth
    connection_request.wait_for_connection(timeout=60000)

print("All toolkits connected!")
```

---

## Important Notes

### Facebook
- ⚠️ **Facebook only supports Facebook Pages**, not personal profiles
- Need to create/manage a Facebook Page first
- Page ID required for posting

### Instagram
- ⚠️ Requires **Business or Creator account**
- Must be connected to a Facebook Page
- Setup Business account at [business.instagram.com](https://business.instagram.com)

### Twitter/X
- ✅ Works with regular Twitter accounts
- No special requirements

---

## Testing Authentication

### 1. Check Current Status
```bash
curl http://localhost:8000/toolkits/default/status
```

### 2. If Not Connected, Authorize
```bash
# Get redirect URL
curl -X POST http://localhost:8000/toolkits/default/authorize/twitter

# Response will include redirect_url - open in browser
```

### 3. Complete OAuth Flow
- Click redirect URL
- Login to platform
- Authorize app
- You'll be redirected back

### 4. Verify Connection
```bash
curl http://localhost:8000/toolkits/default/status
# Should show connected: true
```

---

## Example: Full Flow Frontend Integration

```typescript
// Frontend React/Next.js example

async function connectSocialMedia(toolkit: 'twitter' | 'facebook' | 'instagram') {
  try {
    // 1. Check status first
    const status = await fetch(`/api/toolkits/default/status`).then(r => r.json());
    
    if (status.toolkits[toolkit]?.connected) {
      console.log(`${toolkit} already connected!`);
      return;
    }
    
    // 2. Get authorization URL
    const authResponse = await fetch(
      `/api/toolkits/default/authorize/${toolkit}`,
      { method: 'POST' }
    ).then(r => r.json());
    
    // 3. Open OAuth window
    const authWindow = window.open(
      authResponse.redirect_url,
      '_blank',
      'width=600,height=700'
    );
    
    // 4. Poll for connection (or use webhook)
    const pollInterval = setInterval(async () => {
      const newStatus = await fetch(`/api/toolkits/default/status`).then(r => r.json());
      
      if (newStatus.toolkits[toolkit]?.connected) {
        clearInterval(pollInterval);
        authWindow?.close();
        console.log(`${toolkit} connected successfully!`);
        // Update UI
      }
    }, 2000);
    
  } catch (error) {
    console.error('Auth failed:', error);
  }
}

// Usage
connectSocialMedia('twitter');
```

---

## Troubleshooting

### Connection shows INITIATED but not ACTIVE
- User did not complete OAuth flow
- Link expired (60s default timeout)
- Get new redirect URL and try again

### 401 Unauthorized errors
- Connection expired or revoked
- Re-authorize the toolkit

### Facebook Page ID not found
- Check account is for a Page, not personal profile
- Verify Page access permissions
