# Research: AI Agent Hub

**Date**: 2026-06-27 | **Feature**: 001-ai-agent-hub

---

## Decision 1: Intent Detection Strategy

**Decision**: Use a lightweight LLM call (DeepSeek-V3 via `/chat/completions` with a structured system prompt) to classify each incoming message into one of four intents: `text`, `image`, `audio_stt`, `tts`. Fall back to keyword heuristics if the classification call itself fails.

**Rationale**: A dedicated classification call costs ~100 tokens and adds < 300 ms. It is more robust than pure regex and handles ambiguous phrasing ("make a picture of a dog" vs "describe a dog"). Keyword heuristics as a fallback ensure the system degrades gracefully even if the gateway LLM is unavailable.

**Alternatives considered**:
- Pure regex/keyword matching: Fast but brittle for natural language variations.
- Embedding-based classifier: Overkill for 4 classes; adds a vector DB dependency.
- Ask OpenAI every time: Works but costs money and creates a single point of failure.

---

## Decision 2: Text Model Pool — Adapter Interface

**Decision**: Define an abstract base class `ModelAdapter` with a single method `async def generate(messages: list[dict], **kwargs) -> ModelResponse`. Each of the 7 text adapters (DeepSeek, Groq, Cerebras, Gemini, Together, OpenRouter, HuggingFace) implements this interface. The gateway iterates the ordered list, calling each until one succeeds.

**Model pool order (text)**:
| Priority | Model | Provider | Free Tier Limit |
|---|---|---|---|
| 1 | DeepSeek-V3 | DeepSeek API | ~$0 for first 500k tokens/month |
| 2 | Llama-3.3-70B | Groq | 14,400 req/day, 500k tokens/day |
| 3 | Llama-3.3-70B | Cerebras | 1M tokens/day (fast inference) |
| 4 | Gemini 1.5 Flash | Google AI Studio | 15 RPM, 1M tokens/day |
| 5 | Qwen2.5-72B | Together AI | $1 free credit/month |
| 6 | Mistral-7B-Instruct | OpenRouter (free) | Rate-limited, no daily cap stated |
| 7 | Zephyr-7B / Llama | HuggingFace Inference API | Free, slow, rate-limited |

**Rationale**: DeepSeek-V3 is currently among the strongest open-weight models and has a very generous free tier. Groq is already integrated in the project. Cerebras offers extremely fast inference. This ordering maximises response quality before falling to slower/weaker models.

---

## Decision 3: Image Model Pool

**Decision**: Route image generation requests through:
1. **HuggingFace Inference API** — `black-forest-labs/FLUX.1-schnell` (fastest, free, ~4 s)
2. **Prodia** — REST API, free tier, ~5–10 s, SD-XL models
3. **Fal.ai** — Free credits on signup, `fal-ai/flux/schnell`

**Rationale**: FLUX.1-schnell on HuggingFace is currently the best free image model available. Prodia is a reliable fallback with no signup friction. Fal.ai provides an additional fallback.

**API notes**:
- HuggingFace: `POST https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell` with `Authorization: Bearer {HF_TOKEN}`. Returns raw binary (PNG). May queue if model is cold (~30 s wait on first call).
- Prodia: `GET https://api.prodia.com/v1/job` → poll job ID until complete.
- Fal.ai: `fal_client.subscribe("fal-ai/flux/schnell", ...)` — async Python client.

---

## Decision 4: Audio STT Pool

**Decision**:
1. **Groq Whisper large-v3** — already have Groq API key; `POST https://api.groq.com/openai/v1/audio/transcriptions`; free up to 28,800 seconds/day.
2. **HuggingFace Whisper large-v3** — free inference API fallback; slower.

**Constraint**: Files must be sent as multipart form-data. Max 25 MB per file on Groq.

---

## Decision 5: TTS Pool

**Decision**:
1. **Kokoro-82M via HuggingFace** — `hf_hub_download` or Inference API; open source, very high quality, free.
2. **ElevenLabs free tier** — 10,000 characters/month; `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`.

**Rationale**: Kokoro is currently one of the best open-source TTS models. ElevenLabs has the most natural voices but a strict free-tier character cap.

---

## Decision 6: Microsoft Graph OAuth2

**Decision**: Use `msal` (Microsoft Authentication Library for Python) with the Authorization Code Flow. Store access token + refresh token per user, encrypted with AES-256 (Fernet from `cryptography` package). Auto-refresh on each calendar API call.

**Key details**:
- App registration: Azure Portal → App registrations → Redirect URI: `{BACKEND_URL}/agent/outlook/callback`
- Scopes: `offline_access`, `Calendars.ReadWrite`, `User.Read`
- Refresh token lifetime: 90 days sliding window by default (Microsoft). Extends to 14 months if user remains active. No user re-auth needed within 90 days.
- Token storage: `agent_outlook_connections` MongoDB collection; tokens encrypted with `MS_TOKEN_ENCRYPTION_KEY` (32-byte Fernet key).
- MSAL `ConfidentialClientApplication` with `token_cache` in memory; tokens persisted to MongoDB after each refresh.

