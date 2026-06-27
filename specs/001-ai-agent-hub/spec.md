# Feature Specification: AI Agent Hub

**Feature Branch**: `001-ai-agent-hub`

**Created**: 2026-06-27

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Conversational AI Chat (Priority: P1)

A user opens the Agent Hub page and types a message in natural language. The system understands the type of request (ask a question, generate an image, transcribe audio, write code) and responds using the best available free AI model. If the first model is unavailable or over quota, the system seamlessly falls back to the next one without the user noticing any disruption.

**Why this priority**: This is the core value of the feature. Without a working chat interface backed by a resilient, intent-aware model router, no other capability (calendar, Telegram, WhatsApp) is useful.

**Independent Test**: Open `/agent`, type "Explain what machine learning is in one paragraph." Receive a coherent response. Repeat until quota is exhausted on one model and verify the next model answers instead.

**Acceptance Scenarios**:

1. **Given** a user is logged in and on the Agent Hub page, **When** they type a text question and submit, **Then** they receive a relevant AI-generated reply within 10 seconds.
2. **Given** one text model has exceeded its daily quota, **When** the user sends a message, **Then** the system silently retries with the next model in the fallback chain and returns a valid response.
3. **Given** the user asks for an image (e.g., "draw a cat"), **When** the gateway detects image intent, **Then** the system routes to an image model and displays the generated image inline in the chat.
4. **Given** the user uploads an audio file, **When** the gateway detects audio/transcription intent, **Then** the system returns a text transcription of the audio.
5. **Given** all models in a pool are exhausted for the day, **When** the user sends a request of that type, **Then** the system informs the user clearly that the service is temporarily unavailable for that request type.

---

### User Story 2 — Model Status Dashboard (Priority: P2)

A user wants to know which AI models are currently active and which have hit their quota limits for the day. They open a status panel in the Agent Hub and can see a real-time list of all connected models grouped by type (text, image, audio), with a green/yellow/red indicator for each.

**Why this priority**: Operational visibility is critical for a multi-model gateway. Without it, users cannot diagnose why responses are slower or degraded, and the operator cannot tell which models need attention.

**Independent Test**: Exhaust one model's daily quota manually. Open the status panel and confirm that model shows as quota-exhausted while others show active.

**Acceptance Scenarios**:

1. **Given** a user opens the model status panel, **When** it loads, **Then** they see all configured models grouped by type with current availability status.
2. **Given** a model has exceeded its daily quota, **When** the status panel is viewed, **Then** that model is shown as quota-exhausted with quota reset time if available.
3. **Given** a model API call fails with a network error, **When** the status panel is viewed, **Then** that model is shown as temporarily unavailable.

---

### User Story 3 — Outlook Calendar Integration (Priority: P3)

A user connects their Microsoft Outlook account from the Connections panel. Once connected, they can ask the agent natural-language questions about their calendar ("What meetings do I have tomorrow?", "Schedule a call with Juan on Friday at 3pm") and the agent reads, creates, or updates calendar events on their behalf.

**Why this priority**: Calendar management via conversation is a high-value productivity feature. It transforms the agent from a generic chatbot into a personal assistant.

**Independent Test**: Connect an Outlook account, ask "What do I have scheduled tomorrow?", and verify the agent returns real calendar event data. Then say "Create a 30-minute meeting called Test on [future date]" and verify the event appears in Outlook.

**Acceptance Scenarios**:

1. **Given** a user clicks "Connect Outlook" on the Connections panel, **When** they complete the Microsoft OAuth flow, **Then** their account is linked and the Connections panel shows "Connected" with account name.
2. **Given** an Outlook account is connected, **When** the user asks "What meetings do I have this week?", **Then** the agent returns a list of calendar events for the current week.
3. **Given** an Outlook account is connected, **When** the user asks the agent to schedule an event, **Then** the event is created in Outlook and the agent confirms with event details.
4. **Given** the user clicks "Disconnect Outlook", **When** they confirm, **Then** the integration is removed and the agent can no longer access their calendar.
5. **Given** the OAuth access token approaches expiry, **When** the agent makes a calendar request, **Then** the token is automatically refreshed without requiring the user to re-authenticate (token valid for at least 90 days via refresh token).

---

### User Story 4 — Telegram Integration (Priority: P4)

A user enters their Telegram Bot Token in the Connections panel. The system registers a webhook so that any message sent to that Telegram bot is forwarded to the AI agent, which replies back through Telegram. The user can have full conversations with the agent directly from the Telegram app.

