# PROMPT PARA CLAUDE CODE — Sistema de Captación Automática de Clientes

> Copia y pega TODO este prompt en Claude Code cuando estés parado en la raíz de tu proyecto (el que ya tiene el backend Python + frontend React + base de datos + módulo de info de empresas).
>
> Antes de ejecutar: asegúrate de haber leído la sección "Antes de pegar el prompt" al final de este documento. Hay variables de entorno y decisiones que debes confirmar tú, no Claude.

---

## ROL Y CONTEXTO

Eres un ingeniero senior full-stack especializado en sistemas de growth/outbound. Vas a implementar un sistema de captación automática de clientes para una agencia de desarrollo de software a medida (React + Python + SaaS custom). El sistema ya tiene:

- Backend Python con API REST (FastAPI o Flask, detéctalo leyendo `requirements.txt` y `main.py`/`app.py`).
- Frontend React con login de usuarios (detecta si usa React Router, Zustand/Redux, y qué cliente HTTP — axios/fetch).
- Base de datos (detecta si es Postgres, MySQL o Mongo leyendo la config/ORM existente).
- Un módulo de "obtención de información de empresas" ya construido. **Lee ese módulo primero** antes de escribir código nuevo, porque vas a extenderlo, no reemplazarlo.

**Objetivo de negocio:** ejecutar diariamente un pipeline que encuentra empresas ICP, extrae contactos de decisores, genera emails personalizados, los deja en una cola de aprobación, y tras aprobación humana los envía vía Instantly.ai. El dueño revisa métricas una vez por semana.

**Filosofía de diseño (NO la rompas):**
- Humano en el loop obligatorio en el paso de aprobación de emails. Nunca envíes sin aprobación explícita.
- Rate limits y cuotas de APIs externas manejadas con backoff y circuit breakers.
- Opt-out y supresión de contactos respetada en cada envío (compliance GDPR/LATAM).
- Todo lo que cuesta dinero (llamadas a Claude API, credits de Apollo, credits de Instantly) debe quedar loggeado con timestamp y costo estimado.

---

## STACK Y SERVICIOS EXTERNOS

Usa estos servicios. Si ya hay alguno montado, reutilízalo en vez de crear uno nuevo.

| Capa | Servicio | Variable de entorno |
|------|----------|---------------------|
| LLM para redactar emails y scoring | Anthropic API, modelo `claude-sonnet-4-6`, con prompt caching activado | `ANTHROPIC_API_KEY` |
| Fuente de empresas y contactos | Apollo.io API | `APOLLO_API_KEY` |
| Envío de emails con warm-up y rotación | Instantly.ai API | `INSTANTLY_API_KEY`, `INSTANTLY_CAMPAIGN_ID` |
| Scheduler de jobs | APScheduler (si backend es Flask) o FastAPI + `apscheduler` (si es FastAPI). NO uses Celery salvo que ya esté en el proyecto. | — |
| Research adicional | `httpx` + BeautifulSoup para scraping ligero de sitios web públicos (solo robots.txt-compliant) | — |

---

## ARQUITECTURA — MÓDULOS A CREAR

Organiza el código nuevo bajo un paquete `outbound/` en el backend. NO mezcles con el código existente de otros dominios.

```
backend/
├── outbound/
│   ├── __init__.py
│   ├── models.py              # SQLAlchemy models o Pydantic para Mongo
│   ├── schemas.py             # Pydantic schemas para API
│   ├── apollo_client.py       # Wrapper Apollo con rate limit + retry
│   ├── instantly_client.py    # Wrapper Instantly
│   ├── claude_client.py       # Wrapper Anthropic con prompt caching
│   ├── icp_scorer.py          # Scoring de empresas contra ICP
│   ├── email_drafter.py       # Generación de email personalizado
│   ├── suppression.py         # Lista de supresión (opt-outs, ya contactados)
│   ├── approval_queue.py      # Lógica de cola de aprobación
│   ├── jobs.py                # Definición de jobs programados
│   ├── routes.py              # Endpoints FastAPI/Flask
│   └── tests/
│       ├── test_icp_scorer.py
│       ├── test_email_drafter.py
│       └── test_suppression.py
```

Frontend:

```
frontend/src/
├── pages/
│   ├── OutboundDashboard.jsx       # Métricas semanales, gráficas
│   ├── ApprovalQueue.jsx           # Lista de drafts pendientes
│   └── SuppressionList.jsx         # Gestión de opt-outs
├── components/outbound/
│   ├── DraftCard.jsx               # Card de un email pendiente, con botones Aprobar/Editar/Rechazar
│   ├── MetricsChart.jsx
│   └── ICPConfigForm.jsx           # Formulario para editar el ICP sin tocar código
└── api/outbound.js                 # Cliente del backend outbound
```

