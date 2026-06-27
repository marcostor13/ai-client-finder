# Tasks: AI Agent Hub

**Feature**: 001-ai-agent-hub | **Date**: 2026-06-27
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Format**: `- [ ] [ID] [P?] [Story?] Description — file path`
- **[P]**: Parallelizable (independent files, no blocking deps)
- **[Story]**: User story label (US1–US5)
- No tests — project has no automated test suite

---

## Phase 1: Setup

**Purpose**: Add dependencies, create module skeleton, update env config.

- [x] T001 Add Python dependencies to `backend/requirements.txt`: `msal`, `python-telegram-bot==21.*`, `cryptography` — `backend/requirements.txt`
- [x] T002 [P] Create backend module skeleton with empty `__init__.py` files — `backend/agent_hub/__init__.py`, `backend/agent_hub/models/__init__.py`, `backend/agent_hub/integrations/__init__.py`
- [x] T003 [P] Add all new env vars to `.env.example` with descriptions (DEEPSEEK, CEREBRAS, GEMINI, TOGETHER, OPENROUTER, HUGGINGFACE, PRODIA, FAL, ELEVENLABS, MS_CLIENT_ID/SECRET/REDIRECT_URI/TOKEN_ENCRYPTION_KEY, WAHA_URL, WAHA_API_KEY) — `.env.example`
- [x] T004 Create `docker-compose.yml` at project root with WAHA service (`devlikeapro/waha`, port 3000) and backend service — `docker-compose.yml`

**Checkpoint**: Module directories exist, dependencies listed, env vars documented.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure shared by all user stories. MUST complete before any story work begins.

- [x] T005 Create `ModelResponse` dataclass and `ModelAdapter` abstract base class with `async def generate(messages, **kwargs) -> ModelResponse` — `backend/agent_hub/models/base.py`
- [x] T006 [P] Create daily quota tracker: MongoDB CRUD for `agent_model_usage` collection, `is_quota_exhausted(model_id)`, `increment_usage(model_id, tokens)`, daily limit constants for all 14 models — `backend/agent_hub/models/usage.py`
- [x] T007 [P] Create conversation memory module: CRUD for `agent_conversations` collection, `get_or_create_conversation(user_id, channel, channel_id)`, `append_message(conversation_id, role, content, intent, model_used)`, `get_history(conversation_id, max_messages=20)` — `backend/agent_hub/memory.py`
- [x] T008 Create gateway skeleton: `detect_intent(message) -> Literal["text","image","audio_stt","tts"]` using DeepSeek-V3 chat completions with keyword-heuristic fallback; `POOL_ORDER` dict mapping intent to ordered list of model_ids — `backend/agent_hub/gateway.py`
- [x] T009 Create FastAPI router skeleton with prefix `/agent`, register it in `backend/main.py` via `app.include_router(agent_router, prefix="/agent")` — `backend/agent_hub/routes.py`, `backend/main.py`
- [x] T00 [P] Add `/agent` route to frontend router pointing to `AgentHub` page (lazy import), add "Agent Hub" link to `AppLayout` nav — `frontend/src/App.jsx`, `frontend/src/components/AppLayout.jsx`

**Checkpoint**: Router registered, base classes defined, MongoDB collections accessible, nav link visible.

---

## Phase 3: User Story 1 — Conversational AI Chat (Priority: P1) 🎯 MVP

**Goal**: Full-stack chat: user sends text/audio → gateway detects intent → model pool with fallback → response displayed in browser.

**Independent Test**: Open `/agent`, type a question, receive a response. Disconnect primary model key, resend — response still arrives from fallback. Upload an audio file, receive transcription.

### Backend — Text Model Adapters

