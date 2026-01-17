# API Reference

Complete API documentation for the Gmail Agent backend.

---

## Base URL

```
http://localhost:8000
```

## Authentication

The API uses user-based authentication through Composio. Each user must have an active Gmail connection before executing email actions.

---

## Endpoints

### Health & Info

#### `GET /` - API Information

Returns basic API information.

**Response:**
```json
{
  "message": "Gmail Agent API",
  "version": "2.0.0",
  "docs": "/docs"
}
```

---

#### `GET /health` - Health Check

Check if the API is running.

**Response:**
```json
{
  "status": "healthy"
}
```

---

### Connection Management

#### `POST /connection/exists` - Check Connection

Check if a user has an active Gmail connection.

**Request Body:** None required (uses default user)

**Response:**
```json
{
  "exists": true,
  "user_id": "default"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `exists` | boolean | Whether an active connection exists |
| `user_id` | string | The user identifier |

---

#### `POST /connection/create` - Create Connection

Initiate a new Gmail OAuth connection.

**Request Body:**
```json
{
  "user_id": "default",
  "auth_config_id": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | No | User identifier (default: "default") |
| `auth_config_id` | string | No | Custom auth config ID |

**Response:**
```json
{
  "connection_id": "conn_abc123",
  "redirect_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `connection_id` | string | Unique connection identifier |
| `redirect_url` | string | URL to redirect user for OAuth |

**Error Response (500):**
```json
{
  "detail": "Error message"
}
```

---

#### `POST /connection/status` - Get Connection Status

Get the current status of a connection.

**Request Body:**
```json
{
  "user_id": "default",
  "connection_id": "conn_abc123"
}
```

**Response:**
```json
{
  "status": "ACTIVE",
  "connected": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Connection status (ACTIVE, PENDING, FAILED) |
| `connected` | boolean | Whether connection is active |

---

### Email Actions

#### `POST /actions/send_email` - Send Email

Send an email to a recipient.

**Request Body:**
```json
{
  "user_id": "default",
  "recipient_email": "recipient@example.com",
  "subject": "Meeting Tomorrow",
  "body": "Hi,\n\nJust a reminder about our meeting tomorrow at 10 AM.\n\nBest regards"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | No | User identifier (default: "default") |
| `recipient_email` | string | Yes | Recipient's email address |
| `subject` | string | Yes | Email subject line |
| `body` | string | Yes | Email body content |

**Success Response:**
```json
{
  "successful": true,
  "data": {
    "response": {
      "id": "msg_id_123",
      "threadId": "thread_123",
      "labelIds": ["SENT"]
    }
  }
}
```

**Error Response:**
```json
{
  "successful": false,
  "error": "No connection for user: default"
}
```

---

#### `POST /actions/fetch_emails` - Fetch Emails

Retrieve recent emails from inbox.

**Request Body:**
```json
{
  "user_id": "default",
  "limit": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | No | User identifier (default: "default") |
| `limit` | integer | No | Number of emails to fetch (1-50, default: 5) |

**Success Response:**
```json
{
  "successful": true,
  "data": {
    "data": {
      "messages": [
        {
          "messageId": "msg_123",
          "threadId": "thread_123",
          "subject": "Important Update",
          "sender": "sender@example.com",
          "date": "2026-01-17T10:30:00Z",
          "preview": {
            "body": "Preview text..."
          }
        }
      ]
    }
  }
}
```

---

#### `POST /actions/create_draft` - Create Draft

Create an email draft.

**Request Body:**
```json
{
  "user_id": "default",
  "recipient_email": "recipient@example.com",
  "subject": "Draft Subject",
  "body": "Draft content..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | No | User identifier (default: "default") |
| `recipient_email` | string | Yes | Recipient's email address |
| `subject` | string | Yes | Email subject line |
| `body` | string | Yes | Email body content |

**Success Response:**
```json
{
  "successful": true,
  "data": {
    "response": {
      "id": "draft_123",
      "message": {
        "id": "msg_123",
        "threadId": "thread_123"
      }
    }
  }
}
```

---

### Chat

#### `POST /chat` - AI Chat

Main chatbot endpoint - parses natural language and optionally executes actions.

**Request Body:**
```json
{
  "message": "Send an email to john@example.com about the meeting tomorrow",
  "user_id": "default",
  "auto_execute": true,
  "conversation_history": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | User's message |
| `user_id` | string | No | User identifier (default: "default") |
| `auto_execute` | boolean | No | Whether to auto-execute actions (default: true) |
| `conversation_history` | array | No | Previous conversation for context |

**Response Types:**

### 1. Action Result (Success)

When `auto_execute=true` and action is performed:

```json
{
  "type": "action_result",
  "action": "send_email",
  "intent": {
    "action": "send_email",
    "recipient_email": "john@example.com",
    "recipient_name": "John",
    "subject": "Meeting Tomorrow",
    "body": "Hi John,\n\nJust a reminder about our meeting tomorrow.\n\nBest regards",
    "need_more_info": false
  },
  "result": {
    "successful": true,
    "data": {...}
  }
}
```

### 2. Question (Need More Info)

When the AI needs more information:

```json
{
  "type": "question",
  "message": "What is the recipient's email address?",
  "intent": {
    "action": "send_email",
    "recipient_email": null,
    "subject": null,
    "body": null,
    "need_more_info": true,
    "question": "What is the recipient's email address?"
  }
}
```

### 3. Intent Parsed (No Auto-Execute)

When `auto_execute=false`:

```json
{
  "type": "intent_parsed",
  "intent": {
    "action": "send_email",
    "recipient_email": "john@example.com",
    "subject": "Meeting Tomorrow",
    "body": "...",
    "need_more_info": false
  }
}
```

### 4. Error

```json
{
  "detail": "GROQ_API_KEY not configured"
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 404 | User not found / No connection exists |
| 500 | Internal server error (missing API keys, etc.) |

---

## Examples

### cURL Examples

**Check Connection:**
```bash
curl -X POST http://localhost:8000/connection/exists
```

**Send Email via Chat:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Send email to test@example.com about project update",
    "user_id": "default",
    "auto_execute": true
  }'
```

**Fetch Emails:**
```bash
curl -X POST http://localhost:8000/actions/fetch_emails \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "default",
    "limit": 10
  }'
```

---

## Swagger Documentation

Interactive API documentation is available at:

```
http://localhost:8000/docs
```

Alternative ReDoc documentation:

```
http://localhost:8000/redoc
```
