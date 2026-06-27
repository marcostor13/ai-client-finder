# API Contract: AI Agent Hub

**Base path**: `/agent` | **Auth**: Bearer JWT (all endpoints unless marked public)

---

## Chat & Gateway

### POST /agent/chat
Send a message to the AI agent. Detects intent and routes to the appropriate model pool.

**Request**
```json
{
  "message": "string (required)",
  "conversation_id": "string | null (omit to start new conversation)"
}
```

**Response 200**
```json
{
  "conversation_id": "string",
  "reply": "string | null (text response)",
  "image_url": "string | null (for image intent)",
  "intent": "text | image | audio_stt | tts",
  "model_used": "string",
  "response_ms": "integer"
}
```

**Response 503** — all models in pool exhausted
```json
{ "detail": "All models unavailable for intent 'text'. Resets at 00:00 UTC." }
```

---

### POST /agent/chat/audio
Transcribe an audio file. Multipart form-data.

**Request**: `multipart/form-data`
- `file`: audio file (mp3, wav, m4a, webm — max 25 MB)
- `conversation_id`: string (optional)

**Response 200**
```json
{
  "conversation_id": "string",
  "transcription": "string",
  "model_used": "groq/whisper-large-v3 | huggingface/whisper-large-v3",
  "response_ms": "integer"
}
```

---

### GET /agent/conversations
Get conversation history for the authenticated user (web channel).

**Response 200**
```json
{
  "conversation_id": "string",
  "messages": [
    {
      "role": "user | assistant",
      "content": "string | { type: 'image', url: 'string' }",
      "intent": "string | null",
      "model_used": "string | null",
      "created_at": "ISO8601"
    }
  ],
  "updated_at": "ISO8601"
}
```

---

### DELETE /agent/conversations
Clear conversation history for the authenticated user (web channel).

**Response 200**: `{ "deleted": true }`

---

### GET /agent/models/status
Get real-time status of all configured models.

**Response 200**
```json
{
  "pools": {
    "text": [
      {
        "model_id": "deepseek/deepseek-v3",
        "display_name": "DeepSeek V3",
        "status": "active | quota_exhausted | error | unknown",
        "requests_today": 42,
        "daily_limit": 1000,
        "last_error": "string | null",
        "last_error_at": "ISO8601 | null"
      }
    ],
    "image": [...],
    "audio_stt": [...],
    "tts": [...]
  },
  "as_of": "ISO8601"
}
```

---

## Outlook Calendar

### GET /agent/outlook/auth-url
Get the Microsoft OAuth2 authorization URL to initiate the connect flow.

**Response 200**: `{ "auth_url": "string" }`

---

### GET /agent/outlook/callback *(public — OAuth redirect target)*
Microsoft redirects here after user authorizes. Stores tokens and redirects browser to frontend.

**Query params**: `code`, `state` (from Microsoft)
**Redirect**: `{FRONTEND_URL}/agent?outlook=connected`

---

### GET /agent/outlook/status
Get current Outlook connection status for the authenticated user.

**Response 200**
```json
{
  "connected": true,
  "account_email": "user@outlook.com",
  "account_name": "John Doe",
  "connected_at": "ISO8601",
  "token_expires_at": "ISO8601"
}
```
or `{ "connected": false }`

---

### DELETE /agent/outlook/disconnect
Disconnect Outlook and delete stored tokens.

**Response 200**: `{ "disconnected": true }`

---

## Telegram

### POST /agent/telegram/connect
Register a Telegram bot token and set up webhook.

**Request**: `{ "bot_token": "string" }`

**Response 200**
```json
{
  "connected": true,
  "bot_username": "@MyAssistantBot",
  "webhook_url": "string"
}
```

**Response 400**: `{ "detail": "Invalid bot token" }`

---

### GET /agent/telegram/status
Get Telegram connection status.

**Response 200**: `{ "connected": true, "bot_username": "@MyAssistantBot", "webhook_registered": true }` or `{ "connected": false }`

---

### DELETE /agent/telegram/disconnect
Remove Telegram bot webhook and delete stored token.

**Response 200**: `{ "disconnected": true }`

---

### POST /agent/telegram/webhook/{user_id} *(public — Telegram delivery)*
Receives updates from Telegram. Authenticates via comparing `user_id` path param against stored connections.

**Request**: Telegram `Update` object (standard Telegram Bot API format)
**Response 200**: `{}` (Telegram expects HTTP 200 within 30 s)

---

## WhatsApp (WAHA)

### GET /agent/whatsapp/sessions
List all WhatsApp sessions for the authenticated user.

**Response 200**
```json
{
  "sessions": [
    {
      "session_id": "string",
      "display_name": "Personal",
      "phone_number": "+51999999999 | null",
      "status": "WORKING | SCAN_QR_CODE | STOPPED | PENDING_QR",
      "connected_at": "ISO8601 | null"
    }
  ]
}
```

---

### POST /agent/whatsapp/sessions
Create a new WhatsApp session (generates a WAHA session and returns session_id).

**Request**: `{ "display_name": "string (e.g. 'Personal')" }`

**Response 201**: `{ "session_id": "string", "status": "PENDING_QR" }`

---

### GET /agent/whatsapp/sessions/{session_id}/qr
Get the current QR code for an unlinked session. Frontend polls this every 3 s until status = WORKING.

**Response 200**: `{ "qr_base64": "string (PNG base64)", "status": "SCAN_QR_CODE | WORKING | STOPPED" }`

**Response 404**: session not found or not owned by user

---

### DELETE /agent/whatsapp/sessions/{session_id}
Disconnect and delete a WhatsApp session.

**Response 200**: `{ "deleted": true }`

---

### POST /agent/whatsapp/webhook *(public — WAHA delivery)*
Receives incoming WhatsApp messages from WAHA. Authenticated by shared `WAHA_API_KEY` header.

**Request**: WAHA webhook payload (see webhook-payloads.md)
**Response 200**: `{}`