- [x] T01 [P] [US1] Implement DeepSeek-V3 adapter using OpenAI-compatible `/v1/chat/completions` at `https://api.deepseek.com`; model `deepseek-chat` — `backend/agent_hub/models/text.py`
- [x] T02 [P] [US1] Implement Groq/Llama-3.3-70B adapter (already have key); reuse pattern from `backend/outbound/llm_router.py`; model `llama-3.3-70b-versatile` — `backend/agent_hub/models/text.py`
- [x] T03 [P] [US1] Implement Cerebras/Llama-3.3-70B adapter; OpenAI-compatible base URL `https://api.cerebras.ai/v1`; model `llama3.3-70b` — `backend/agent_hub/models/text.py`
- [x] T04 [P] [US1] Implement Google Gemini 1.5 Flash adapter via `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent`; translate OpenAI-style messages to Gemini `contents` format — `backend/agent_hub/models/text.py`
- [x] T05 [P] [US1] Implement Together AI / Qwen2.5-72B adapter; OpenAI-compatible base URL `https://api.together.xyz/v1`; model `Qwen/Qwen2.5-72B-Instruct-Turbo` — `backend/agent_hub/models/text.py`
- [x] T06 [P] [US1] Implement OpenRouter / Mistral-7B-free adapter; base URL `https://openrouter.ai/api/v1`; model `mistralai/mistral-7b-instruct:free`; add `HTTP-Referer` header — `backend/agent_hub/models/text.py`
- [x] T07 [P] [US1] Implement HuggingFace Inference API text adapter; POST to `https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta`; handle 503 (model loading) with retry — `backend/agent_hub/models/text.py`

### Backend — Image Model Adapters

- [x] T08 [P] [US1] Implement HuggingFace FLUX.1-schnell image adapter; POST to `https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell`; returns raw PNG bytes; save to temp and return base64 data URI — `backend/agent_hub/models/image.py`
- [x] T09 [P] [US1] Implement Prodia SDXL adapter; submit job via `POST https://api.prodia.com/v1/job`; poll `GET /v1/job/{id}` until status=succeeded; return image URL — `backend/agent_hub/models/image.py`
- [x] T00 [P] [US1] Implement Fal.ai FLUX adapter using `fal-client` async `subscribe("fal-ai/flux/schnell", ...)`; add `fal-client` to `requirements.txt`; return image URL — `backend/agent_hub/models/image.py`, `backend/requirements.txt`

### Backend — Audio Adapters

- [x] T01 [P] [US1] Implement Groq Whisper large-v3 STT adapter; `POST https://api.groq.com/openai/v1/audio/transcriptions`; multipart form-data with model `whisper-large-v3` — `backend/agent_hub/models/audio.py`
- [x] T02 [P] [US1] Implement HuggingFace Whisper STT fallback adapter; POST binary audio to `https://api-inference.huggingface.co/models/openai/whisper-large-v3` — `backend/agent_hub/models/audio.py`
- [x] T03 [P] [US1] Implement HuggingFace Kokoro-82M TTS adapter; POST text to `https://api-inference.huggingface.co/models/hexgrad/Kokoro-82M`; returns wav bytes; encode as base64 data URI — `backend/agent_hub/models/audio.py`
- [x] T04 [P] [US1] Implement ElevenLabs TTS adapter; `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`; default voice Rachel; track character count against 10k/month limit — `backend/agent_hub/models/audio.py`

### Backend — Gateway Routing Logic

- [x] T05 [US1] Implement `route_to_pool(intent, messages, **kwargs) -> ModelResponse` in gateway: iterate `POOL_ORDER[intent]`, skip quota-exhausted models, call adapter, on failure try next, raise `AllModelsExhausted` if all fail; increment usage on success — `backend/agent_hub/gateway.py`

### Backend — API Endpoints (US1)

- [x] T06 [US1] Implement `POST /agent/chat`: authenticate user, get/create web conversation, detect intent, call gateway, append both messages to memory, return `ModelResponse` JSON — `backend/agent_hub/routes.py`
- [x] T07 [US1] Implement `POST /agent/chat/audio`: accept multipart audio file, route to audio_stt pool, return transcription; optionally feed transcription back through text pool for a response — `backend/agent_hub/routes.py`
- [x] T08 [P] [US1] Implement `GET /agent/conversations` (return web channel history) and `DELETE /agent/conversations` (clear it) — `backend/agent_hub/routes.py`

### Frontend — Chat UI