**Why this priority**: Telegram is a widely used messaging channel. Connecting the agent to Telegram lets users interact without opening the web platform, dramatically increasing accessibility and usage frequency.

**Independent Test**: Enter a bot token, verify webhook registration succeeds, send a message to the Telegram bot, and verify an AI-generated reply arrives in Telegram within 10 seconds.

**Acceptance Scenarios**:

1. **Given** a user enters a valid Bot Token and clicks "Connect", **When** the system registers the webhook, **Then** the Connections panel shows "Active" with the bot username.
2. **Given** the Telegram bot is connected, **When** a user sends a message to the bot in Telegram, **Then** the AI agent processes it and the bot replies within 10 seconds.
3. **Given** the Telegram bot is connected, **When** a user asks a calendar-related question in Telegram and Outlook is also connected, **Then** the agent uses the Outlook integration to answer.
4. **Given** a user enters an invalid Bot Token, **When** they click "Connect", **Then** the system displays an error message explaining the token is invalid.
5. **Given** a user clicks "Disconnect Telegram", **When** they confirm, **Then** the webhook is removed and the bot stops responding to messages.

---

### User Story 5 — WhatsApp Integration via QR Code (Priority: P5)

A user opens the WhatsApp section of the Connections panel and sees a QR code. They scan it with their WhatsApp mobile app to link their account. Once linked, the AI agent can receive and send WhatsApp messages on their behalf. The user can manage multiple WhatsApp accounts, each shown as a separate session with its own connection status.

**Why this priority**: WhatsApp is the dominant messaging platform in many markets. Enabling the agent to communicate via WhatsApp makes it accessible to a much wider audience and enables use cases like automated follow-ups and appointment reminders.

**Independent Test**: Open the Connections panel, scan the displayed QR code with WhatsApp on a phone, send a message to the linked number, and verify the AI agent replies through WhatsApp.

**Acceptance Scenarios**:

1. **Given** a user opens the WhatsApp Connections panel, **When** the QR code is displayed, **Then** they can scan it with WhatsApp to link their account within 60 seconds.
2. **Given** a WhatsApp account is linked, **When** a user sends a message to the connected number, **Then** the AI agent replies within 15 seconds.
3. **Given** a user wants to add a second WhatsApp account, **When** they click "Add Account", **Then** a new QR code session is created and appears as a separate entry in the session list.
4. **Given** a WhatsApp session is listed, **When** the user clicks "Disconnect" for that session, **Then** that WhatsApp account is unlinked and the agent stops responding from it.
5. **Given** a WhatsApp session disconnects unexpectedly (phone offline), **When** the user views the Connections panel, **Then** that session is shown as "Disconnected" with an option to re-scan.

---

### Edge Cases

- What happens when all models across all pools are exhausted simultaneously? → System returns a clear "Service temporarily unavailable" message with estimated reset time.
- What if the user's internet drops mid-conversation? → Partial messages are not lost; the chat history is persisted in the backend and reloads on reconnect.
- What if the Microsoft OAuth redirect fails or is denied by the user? → The connection flow is cancelled gracefully and the user is returned to the Connections panel with an error notice.
- What if the WhatsApp QR code expires before being scanned? → The system automatically generates a new QR code and displays it.
- What if the Telegram webhook URL changes (e.g., after redeployment)? → The system re-registers the webhook automatically on startup or when the connection is re-saved.
- What if the AI agent receives a very long WhatsApp or Telegram message that exceeds model context limits? → The system truncates or summarizes prior context to keep the request within limits while preserving the current message.
- What if multiple WhatsApp sessions receive messages simultaneously? → Each session is handled independently with its own conversation context.

---

## Requirements *(mandatory)*

### Functional Requirements

**Chat & Gateway**
- **FR-001**: The system MUST accept text messages from users and return AI-generated responses.
- **FR-002**: The system MUST detect the intent of each incoming message (text, image generation, audio transcription, code) and route it to the appropriate model pool.
- **FR-003**: The system MUST maintain an ordered fallback list per model pool; if the primary model fails or is over quota, it MUST automatically try the next model in the list.
- **FR-004**: The system MUST track daily usage per model and skip models that have exceeded their quota limit.
- **FR-005**: The system MUST expose a real-time status endpoint showing availability and quota state of every configured model.
- **FR-006**: The system MUST display generated images inline within the chat history.
- **FR-007**: The system MUST accept audio file uploads and return transcribed text via the audio model pool.
- **FR-008**: The system MUST persist per-user conversation history so it is available after page reload or session change.