**Required env vars**: `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_REDIRECT_URI`, `MS_TOKEN_ENCRYPTION_KEY`

**Signup link**: https://portal.azure.com → App registrations (free, no billing required for personal calendar access)

---

## Decision 7: Telegram Integration

**Decision**: Use `python-telegram-bot` v21 in webhook mode. Each user stores their own Bot Token. On connect, the backend calls `https://api.telegram.org/bot{TOKEN}/setWebhook?url={BACKEND_URL}/agent/telegram/webhook/{user_id}`. Incoming updates hit this endpoint and are dispatched to the gateway.

**Rationale**: Webhook mode is more efficient than polling for a server deployment. Each user brings their own bot (created via @BotFather on Telegram — free and instant).

**Key details**:
- Bot creation: Message @BotFather → `/newbot` → receive token (takes ~30 seconds, completely free)
- No rate limits on webhook delivery for standard usage
- Message format: standard Telegram `Update` object; `message.text` is the user input
- Reply: `bot.send_message(chat_id=update.effective_chat.id, text=response)`
- Conversation context keyed by `(user_id, telegram_chat_id)`

**Required env vars**: None (token entered by user via UI; stored encrypted in MongoDB)

---

## Decision 8: WhatsApp via WAHA

**Decision**: Deploy WAHA (WhatsApp HTTP API) as a Docker service. Use the free Core edition (`devlikeapro/waha:latest`). One WAHA session per WhatsApp account. Frontend polls `/agent/whatsapp/sessions/{session_id}/qr` (backend proxies to WAHA) to display QR code. Incoming messages arrive via WAHA webhook → `POST /agent/whatsapp/webhook`.

**Key details**:
- WAHA Core: free, unlimited sessions, no message limits, no phone number required (uses existing WhatsApp account)
- Docker run: `docker run -it --rm -p 3000:3000 devlikeapro/waha`
- Session create: `POST http://localhost:3000/api/sessions` → `{"name": "{session_id}"}`
- QR code: `GET http://localhost:3000/api/sessions/{session_id}/qr` → returns base64 PNG or SVG
- Incoming webhook: configure via `POST http://localhost:3000/api/sessions/{session_id}/webhooks` → URL = `{BACKEND_URL}/agent/whatsapp/webhook`
- Send message: `POST http://localhost:3000/api/sendText` with `{"session": "{session_id}", "chatId": "{phone}@c.us", "text": "{reply}"}`
- Session status: `GET http://localhost:3000/api/sessions/{session_id}` → `{"status": "WORKING" | "SCAN_QR_CODE" | "STOPPED"}`

**Required env vars**: `WAHA_URL` (default `http://localhost:3000`), `WAHA_API_KEY` (optional, set in WAHA config)

**Alternatives considered**:
- Twilio WhatsApp Business API: Requires business verification; not free.
- WhatsApp Cloud API (Meta): Requires business verification; messages go through Meta servers.
- Baileys (Node.js): Would require a separate Node microservice.

---

## Decision 9: Daily Usage Quota Tracking

**Decision**: MongoDB collection `agent_model_usage`. Document structure: `{user_id, model_id, date (YYYY-MM-DD), request_count, token_count, last_error, last_error_at}`. The gateway increments counts on success and records errors on failure. Before each model call, the gateway checks if `request_count >= DAILY_LIMIT[model_id]`. Limits are hardcoded as constants in `usage.py` based on each provider's documented free tier.

**Rationale**: Simple, requires no external service, works within the single-worker constraint.

---

## New Environment Variables

```env
# AI Gateway — Text Models
DEEPSEEK_API_KEY=          # https://platform.deepseek.com → API Keys
CEREBRAS_API_KEY=          # https://cloud.cerebras.ai → API Keys (free)
GEMINI_API_KEY=            # https://aistudio.google.com/apikey (free)
TOGETHER_API_KEY=          # https://api.together.ai → Settings → API Keys
OPENROUTER_API_KEY=        # https://openrouter.ai/keys (free tier available)
HUGGINGFACE_API_KEY=       # https://huggingface.co/settings/tokens (free)

# AI Gateway — Image Models
PRODIA_API_KEY=            # https://app.prodia.com/api (free)
FAL_API_KEY=               # https://fal.ai/dashboard/keys (free credits)

# AI Gateway — Audio/TTS
ELEVENLABS_API_KEY=        # https://elevenlabs.io → Profile → API Keys (free tier)

# Outlook Calendar
MS_CLIENT_ID=              # Azure Portal → App registrations → Application (client) ID
MS_CLIENT_SECRET=          # Azure Portal → App registrations → Certificates & secrets
MS_REDIRECT_URI=           # e.g. https://api.yourdomain.com/agent/outlook/callback
MS_TOKEN_ENCRYPTION_KEY=   # 32-byte base64 Fernet key — generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# WhatsApp (WAHA)
WAHA_URL=http://localhost:3000   # WAHA service URL
WAHA_API_KEY=                    # Optional — set in WAHA if auth enabled
```