- [x] T09 [US1] Create `AgentHub.jsx` page: full-viewport layout with left panel (chat) and right panel (model status + connections tabs); import `ChatWindow`, `ModelStatus`, `Connections` components — `frontend/src/pages/AgentHub.jsx`
- [x] T00 [US1] Create `ChatWindow.jsx`: scrollable message list (`role: user|assistant`), renders text + `<img>` for image responses; fixed bottom input bar with text field, Send button, audio upload button; calls `POST /agent/chat` via `api.js`; loads history on mount via `GET /agent/conversations` — `frontend/src/components/agent/ChatWindow.jsx`
- [x] T01 [US1] Create `agent.css`: dark glassmorphism layout (deep grey background `#0f0f13`), purple (`#6D28D9`) accent for user bubbles, `backdrop-filter: blur(12px)` panels, Inter/Outfit font import, smooth bubble animations, responsive layout — `frontend/src/agent.css`

**Checkpoint — US1**: Chat fully functional. Text, image, audio all route through gateway with fallback. Conversation history persists. `/agent` page loads with working chat UI.

---

## Phase 4: User Story 2 — Model Status Dashboard (Priority: P2)

**Goal**: Real-time panel showing availability and daily quota state of every configured model.

**Independent Test**: Open `/agent`, toggle status panel. Exhaust one model's quota manually (insert a MongoDB doc with count at limit). Verify that model shows quota_exhausted; others show active.

- [x] T02 [US2] Implement `GET /agent/models/status`: for each model in all pools, query `agent_model_usage` for today, compare against limit constant, determine status (`active|quota_exhausted|error|unknown`), return structured JSON per `contracts/api-endpoints.md` — `backend/agent_hub/routes.py`
- [x] T03 [US2] Create `ModelStatus.jsx`: collapsible right-side panel; four sections (Text / Image / STT / TTS); per-model row with provider logo placeholder, display name, status badge (green=active, yellow=limited, red=quota_exhausted/error), requests_today / daily_limit counter; auto-refresh every 60 s via `GET /agent/models/status`; skeleton loading state — `frontend/src/components/agent/ModelStatus.jsx`
- [x] T04 [US2] Wire `ModelStatus` into `AgentHub.jsx`: toggle button in header, slide-in animation, default collapsed on mobile — `frontend/src/pages/AgentHub.jsx`

**Checkpoint — US2**: Model status panel opens, shows all models, refreshes automatically, correctly reflects quota state.

---

## Phase 5: User Story 3 — Outlook Calendar Integration (Priority: P3)

**Goal**: Connect Microsoft account via OAuth; agent can read/create events from natural language.

**Independent Test**: Click Connect Outlook → complete OAuth → ask "What meetings do I have tomorrow?" → see real events → ask to create event → verify in Outlook.

### Backend — Outlook Integration

- [x] T05 [US3] Implement `outlook.py`: `get_auth_url()` using `msal.ConfidentialClientApplication`; `exchange_code_for_tokens(code)` → encrypt tokens with Fernet and store in `agent_outlook_connections`; `refresh_access_token(user_id)` → auto-refresh before each call; `get_calendar_events(user_id, start, end)` → MS Graph `GET /me/calendarView`; `create_event(user_id, subject, start, end, body)` → MS Graph `POST /me/events` — `backend/agent_hub/integrations/outlook.py`
- [x] T06 [P] [US3] Implement Outlook endpoints: `GET /agent/outlook/auth-url` (returns auth URL), `GET /agent/outlook/callback` (public, exchanges code, redirects to frontend), `GET /agent/outlook/status`, `DELETE /agent/outlook/disconnect` — `backend/agent_hub/routes.py`
- [x] T07 [US3] Add calendar tool-calling to gateway: when intent=`text` and Outlook is connected for user, append system context with today's date; if message mentions calendar/schedule/meeting, call `outlook.py` to fetch events and inject into model context before sending to LLM — `backend/agent_hub/gateway.py`

### Frontend — Outlook Connection UI

- [x] T08 [US3] Create `Connections.jsx`: tab panel with three tabs (Outlook | Telegram | WhatsApp); Outlook tab shows connect/disconnect button, account name when connected, last-sync time; calls `GET /agent/outlook/status` on mount; "Connect Outlook" opens OAuth URL from `GET /agent/outlook/auth-url` in a popup window; "Disconnect" calls `DELETE /agent/outlook/disconnect` — `frontend/src/components/agent/Connections.jsx`
- [x] T09 [US3] Handle OAuth callback redirect: on `AgentHub` mount, detect `?outlook=connected` query param, show success toast notification using existing `NotificationContext`, clear the param from URL — `frontend/src/pages/AgentHub.jsx`

