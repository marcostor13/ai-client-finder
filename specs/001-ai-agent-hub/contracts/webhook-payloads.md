# Webhook Payload Contracts: AI Agent Hub

---

## Telegram Webhook Payload

Delivered by Telegram to `POST /agent/telegram/webhook/{user_id}`.

```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 42,
    "from": {
      "id": 987654321,
      "is_bot": false,
      "first_name": "Marcos",
      "username": "marcos_user",
      "language_code": "es"
    },
    "chat": {
      "id": 987654321,
      "first_name": "Marcos",
      "username": "marcos_user",
      "type": "private"
    },
    "date": 1719446400,
    "text": "What meetings do I have tomorrow?"
  }
}
```

**Fields the handler reads**:
- `message.text` — user input (may be absent for voice/photo messages)
- `message.chat.id` — used as `channel_id` for conversation keying and reply target
- `message.from.id` — Telegram user ID (for logging)

**Handler response**: Must return HTTP 200 within 30 s. Agent reply is sent asynchronously via `bot.send_message(chat_id=..., text=...)`.

---

## WhatsApp Webhook Payload (WAHA)

Delivered by WAHA to `POST /agent/whatsapp/webhook`.

```json
{
  "event": "message",
  "session": "user123-account1",
  "payload": {
    "id": "true_51999999999@c.us_ABCDEF123",
    "timestamp": 1719446400,
    "from": "51999999999@c.us",
    "to": "51888888888@c.us",
    "body": "Hola, ¿qué tengo mañana en el calendario?",
    "hasMedia": false,
    "ack": 1,
    "fromMe": false,
    "isGroup": false,
    "chat": {
      "id": "51999999999@c.us"
    }
  }
}
```

**Fields the handler reads**:
- `session` — maps to `agent_whatsapp_sessions.session_id` → identifies user
- `payload.body` — user message text
- `payload.from` — sender phone (`phone@c.us` format) → used as `channel_id` for conversation keying
- `payload.fromMe` — if `true`, message was sent by the linked account; skip to avoid loops
- `payload.isGroup` — if `true`, skip (groups not supported in v1)

**Authentication**: WAHA sends `X-Api-Key: {WAHA_API_KEY}` header. Handler verifies this before processing.

**Handler response**: Must return HTTP 200 quickly. Agent processes and replies asynchronously via WAHA `POST /api/sendText`.

**Send reply payload (to WAHA)**:
```json
{
  "session": "user123-account1",
  "chatId": "51999999999@c.us",
  "text": "Mañana tienes una reunión con Juan a las 3pm."
}
```