**Outlook Calendar**
- **FR-009**: The system MUST provide an OAuth2 authorization flow for users to connect their Microsoft account.
- **FR-010**: The system MUST store the OAuth refresh token securely per user and use it to obtain new access tokens automatically (token must remain valid for at least 90 days without user re-authentication).
- **FR-011**: The system MUST allow the agent to read upcoming calendar events when the user asks about their schedule.
- **FR-012**: The system MUST allow the agent to create new calendar events when the user requests via natural language.
- **FR-013**: The system MUST allow users to disconnect their Outlook account, which MUST immediately revoke stored tokens.

**Telegram**
- **FR-014**: The system MUST allow users to register a Telegram Bot Token via the UI.
- **FR-015**: The system MUST register a webhook with the Telegram Bot API so incoming messages are received in real time.
- **FR-016**: The agent MUST process messages received via Telegram and reply through the same Telegram bot.
- **FR-017**: Conversation context from Telegram messages MUST be maintained per-user per-channel.
- **FR-018**: The system MUST allow users to disconnect Telegram, which MUST remove the webhook registration.

**WhatsApp**
- **FR-019**: The system MUST display a QR code that users can scan with WhatsApp to link their account.
- **FR-020**: The system MUST support multiple WhatsApp accounts simultaneously, each as an independent session.
- **FR-021**: The agent MUST process messages received via WhatsApp and reply through the same linked account.
- **FR-022**: The system MUST allow users to disconnect individual WhatsApp sessions.
- **FR-023**: The system MUST show the connection status (connected, disconnected, loading) for each WhatsApp session.
- **FR-024**: The QR code MUST automatically refresh if it expires before being scanned.

### Key Entities

- **AgentConversation**: A per-user chat session with full message history (role, content, timestamp, model used, intent detected).
- **ModelUsageLog**: Daily usage counter per model per user; resets at midnight UTC.
- **OutlookConnection**: Per-user Microsoft OAuth credentials (access token, refresh token, expiry, account email).
- **TelegramConnection**: Per-user bot token, webhook URL, and bot username.
- **WhatsAppSession**: Per-user WhatsApp session identifier, phone number, status, and QR code state. Multiple per user.
- **AgentMessage**: A single turn in a conversation, tagged with channel (web, telegram, whatsapp), intent, model used, and response time.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive an AI response within 10 seconds for text requests under normal load.
- **SC-002**: When the primary model is unavailable, the system automatically falls back and the user receives a response within 15 seconds — with no error shown.
- **SC-003**: The Outlook OAuth connection flow completes in under 2 minutes and remains valid for at least 90 days without requiring re-authentication.
- **SC-004**: Messages sent via Telegram to the connected bot receive a reply within 10 seconds of delivery.
- **SC-005**: The WhatsApp QR code is scannable and produces a confirmed connection within 60 seconds of display.
- **SC-006**: Messages sent via WhatsApp receive a reply within 15 seconds of delivery.
- **SC-007**: The model status panel accurately reflects quota-exhausted models within 60 seconds of exhaustion occurring.
- **SC-008**: Conversation history for a user persists correctly across page reloads and browser sessions.
- **SC-009**: The system supports at least 3 simultaneous WhatsApp accounts per user without cross-contamination of conversation context.

---

## Assumptions

- Users are authenticated via the existing JWT-based auth system; no new authentication mechanism is needed.
- The WAHA (WhatsApp HTTP API) service is deployed as a Docker container on the same infrastructure as the backend; it is not a third-party SaaS.
- Free-tier model quotas are sufficient for a single-user or small-team deployment; the system is not designed for high-volume public traffic.
- Calendar integration is limited to a single connected Outlook/Microsoft account per user in v1.
- Telegram integration uses the Bot API only (not user accounts); each user brings their own bot token.
- Audio transcription is limited to files under 25 MB (Groq Whisper limit).
- Image generation requests produce one image per request; batch generation is out of scope for v1.
- The backend is deployed with a single worker process (consistent with existing deployment constraints for APScheduler).
- WhatsApp message sending is subject to WhatsApp's own terms of service; the feature is intended for personal/business use by the account owner, not bulk messaging.
- The Microsoft OAuth app registration (client ID and secret) is managed by the platform operator, not each individual user.