**Checkpoint — US3**: Outlook connected, agent reads and creates events via chat, disconnect removes token, token auto-refreshes.

---

## Phase 6: User Story 4 — Telegram Integration (Priority: P4)

**Goal**: User enters bot token → webhook registered → messages via Telegram get AI replies.

**Independent Test**: Enter bot token in Connections panel → status shows Active → send "Hello" to bot in Telegram → receive AI reply within 10 seconds.

### Backend — Telegram Integration

- [x] T00 [US4] Implement `telegram.py`: `connect_bot(user_id, token)` → validate token via `GET https://api.telegram.org/bot{token}/getMe`, encrypt and store in `agent_telegram_connections`, register webhook via `setWebhook`; `disconnect_bot(user_id)` → `deleteWebhook`, delete doc; `send_reply(token, chat_id, text)` → `sendMessage`; `get_status(user_id)` — `backend/agent_hub/integrations/telegram.py`
- [x] T01 [US4] Implement Telegram endpoints: `POST /agent/telegram/connect`, `GET /agent/telegram/status`, `DELETE /agent/telegram/disconnect`, `POST /agent/telegram/webhook/{user_id}` (public; parse `Update`, look up user by `user_id` path param, route message to gateway, send reply via `telegram.py`) — `backend/agent_hub/routes.py`

### Frontend — Telegram Connection UI

- [x] T02 [US4] Add Telegram tab to `Connections.jsx`: text input for bot token (password-masked), Connect button, status badge (Active/Disconnected), bot username when active, Disconnect button; calls `POST /agent/telegram/connect` on save; polls `GET /agent/telegram/status` on mount — `frontend/src/components/agent/Connections.jsx`

**Checkpoint — US4**: Bot token entered, webhook active, Telegram messages receive AI replies, disconnect removes webhook.

---

## Phase 7: User Story 5 — WhatsApp Integration (Priority: P5)

**Goal**: QR code scan links WhatsApp account(s); messages to linked number get AI replies.

**Independent Test**: Add Account → QR displayed → scan with phone → status WORKING → send message to linked number → AI reply received → second account works independently.

### Backend — WhatsApp / WAHA Integration

- [x] T03 [US5] Implement `whatsapp.py`: `create_session(user_id, display_name)` → generate `session_id`, call WAHA `POST /api/sessions`, register webhook via WAHA `POST /api/sessions/{id}/webhooks`, store in `agent_whatsapp_sessions`; `get_qr(session_id)` → proxy WAHA `GET /api/sessions/{id}/qr`, return base64 PNG; `get_session_status(session_id)` → proxy WAHA `GET /api/sessions/{id}`; `send_message(session_id, chat_id, text)` → WAHA `POST /api/sendText`; `delete_session(session_id)` → WAHA `DELETE /api/sessions/{id}`, delete MongoDB doc — `backend/agent_hub/integrations/whatsapp.py`
- [x] T04 [US5] Implement WhatsApp endpoints: `GET /agent/whatsapp/sessions`, `POST /agent/whatsapp/sessions`, `GET /agent/whatsapp/sessions/{session_id}/qr`, `DELETE /agent/whatsapp/sessions/{session_id}` — all require JWT auth, verify session belongs to user — `backend/agent_hub/routes.py`
- [x] T05 [US5] Implement `POST /agent/whatsapp/webhook` (public): verify `X-Api-Key` header matches `WAHA_API_KEY`; parse payload per `contracts/webhook-payloads.md`; skip if `fromMe=true` or `isGroup=true`; look up user by `session` field in `agent_whatsapp_sessions`; route message body to gateway; send reply via `whatsapp.py` — `backend/agent_hub/routes.py`

### Frontend — WhatsApp Connection UI

- [x] T06 [US5] Add WhatsApp tab to `Connections.jsx`: "Add Account" button → modal with display name input → calls `POST /agent/whatsapp/sessions` → shows QR code image (polls `GET /agent/whatsapp/sessions/{id}/qr` every 3 s until WORKING); session list showing each account with display name, phone number, status badge; Disconnect button per session; handles QR expiry with auto-refresh prompt — `frontend/src/components/agent/Connections.jsx`