---

## ESPECIFICACIÓN DETALLADA

### 1. Modelos de datos (crea las migraciones)

**`Prospect`** — una empresa + un contacto decisor:
- `id`, `company_name`, `company_domain`, `company_size`, `industry`, `country`
- `contact_email`, `contact_full_name`, `contact_title`, `contact_linkedin_url`
- `icp_score` (0–100), `tier` (A/B/C), `signals_detected` (JSON array de strings)
- `source` (default "apollo"), `apollo_contact_id`, `discovered_at`
- `status` enum: `discovered`, `enriched`, `drafted`, `pending_approval`, `approved`, `sent`, `replied`, `bounced`, `suppressed`, `rejected`
- `created_at`, `updated_at`

**`EmailDraft`** — borrador de email generado:
- `id`, `prospect_id` (FK), `subject`, `body_markdown`, `body_html`
- `personalization_notes` (qué señales usó Claude para personalizar)
- `status` enum: `pending_approval`, `approved`, `rejected`, `sent`
- `reviewed_by` (user_id), `reviewed_at`, `sent_at`
- `claude_tokens_used`, `claude_cost_usd`, `model_used`
- `instantly_message_id` (nullable, se llena al enviar)

**`SuppressionEntry`**:
- `id`, `email` (unique, indexed), `reason` (`opt_out`, `bounce`, `complaint`, `do_not_contact`, `manual`)
- `added_at`, `source`

**`OutboundMetrics`** — snapshot diario agregado:
- `date`, `prospects_discovered`, `emails_drafted`, `emails_approved`, `emails_sent`, `replies_received`, `meetings_booked`
- `apollo_credits_used`, `claude_cost_usd`, `instantly_emails_consumed`

**`ICPConfig`** — guarda el ICP editable desde UI:
- `id`, `version`, `active` (bool), `config_json` (con filtros de Apollo, pesos de scoring, angles de entrada), `updated_by`, `updated_at`

### 2. Apollo Client (`apollo_client.py`)

- Método `search_companies(filters: dict, page: int, per_page: int = 25)` — usa endpoint `/v1/mixed_companies/search`.
- Método `get_contacts_for_company(company_id, titles: list)` — busca contactos con títulos objetivo (default: `["CEO", "CTO", "Head of Engineering", "VP Engineering", "Product Manager", "Director of Technology"]`).
- Rate limit: max 60 requests/min. Usa `tenacity` para retry exponencial en 429s.
- Log cada request en tabla `api_calls_log` (crea si no existe) con endpoint, tokens/credits consumidos, response time.

### 3. ICP Scorer (`icp_scorer.py`)

Implementa este algoritmo de scoring (los pesos vienen de `ICPConfig.config_json`):

```python
def score_company(company: dict, icp_config: dict) -> tuple[int, list[str]]:
    """
    Retorna (score, signals_detected).
    Score 0–100. signals_detected es lista de strings con qué matcheo.
    """
```

Factores y pesos por defecto (editables en ICPConfig):
- Tamaño (20 pts): rango ideal 50–200 empleados
- Industria (20 pts): match con lista de industrias del ICP
- Geo (10 pts): LATAM / España / US Hispanic market priorizados
- Señales de compra (30 pts, suma 10 por cada una detectada hasta 3):
  - Vacantes técnicas activas (detectar con web_search en LinkedIn jobs del dominio)
  - Funding reciente (<12 meses) — se infiere de campos de Apollo
  - Stack legacy detectado (WordPress, PHP <7, Joomla, etc.) — de technographics de Apollo
  - Keywords de "digital transformation" o "modernization"
- Revenue fit (20 pts): $2M–$50M anuales estimados

Si score < 30, marca `tier = 'rejected'` y salta el resto del pipeline para esa empresa.

### 4. Claude Client (`claude_client.py`)

```python
from anthropic import Anthropic

client = Anthropic()
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT_TEMPLATE = """..."""  # largo, cacheado

def draft_email(prospect: Prospect, icp_config: dict, case_studies: list[str]) -> EmailDraft:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT_TEMPLATE,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[{"role": "user", "content": build_user_prompt(prospect)}]
    )
    # parsea, calcula costo desde usage.input_tokens, usage.output_tokens, usage.cache_read_input_tokens
    # guarda en EmailDraft con status=pending_approval
```

