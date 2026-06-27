# Free AI Models Guide

**Purpose**: Reference for all free-tier AI APIs integrated (or available for integration) in the AI Agent Hub.
**Last updated**: 2026-06-27

---

## How to Read This Guide

Each entry includes:
- **Model**: Model name and capability
- **Provider / API**: Service name and API endpoint style
- **Free Tier**: What you get for free
- **How to Get the Key**: Step-by-step signup instructions
- **Quota Reset**: When limits refresh

---

## TEXT / LLM MODELS

---

### 1. DeepSeek-V3
**Capability**: General text generation, reasoning, code, multilingual. Benchmark-leading open-weight model.

**Provider**: DeepSeek API (`https://api.deepseek.com`)

**Free Tier**: ~$5 free credits on signup; ~$0.27/M tokens input. Effectively free for low-volume use. Also has a free web playground.

**API Style**: OpenAI-compatible (`/v1/chat/completions`)

**How to get the key**:
1. Go to [https://platform.deepseek.com](https://platform.deepseek.com)
2. Click "Sign Up" → create account (email + password or Google)
3. Navigate to **API Keys** in the left sidebar
4. Click **"Create API Key"** → copy the key
5. Set: `DEEPSEEK_API_KEY=sk-...`

**Quota Reset**: Credit-based (not time-based)

**Example call**:
```python
import httpx
response = await httpx.AsyncClient().post(
    "https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "Hello"}]}
)
```

---

### 2. Groq — Llama 3.3 70B
**Capability**: Ultra-fast inference on open-weight models. Best free-tier throughput.

**Provider**: Groq Cloud (`https://api.groq.com`)

**Free Tier**: 14,400 requests/day, 500,000 tokens/day, 6,000 tokens/minute. **Already in project.**

**API Style**: OpenAI-compatible

**How to get the key**:
1. Go to [https://console.groq.com](https://console.groq.com)
2. Sign Up with Google or email
3. Left sidebar → **API Keys** → **Create API Key**
4. Set: `GROQ_API_KEY=gsk_...`

**Quota Reset**: Daily at 00:00 UTC

**Available free models**: `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768`, `gemma2-9b-it`

---

### 3. Cerebras — Llama 3.3 70B
**Capability**: Extremely fast inference (up to 2,100 tokens/second). Full 70B model, free tier.

**Provider**: Cerebras Cloud (`https://api.cerebras.ai`)

**Free Tier**: 1,000,000 tokens/day, 60 requests/minute

**API Style**: OpenAI-compatible

**How to get the key**:
1. Go to [https://cloud.cerebras.ai](https://cloud.cerebras.ai)
2. Sign Up → verify email
3. Navigate to **API Keys** in your account dashboard
4. Click **"Generate API Key"** → copy
5. Set: `CEREBRAS_API_KEY=csk-...`

**Quota Reset**: Daily

**Available free models**: `llama3.3-70b`, `llama3.1-8b`

---

### 4. Google Gemini 1.5 Flash
**Capability**: Multimodal (text + images), very fast, long context (1M tokens). Best for complex tasks on free tier.

**Provider**: Google AI Studio (`https://generativelanguage.googleapis.com`)

**Free Tier**: 15 RPM (requests/minute), 1,500 RPD (requests/day), 1,000,000 tokens/day. **No billing required.**

**API Style**: Google-native (also available via OpenAI-compatible endpoint)

**How to get the key**:
1. Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with Google account
3. Click **"Create API Key"**
4. Select a Google Cloud project (or create one — free)
5. Copy the key
6. Set: `GEMINI_API_KEY=AIza...`

**Quota Reset**: Per-minute (RPM) + daily (RPD)

**Example call**:
```python
import httpx
response = await httpx.AsyncClient().post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
    json={"contents": [{"parts": [{"text": "Hello"}]}]}
)
```

---

### 5. Together AI — Qwen2.5 72B
**Capability**: Strong multilingual model, good for Asian language content and general tasks.

**Provider**: Together AI (`https://api.together.xyz`)

**Free Tier**: $1 free credit on signup (then pay-as-you-go at very low rates). Free tier models also available.

**API Style**: OpenAI-compatible

**How to get the key**:
1. Go to [https://api.together.ai](https://api.together.ai)
2. Sign Up → verify email
3. Navigate to **Settings → API Keys**
4. Click **"Create API Key"** → copy
5. Set: `TOGETHER_API_KEY=...`

**Free models**: `Qwen/Qwen2.5-72B-Instruct-Turbo`, `meta-llama/Llama-3.3-70B-Instruct-Turbo` (among many others)

---

### 6. OpenRouter — Mistral 7B (free)
**Capability**: Routes to many models. Free tier includes several Mistral and Llama variants.

**Provider**: OpenRouter (`https://openrouter.ai/api`)

**Free Tier**: Free models available without credits. Rate-limited. Check [https://openrouter.ai/models?q=free](https://openrouter.ai/models?q=free) for current list.

**API Style**: OpenAI-compatible

**How to get the key**:
1. Go to [https://openrouter.ai](https://openrouter.ai)
2. Click **"Sign In"** → create account
3. Navigate to **Keys** in account settings
4. Click **"Create Key"** → copy
5. Set: `OPENROUTER_API_KEY=sk-or-...`

**Free models include**: `mistralai/mistral-7b-instruct:free`, `meta-llama/llama-3.2-3b-instruct:free`, `google/gemma-2-9b-it:free`

---

### 7. HuggingFace Inference API — Text
**Capability**: Access to thousands of open-source models. Free tier with rate limits. Slower than dedicated providers.

**Provider**: HuggingFace (`https://api-inference.huggingface.co`)

**Free Tier**: Free with HuggingFace account. Rate-limited; may queue during high traffic.

**How to get the key**:
1. Go to [https://huggingface.co/join](https://huggingface.co/join)
2. Create account → verify email
3. Click your profile picture → **Settings → Access Tokens**
4. Click **"New token"** → Type: Read → copy
5. Set: `HUGGINGFACE_API_KEY=hf_...`

**Good free text models**: `HuggingFaceH4/zephyr-7b-beta`, `microsoft/phi-2`, `mistralai/Mistral-7B-Instruct-v0.3`

---

## IMAGE MODELS

---

### 8. HuggingFace — FLUX.1-schnell (Image)
**Capability**: State-of-the-art image generation. Fast, high quality, open source.

**Provider**: HuggingFace Inference API

**Free Tier**: Free with HuggingFace token (same key as text above). May cold-start on first call (~30 s).

**Model**: `black-forest-labs/FLUX.1-schnell`

**How to get the key**: Same as #7 above. Uses `HUGGINGFACE_API_KEY`.

**Example call**:
```python
import httpx
response = await httpx.AsyncClient().post(
    "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
    headers={"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"},
    json={"inputs": "A sunset over the ocean"},
    timeout=60.0
)
# response.content is raw PNG binary
```

---

### 9. Prodia — SDXL Image Generation
**Capability**: Stable Diffusion XL via simple REST API. Reliable free tier.

**Provider**: Prodia (`https://api.prodia.com`)

**Free Tier**: Free tier available. Rate-limited.

**How to get the key**:
1. Go to [https://app.prodia.com](https://app.prodia.com)
2. Sign up with email or Google
3. Navigate to **API** in the sidebar
4. Copy the API key shown
5. Set: `PRODIA_API_KEY=...`

**Flow**: Submit job → poll job ID → download image URL

---

### 10. Fal.ai — FLUX.1-schnell
**Capability**: Fast, production-grade image generation. Free credits on signup.

**Provider**: Fal.ai (`https://fal.ai`)

**Free Tier**: Free credits on signup; pay-as-you-go thereafter (very cheap, ~$0.003/image)

**How to get the key**:
1. Go to [https://fal.ai](https://fal.ai)
2. Sign Up → verify email
3. Navigate to [https://fal.ai/dashboard/keys](https://fal.ai/dashboard/keys)
4. Click **"Add key"** → copy
5. Set: `FAL_API_KEY=...`

**Python client**: `pip install fal-client`

---

## AUDIO — SPEECH TO TEXT (STT)

---

### 11. Groq — Whisper Large V3 (STT)
**Capability**: OpenAI Whisper large-v3 inference at very high speed. Best free STT available.

**Provider**: Groq Cloud (same API key as #2)

**Free Tier**: 28,800 seconds of audio/day (8 hours). Max 25 MB per file.

**API Style**: OpenAI-compatible audio transcription

**Uses existing `GROQ_API_KEY`**.

**Supported formats**: mp3, mp4, mpeg, mpga, m4a, wav, webm

**Example call**:
```python
import httpx
async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")},
        data={"model": "whisper-large-v3", "response_format": "json"}
    )
```

---

### 12. HuggingFace — Whisper Large V3 (STT fallback)
**Capability**: Whisper large-v3 via HuggingFace Inference API. Slower than Groq but free.

**Provider**: HuggingFace Inference API

**Model**: `openai/whisper-large-v3`

**Uses existing `HUGGINGFACE_API_KEY`**.

---

## AUDIO — TEXT TO SPEECH (TTS)

---

### 13. Kokoro-82M via HuggingFace (TTS)
**Capability**: One of the best open-source TTS models. Natural-sounding voices, multiple languages. Very lightweight (82M params).

**Provider**: HuggingFace Inference API

**Model**: `hexgrad/Kokoro-82M`

**Free Tier**: Free with HuggingFace token. Rate-limited.

**Uses existing `HUGGINGFACE_API_KEY`**.

**Example call**:
```python
import httpx
response = await httpx.AsyncClient().post(
    "https://api-inference.huggingface.co/models/hexgrad/Kokoro-82M",
    headers={"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"},
    json={"inputs": "Hello, I am your AI assistant."},
    timeout=30.0
)
# response.content is raw audio (wav)
```

---

### 14. ElevenLabs (TTS — free tier)
**Capability**: Most natural-sounding TTS. Multiple voices and languages. Free tier limited to 10,000 characters/month.

**Provider**: ElevenLabs (`https://api.elevenlabs.io`)

**Free Tier**: 10,000 characters/month (~7 minutes of audio), access to pre-made voices

**How to get the key**:
1. Go to [https://elevenlabs.io](https://elevenlabs.io)
2. Click **"Sign Up"** → create free account
3. Navigate to **Profile → API Key** (bottom left)
4. Copy the key
5. Set: `ELEVENLABS_API_KEY=...`

**Voices (free)**: Rachel, Drew, Clyde, Paul, Domi, Dave, Fin, Sarah, Antoni, Thomas — get voice IDs from [https://api.elevenlabs.io/v1/voices](https://api.elevenlabs.io/v1/voices)

---

## EXTERNAL SERVICE INTEGRATIONS

---

### 15. Microsoft Graph API (Outlook Calendar)
**Capability**: Read/create/update calendar events, manage Outlook mail.

**Provider**: Microsoft Azure / Microsoft Graph

**Cost**: Free for personal Microsoft accounts. Azure app registration is free.

**How to set up**:
1. Go to [https://portal.azure.com](https://portal.azure.com) (sign in with any Microsoft account — free)
2. Navigate to **Azure Active Directory → App registrations**
3. Click **"New registration"**
   - Name: `AI Agent Hub` (or any name)
   - Supported account types: **"Accounts in any organizational directory and personal Microsoft accounts"**
   - Redirect URI: Web → `https://your-backend.com/agent/outlook/callback`
4. After creation, note the **Application (client) ID** → `MS_CLIENT_ID`
5. Go to **Certificates & secrets → New client secret** → copy value → `MS_CLIENT_SECRET`
6. Go to **API permissions → Add permission → Microsoft Graph → Delegated**
   - Add: `Calendars.ReadWrite`, `offline_access`, `User.Read`
   - Click **"Grant admin consent"** (for personal accounts this is automatic)
7. Set env vars: `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_REDIRECT_URI`

**Token lifetime**: Refresh tokens last 90 days (sliding window extends if user stays active).

---

### 16. Telegram Bot API
**Capability**: Send/receive messages via a Telegram bot. Webhook delivery for real-time messaging.

**Provider**: Telegram (`https://api.telegram.org`)

**Cost**: Completely free. No limits for standard usage.

**How to create a bot**:
1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Enter a display name (e.g., "My AI Assistant")
4. Enter a username ending in `bot` (e.g., `myaiassistant_bot`)
5. BotFather sends you a **token** like `1234567890:ABCDefGHIjklmNoPQRsTUVwxYZ`
6. Enter this token in the AI Agent Hub → Connections → Telegram

**No env vars needed** — users provide their own bot token via the UI.

**Useful BotFather commands**:
- `/setdescription` — set bot description shown to users
- `/setprivacy` — set to DISABLE to receive all group messages (not needed for private chats)

---

### 17. WhatsApp via WAHA (WhatsApp HTTP API)
**Capability**: Connect personal WhatsApp accounts via QR code scan. Send/receive messages.

**Provider**: WAHA (open source, self-hosted) — [https://waha.devlike.pro](https://waha.devlike.pro)

**Cost**: Free (Core edition). No WhatsApp Business account needed. Uses your personal number.

**How to deploy WAHA**:

**Quick start (local/dev)**:
```bash
docker run -d \
  --name waha \
  -p 3000:3000 \
  devlikeapro/waha
```

**With API key (recommended for production)**:
```bash
docker run -d \
  --name waha \
  -p 3000:3000 \
  -e WHATSAPP_API_KEY=your-secret-key \
  devlikeapro/waha
```

**Production (docker-compose)**:
```yaml
services:
  waha:
    image: devlikeapro/waha
    ports:
      - "3000:3000"
    environment:
      - WHATSAPP_API_KEY=${WAHA_API_KEY}
    volumes:
      - waha_data:/app/.sessions
    restart: unless-stopped

volumes:
  waha_data:
```

**Verify it's running**: `curl http://localhost:3000/api/sessions`

**WAHA Dashboard**: `http://localhost:3000/dashboard` — UI to manage sessions

**Set env vars**: `WAHA_URL=http://localhost:3000`, `WAHA_API_KEY=your-secret-key`

**Important**: WhatsApp Web can only be open in one place at a time per number. Using WAHA will disconnect any existing WhatsApp Web session on your browser.

---

## SUMMARY TABLE

| # | Model | Type | Provider | Free Tier | Env Var |
|---|---|---|---|---|---|
| 1 | DeepSeek-V3 | Text LLM | DeepSeek API | ~$5 free credits | `DEEPSEEK_API_KEY` |
| 2 | Llama 3.3 70B | Text LLM | Groq | 14,400 req/day | `GROQ_API_KEY` ✅ |
| 3 | Llama 3.3 70B | Text LLM | Cerebras | 1M tokens/day | `CEREBRAS_API_KEY` |
| 4 | Gemini 1.5 Flash | Text LLM | Google AI Studio | 1,500 req/day | `GEMINI_API_KEY` |
| 5 | Qwen2.5-72B | Text LLM | Together AI | $1 free credit | `TOGETHER_API_KEY` |
| 6 | Mistral-7B | Text LLM | OpenRouter | Free models | `OPENROUTER_API_KEY` |
| 7 | Various | Text LLM | HuggingFace | Free (slow) | `HUGGINGFACE_API_KEY` |
| 8 | FLUX.1-schnell | Image | HuggingFace | Free (slow) | `HUGGINGFACE_API_KEY` |
| 9 | SDXL | Image | Prodia | Free tier | `PRODIA_API_KEY` |
| 10 | FLUX.1-schnell | Image | Fal.ai | Free credits | `FAL_API_KEY` |
| 11 | Whisper large-v3 | STT | Groq | 8 hrs/day | `GROQ_API_KEY` ✅ |
| 12 | Whisper large-v3 | STT | HuggingFace | Free (slow) | `HUGGINGFACE_API_KEY` |
| 13 | Kokoro-82M | TTS | HuggingFace | Free (slow) | `HUGGINGFACE_API_KEY` |
| 14 | Multilingual v2 | TTS | ElevenLabs | 10k chars/mo | `ELEVENLABS_API_KEY` |
| 15 | Calendar API | Integration | Microsoft Graph | Free | `MS_CLIENT_ID/SECRET` |
| 16 | Bot API | Integration | Telegram | Free | User provides token |
| 17 | WhatsApp | Integration | WAHA (self-hosted) | Free | `WAHA_URL/API_KEY` |

✅ = already in project
