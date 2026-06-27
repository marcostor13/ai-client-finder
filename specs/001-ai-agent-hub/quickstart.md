# Quickstart & Validation Guide: AI Agent Hub

**Feature**: 001-ai-agent-hub | **Date**: 2026-06-27

This guide describes how to validate the AI Agent Hub end-to-end after implementation. It is not a test suite — it is a runnable checklist for confirming each major capability works correctly.

---

## Prerequisites

1. **Backend running** with all new env vars set (see research.md → New Environment Variables)
2. **WAHA running**: `docker run -d -p 3000:3000 devlikeapro/waha`
3. **Frontend running**: `cd frontend && npm run dev`
4. **At least one free API key configured**: Minimum `DEEPSEEK_API_KEY` or `GROQ_API_KEY`
5. **MongoDB Atlas** accessible (existing connection)
6. **Logged in** to the frontend as an existing user

---

## Validation 1: Chat — Basic Text Response

**Steps**:
1. Navigate to `http://localhost:5173/agent`
2. Type: "What is the capital of Peru?" and press Enter
3. Observe the response appears within 10 seconds

**Expected**: Response contains "Lima". The message shows the model used (e.g., "deepseek-v3").

---

## Validation 2: Model Fallback

**Steps**:
1. Set `DEEPSEEK_API_KEY` to an invalid key in `.env`
2. Restart the backend
3. Send a text message from the Agent Hub
4. Observe the response still arrives (from Groq or next model in chain)
5. Open the Model Status panel and confirm DeepSeek shows as "error"

**Expected**: Response arrives from the fallback model. No error shown to the user.

---

## Validation 3: Model Status Panel

**Steps**:
1. Open Agent Hub → click the "Model Status" toggle
2. Observe the panel showing all configured models

**Expected**: At least one model shows "active" in each pool. Quota exhausted models show "quota_exhausted" with request counts.

---

## Validation 4: Image Generation

**Steps**:
1. In the chat, type: "Generate an image of a sunset over the ocean"
2. Wait up to 30 seconds (HuggingFace may cold-start)

**Expected**: An image appears inline in the chat. The model used shows as "huggingface/flux-schnell" or fallback.

---

## Validation 5: Audio Transcription

**Steps**:
1. Click the audio upload button in the chat input
2. Upload a short .mp3 or .wav file (any speech)

**Expected**: Transcription appears as an assistant message within 15 seconds.

---

## Validation 6: Outlook Calendar — Connect

**Prerequisites**: Azure app registered with redirect URI pointing to backend.

**Steps**:
1. Open Agent Hub → Connections tab → Outlook
2. Click "Connect Outlook"
3. Complete Microsoft OAuth flow in the opened window
4. Return to Agent Hub — Outlook should show "Connected" with account email

**Expected**: `agent_outlook_connections` document exists in MongoDB with encrypted tokens.

---

## Validation 7: Outlook Calendar — Query

**Prerequisites**: Outlook connected (Validation 6 passed).

**Steps**:
1. In the chat, type: "What meetings do I have tomorrow?"

**Expected**: Agent returns a list of calendar events for tomorrow (or "no events" if calendar is empty).

---

## Validation 8: Outlook Calendar — Create Event

**Steps**:
1. In the chat, type: "Schedule a 30-minute test meeting called 'QA Check' on [a future date] at 10am"

**Expected**: Agent confirms event created. Verify in Outlook calendar.

---

## Validation 9: Telegram — Connect Bot

**Prerequisites**: Telegram bot created via @BotFather; bot token available.

**Steps**:
1. Open Agent Hub → Connections → Telegram
2. Paste bot token and click "Connect"
3. Status should change to "Active — @YourBotName"

**Expected**: Webhook registered. Check: `curl https://api.telegram.org/bot{TOKEN}/getWebhookInfo` — `url` field should be set.

---

## Validation 10: Telegram — Send & Receive

**Steps**:
1. Open Telegram, find your bot, send: "Hello, who are you?"
2. Wait up to 10 seconds

**Expected**: Bot replies with an AI-generated response.

---

## Validation 11: Telegram — Calendar Query via Telegram

**Prerequisites**: Both Outlook and Telegram connected.

**Steps**:
1. In Telegram, send: "What's on my calendar today?"

**Expected**: Bot replies with today's calendar events from Outlook.

---

## Validation 12: WhatsApp — QR Scan

**Prerequisites**: WAHA running on port 3000.

**Steps**:
1. Open Agent Hub → Connections → WhatsApp
2. Click "Add Account" and enter a display name (e.g., "Personal")
3. A QR code appears
4. Open WhatsApp on your phone → Linked Devices → Link a Device
5. Scan the QR code
6. Session status changes to "Connected" within 30 seconds

**Expected**: `agent_whatsapp_sessions` document has `status: WORKING` and a phone number.

---

## Validation 13: WhatsApp — Send & Receive

**Steps**:
1. From another phone (or WhatsApp Web on another account), send a message to the linked WhatsApp number: "Hola, ¿qué hora es?"
2. Wait up to 15 seconds

**Expected**: The linked WhatsApp account receives an AI-generated reply.

---

## Validation 14: Multiple WhatsApp Accounts

**Steps**:
1. Click "Add Account" again with a different display name
2. Scan a second QR code with a different phone/WhatsApp account
3. Verify both sessions appear in the session list with "Connected" status

**Expected**: Two independent sessions visible; messages from each get independent replies.

---

## Validation 15: Disconnect All

**Steps**:
1. Disconnect Outlook → confirm status shows "Not connected"
2. Disconnect Telegram → verify via Telegram API that webhook is removed
3. Disconnect each WhatsApp session → verify WAHA session is stopped

**Expected**: All integrations show disconnected. Agent responses continue working via web chat.

---

## Validation 16: Conversation Persistence

**Steps**:
1. Have a multi-turn conversation on the web chat (3+ messages)
2. Reload the page

**Expected**: Full conversation history reloads and is visible.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| No AI response | Check backend logs for model errors; verify at least one API key is valid |
| QR code doesn't appear | Check WAHA is running: `curl http://localhost:3000/api/sessions` |
| Telegram webhook not working | Verify `APP_BASE_URL` is reachable from the internet (use ngrok for local dev) |
| Outlook token expired | Delete `agent_outlook_connections` doc and reconnect |
| Image generation times out | HuggingFace cold start can take 60 s; retry after model warms up |