El system prompt debe incluir:
- Voz y tono de la agencia (léelo desde `ICPConfig.config_json["brand_voice"]`)
- 2–3 case studies resumidos
- Reglas duras: máximo 120 palabras, asunto de 6–8 palabras, una sola llamada a la acción, no prometer cosas que la agencia no hace, siempre firmar con nombre real del dueño + link a calendly.

### 5. Instantly Client (`instantly_client.py`)

- Método `add_lead_to_campaign(campaign_id, email, first_name, last_name, custom_vars: dict)` — endpoint `/api/v2/leads`.
- Método `pause_lead(lead_id)` para cuando marcamos suppress.
- Método `get_campaign_stats(campaign_id)` para el dashboard semanal.

### 6. Suppression (`suppression.py`)

Antes de enviar CUALQUIER email, verifica:
1. `SuppressionEntry` no contiene ese email.
2. El dominio no está en una lista estática de dominios a evitar (crea `outbound/blocked_domains.txt` con: gov, .edu, google, meta, microsoft, apple, amazon, y todos los dominios de agencias de software competencia — dejar vacía para que el dueño llene).
3. No se envió a ese email en los últimos 90 días.

Todo email enviado tiene en el footer un link de opt-out que apunta a `GET /outbound/unsubscribe?token={signed_token}`. El endpoint marca `SuppressionEntry` con reason=`opt_out` y llama a `instantly_client.pause_lead`.

### 7. Jobs programados (`jobs.py`)

Tres jobs con APScheduler:

**Job A — `discover_prospects` (diario, 8am hora del servidor)**
1. Lee `ICPConfig` activa.
2. Llama Apollo con filtros de la config. Máximo 25 empresas por día (para no reventar cuota del plan Free).
3. Para cada empresa, llama `score_company`. Si `score >= 50`, busca contacto con `get_contacts_for_company` (1 solo contacto por empresa para no quemar credits).
4. Crea `Prospect` con status=`enriched`.

**Job B — `draft_emails` (diario, 9am)**
1. Toma prospects con status=`enriched`, tier A o B, max 15 por día.
2. Pasa por suppression check.
3. Llama `email_drafter.draft_email`. Guarda `EmailDraft` con status=`pending_approval`. Actualiza prospect a `drafted`.
4. Si el dueño tiene configurado email de notificación, envía un digest diario: "Tienes N emails pendientes de aprobar, entra a /outbound/approvals".

**Job C — `send_approved_emails` (cada hora, 8am–6pm)**
1. Toma `EmailDraft` con status=`approved` y `sent_at IS NULL`.
2. Llama `instantly_client.add_lead_to_campaign`. Marca `sent_at = now()`, actualiza prospect a `sent`.
3. Rate limit: máximo 10 envíos por hora en total, para dar tiempo al warm-up de Instantly.

**Job D — `sync_replies_and_stats` (diario, 7pm)**
1. Llama Instantly para traer replies del día. Actualiza `Prospect.status = replied` donde matchee email.
2. Calcula métricas agregadas y guarda en `OutboundMetrics`.

### 8. Endpoints REST (`routes.py`)

Namespace `/api/outbound`. Protege todos con el middleware de auth existente (reutiliza, no crees uno nuevo).

- `GET /api/outbound/approvals?status=pending_approval&limit=50` — lista drafts.
- `POST /api/outbound/approvals/{draft_id}/approve` — marca approved.
- `POST /api/outbound/approvals/{draft_id}/reject` — marca rejected, opcional body `{"reason": "..."}`.
- `PATCH /api/outbound/approvals/{draft_id}` — edita subject/body antes de aprobar.
- `GET /api/outbound/metrics?days=30` — devuelve `OutboundMetrics` agregado.
- `GET /api/outbound/prospects?tier=A&status=enriched` — lista prospects.
- `POST /api/outbound/icp-config` — actualiza `ICPConfig` (crea nueva versión, desactiva la anterior).
- `GET /api/outbound/unsubscribe` — público, sin auth, procesa opt-out.
- `POST /api/outbound/suppression` — agrega email manualmente a lista de supresión.

### 9. Frontend React

Crea las páginas dentro del shell de navegación existente. Protégelas con el mismo guard de auth.

- **`OutboundDashboard.jsx`** — 4 tarjetas grandes: "Descubiertos esta semana", "Pendientes de aprobar", "Enviados", "Respuestas". Un gráfico de línea de 30 días con envíos vs respuestas. Usa `recharts` si no hay otra librería ya instalada.
- **`ApprovalQueue.jsx`** — lista paginada de `DraftCard`. Cada card muestra: empresa, contacto, título, score, tier, signals detectados, subject + body del email. Botones: Aprobar (verde), Editar (azul, abre inline editor), Rechazar (rojo, pide motivo opcional). Teclas rápidas: `A` para aprobar, `R` para rechazar, `E` para editar — esto hace que el dueño pueda procesar 15 drafts en 10 minutos.
- **`SuppressionList.jsx`** — tabla simple con search. Botón para agregar email manualmente.
- **`ICPConfigForm.jsx`** — formulario con secciones: filtros Apollo (tamaño, industrias, geo), pesos del scoring, brand voice (textarea), case studies (lista editable), email de notificación del dueño.

