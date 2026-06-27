# Data Model: AI Agent Hub

**Date**: 2026-06-27 | **Feature**: 001-ai-agent-hub | **Database**: MongoDB Atlas

---

## Collection: `agent_conversations`

Stores per-user conversation history. Each document is one complete conversation thread (keyed by user + channel + channel-specific ID).

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId (ref: users._id)",
  "channel": "web | telegram | whatsapp",
  "channel_id": "string (chat_id for telegram; phone@c.us for whatsapp; user_id for web)",
  "messages": [
    {
      "role": "user | assistant",
      "content": "string (text) | { type: 'image', url: 'string' }",
      "intent": "text | image | audio_stt | tts | null",
      "model_used": "string (e.g. 'deepseek-v3') | null",
      "response_ms": "integer | null",
      "created_at": "ISODate"
    }
  ],
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

**Indexes**: `{ user_id: 1, channel: 1, channel_id: 1 }` (unique), `{ updated_at: -1 }`

**Validation rules**:
- `channel` must be one of `web`, `telegram`, `whatsapp`
- `messages` max length: 200 (oldest messages pruned to keep context manageable)
- `content` for `image` intent stores a public URL or base64 data URI

---

## Collection: `agent_model_usage`

Tracks daily usage per model per user for quota enforcement.

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId (ref: users._id)",
  "model_id": "string (e.g. 'groq/llama-3.3-70b')",
  "pool": "text | image | audio_stt | tts",
  "date": "string YYYY-MM-DD (UTC)",
  "request_count": "integer",
  "token_count": "integer",
  "last_error": "string | null",
  "last_error_at": "ISODate | null",
  "updated_at": "ISODate"
}
```

**Indexes**: `{ user_id: 1, model_id: 1, date: 1 }` (unique)

**Daily limits (constants in usage.py)**:
| model_id | pool | daily_request_limit | daily_token_limit |
|---|---|---|---|
| `deepseek/deepseek-v3` | text | 1000 | 500000 |
| `groq/llama-3.3-70b` | text | 14400 | 500000 |
| `cerebras/llama-3.3-70b` | text | 5000 | 1000000 |
| `google/gemini-1.5-flash` | text | 1500 | 1000000 |
| `together/qwen2.5-72b` | text | 500 | 200000 |
| `openrouter/mistral-7b` | text | 200 | 100000 |
| `huggingface/zephyr-7b` | text | 100 | 50000 |
| `huggingface/flux-schnell` | image | 100 | null |
| `prodia/sdxl` | image | 50 | null |
| `fal/flux-schnell` | image | 30 | null |
| `groq/whisper-large-v3` | audio_stt | 100 | null |
| `huggingface/whisper-large-v3` | audio_stt | 50 | null |
| `huggingface/kokoro-82m` | tts | 100 | null |
| `elevenlabs/multilingual-v2` | tts | 20 | 10000 |

---

## Collection: `agent_outlook_connections`

Stores Microsoft Graph OAuth2 credentials per user. Tokens are encrypted at rest.

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId (ref: users._id)",
  "ms_account_email": "string",
  "ms_account_name": "string",
  "access_token_enc": "string (Fernet-encrypted)",
  "refresh_token_enc": "string (Fernet-encrypted)",
  "token_expires_at": "ISODate",
  "scopes": ["offline_access", "Calendars.ReadWrite", "User.Read"],
  "connected_at": "ISODate",
  "last_refreshed_at": "ISODate"
}
```

**Indexes**: `{ user_id: 1 }` (unique — one Outlook account per user in v1)

**State transitions**:
- `connected_at` set → active connection
- `refresh_token_enc` set → can auto-refresh
- On disconnect: document deleted; client must re-authorise to reconnect

---

## Collection: `agent_telegram_connections`

Stores Telegram Bot API credentials per user.

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId (ref: users._id)",
  "bot_token_enc": "string (Fernet-encrypted with MS_TOKEN_ENCRYPTION_KEY)",
  "bot_username": "string (e.g. '@MyAssistantBot')",
  "webhook_url": "string",
  "webhook_registered": "boolean",
  "connected_at": "ISODate",
  "last_message_at": "ISODate | null"
}
```

**Indexes**: `{ user_id: 1 }` (unique — one Telegram bot per user)

**State transitions**:
- `webhook_registered: true` → bot is active and receiving messages
- On disconnect: webhook deleted from Telegram API; document deleted from MongoDB

---

## Collection: `agent_whatsapp_sessions`

Stores WAHA WhatsApp session state per user per account. Multiple documents per user (one per linked WhatsApp account).

```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId (ref: users._id)",
  "session_id": "string (e.g. 'user123-account1' — used as WAHA session name)",
  "display_name": "string (user-provided label, e.g. 'Personal')",
  "phone_number": "string | null (populated after QR scan)",
  "status": "PENDING_QR | SCAN_QR_CODE | WORKING | STOPPED | FAILED",
  "waha_session_created": "boolean",
  "webhook_registered": "boolean",
  "created_at": "ISODate",
  "connected_at": "ISODate | null",
  "last_message_at": "ISODate | null"
}
```

**Indexes**: `{ user_id: 1 }`, `{ session_id: 1 }` (unique)

**Status flow**:
```
PENDING_QR → (backend creates WAHA session) → SCAN_QR_CODE → (user scans QR) → WORKING
WORKING → (phone goes offline / logout) → STOPPED
STOPPED → (user reconnects) → SCAN_QR_CODE
```