**Checkpoint — US5**: QR scan works, messages route through AI, multiple accounts work independently, disconnect stops session.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T07 [P] Add error handling to all gateway adapter calls: catch `httpx.TimeoutException`, `httpx.HTTPStatusError`; log model_id + error; mark model as errored in usage doc; propagate `AllModelsExhausted` to API with 503 + retry-after hint — `backend/agent_hub/gateway.py`, `backend/agent_hub/models/usage.py`
- [x] T08 [P] Add Fernet encryption key generation instructions to `docs/FREE_AI_MODELS_GUIDE.md` and README; generate key command: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` — `docs/FREE_AI_MODELS_GUIDE.md`
- [x] T09 [P] Update `backend/agent_hub/models/usage.py` to auto-reset usage counts for expired days (compare stored `date` with today's UTC date before quota check) — `backend/agent_hub/models/usage.py`
- [x] T00 Prune conversation history in `memory.py` to keep only the last 20 messages per conversation (oldest messages dropped) to prevent unbounded context growth — `backend/agent_hub/memory.py`
- [x] T01 [P] Add WAHA session to `docker-compose.yml` with a persistent volume for session data so WhatsApp sessions survive container restarts — `docker-compose.yml`
- [x] T02 Run quickstart.md validation (all 16 steps) and fix any issues found — `specs/001-ai-agent-hub/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └── Phase 2 (Foundational) ← BLOCKS everything
            ├── Phase 3 (US1 Chat) ← MVP — deliver here
            │       └── Phase 4 (US2 Status)    [can parallelize with US1]
            ├── Phase 5 (US3 Outlook)            [can start after Phase 2]
            ├── Phase 6 (US4 Telegram)           [can start after Phase 2]
            └── Phase 7 (US5 WhatsApp)           [can start after Phase 2]
                        └── Phase 8 (Polish)
```

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational — start first, it's the MVP
- **US2 (P2)**: Depends on US1 backend being live (needs usage data); UI independent
- **US3 (P3)**: Depends only on Foundational; Connections.jsx can be built in parallel with US1
- **US4 (P4)**: Depends only on Foundational; adds a tab to Connections.jsx (US3 base)
- **US5 (P5)**: Depends only on Foundational + WAHA running; adds a tab to Connections.jsx

### Within Each Story

- Models/adapters → Gateway integration → API endpoints → Frontend UI
- T005–T010 (Foundation) must all complete before any story task starts

### Parallel Opportunities per Phase

**Phase 2 (Foundational)**: T006, T007, T010 can all run in parallel with T005
**Phase 3 (US1)**: T011–T024 (all adapters) are fully parallel — 14 tasks can run simultaneously
**Phase 5–7 (Integrations)**: Backend integration files (T035, T040, T043) can all run in parallel if different people

---

## Implementation Strategy

### MVP First (US1 only — ~25 tasks)

1. Complete Phase 1 (T001–T004)
2. Complete Phase 2 (T005–T010)
3. Complete Phase 3 (T011–T031)
4. **Validate**: Chat works, all model pools with fallback, history persists
5. Deploy / demo MVP

### Incremental Delivery

| Milestone | Phases | Cumulative Tasks | Deliverable |
|---|---|---|---|
| MVP | 1–3 | T001–T031 (31 tasks) | Working chat with multi-model AI |
| Status | +4 | T032–T034 | Model status panel visible |
| Outlook | +5 | T035–T039 | Calendar access via chat |
| Telegram | +6 | T040–T042 | Chat via Telegram app |
| WhatsApp | +7 | T043–T046 | Chat via WhatsApp |
| Complete | +8 | T047–T052 | Hardened, polished |

---

## Task Count Summary

| Phase | Story | Tasks | Notes |
|---|---|---|---|
| Phase 1 | Setup | 4 | Sequential, quick |
| Phase 2 | Foundation | 6 | Blocking — do first |
| Phase 3 | US1 Chat | 21 | 14 adapter tasks parallelizable |
| Phase 4 | US2 Status | 3 | Fast |
| Phase 5 | US3 Outlook | 5 | Needs Azure app registration |
| Phase 6 | US4 Telegram | 3 | Needs Telegram bot |
| Phase 7 | US5 WhatsApp | 4 | Needs WAHA running |
| Phase 8 | Polish | 6 | After all stories |
| **Total** | | **52 tasks** | |