---

## GUARDRAILS (CRÍTICOS, NO LOS OMITAS)

1. **Cuotas en variables de entorno**, no hardcodeadas. `MAX_COMPANIES_PER_DAY`, `MAX_EMAILS_PER_DAY`, `MAX_SENDS_PER_HOUR`.
2. **Circuit breaker**: si una API externa (Apollo/Claude/Instantly) devuelve 5 errores seguidos, pausa el job durante 30 minutos y loggea.
3. **Cost ceiling de Claude**: si `SUM(claude_cost_usd)` del día > $5, detén `draft_emails` y loggea alerta. El dueño sube el límite manualmente.
4. **Idempotencia**: `add_lead_to_campaign` debe ser idempotente por email. Si ya existe en la campaña, no dupliques.
5. **Logs estructurados** con `structlog` (o el logger existente). Campos: `job_name`, `prospect_id`, `stage`, `duration_ms`, `external_api`, `cost_usd`.
6. **Tests unitarios obligatorios** para: `icp_scorer.score_company` (al menos 5 casos: fit perfecto, tamaño fuera, industria fuera, geo fuera, señales ausentes), `suppression.is_suppressed`, `email_drafter.build_user_prompt`. Usa `pytest` con fixtures. Mockea las APIs externas con `respx` o `responses`.
7. **No escribas el contenido del email en logs** (puede tener PII). Solo guarda métricas agregadas.
8. **Migrations reversibles**: usa Alembic (Postgres/MySQL) o scripts con `down()` equivalente.

---

## PLAN DE EJECUCIÓN EN FASES

**No hagas todo de una vez.** Ejecuta en este orden y PARA después de cada fase para que yo valide antes de seguir:

### FASE 1 — Esqueleto + Apollo (detén y pregúntame cuando termines)
- Crea migraciones de los 5 modelos.
- Implementa `apollo_client.py` + tests.
- Implementa `icp_scorer.py` + tests (5+ casos).
- Endpoint `POST /api/outbound/icp-config` + `GET`.
- Job A (`discover_prospects`) funcionando end-to-end.
- Frontend: solo `ICPConfigForm.jsx` por ahora.
- Ejecuta los tests, muéstrame resultados, y PARA.

### FASE 2 — Claude + cola de aprobación (después de que apruebe Fase 1)
- Implementa `claude_client.py` con prompt caching.
- Implementa `email_drafter.py` + tests.
- Implementa `suppression.py` + tests.
- Job B (`draft_emails`).
- Endpoints de approvals.
- Frontend: `ApprovalQueue.jsx` + `DraftCard.jsx` con teclas rápidas.
- Tests.
- PARA y espera mi review.

### FASE 3 — Instantly + envío + métricas (después de aprobación)
- Implementa `instantly_client.py`.
- Job C (`send_approved_emails`).
- Job D (`sync_replies_and_stats`).
- Endpoint de unsubscribe.
- Frontend: `OutboundDashboard.jsx` + `SuppressionList.jsx`.
- Tests.

### FASE 4 — Hardening (al final)
- Circuit breakers.
- Cost ceiling.
- Alertas por email al dueño.
- Documentación en `outbound/README.md` con diagramas ASCII del flujo.

---

## CONVENCIONES

- Python: type hints obligatorios en todas las funciones públicas. `black` + `ruff`. No uses `Any` salvo que no haya alternativa.
- React: functional components + hooks. TailwindCSS si el proyecto ya lo usa, si no, CSS modules.
- Commits: uno por módulo con mensaje tipo `feat(outbound): add apollo client with rate limiting`.
- Nada de `print()`: usa el logger.
- Nada de secrets en código: todo vía `os.environ` / `.env`.
- Si encuentras una decisión arquitectónica importante donde dudas, PREGUNTA antes de codear. No asumas.

---

## EMPIEZA AHORA

1. Primero, lee el proyecto: dime qué framework backend tiene, qué base de datos, y cómo está estructurado el módulo de "info de empresas" existente.
2. Luego propón qué vas a reutilizar y qué vas a crear nuevo.
3. Espera mi "adelante" antes de escribir código.
4. Ejecuta Fase 1 y PARA.
