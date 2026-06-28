"""
Herramientas (tool use) del Coach — le dan manos al agente.

Define los esquemas en formato Anthropic y un ejecutor async que mapea cada
herramienta a las integraciones ya existentes:
  - Outlook / Microsoft Graph (calendario): ver / agendar / cancelar reuniones
  - WhatsApp vía WAHA: enviar mensajes desde la cuenta conectada
  - Metas del coach (coach_goals) y memoria (coach_knowledge)

El agente decide cuándo llamarlas; este módulo las ejecuta y devuelve un texto
que vuelve al modelo como tool_result. Todo va contra el mismo user_id, así que
usa las credenciales que Marcos ya conectó en cada integración.
"""
from datetime import datetime, timedelta

from zoneinfo import ZoneInfo

from backend.database import get_collection

LIMA = ZoneInfo("America/Lima")


# ── Esquemas de herramientas (formato Anthropic) ─────────────────────────────

TOOLS = [
    {
        "name": "get_calendar",
        "description": (
            "Lista los eventos del calendario de Outlook de Marcos en un rango de fechas. "
            "Úsalo antes de agendar para evitar choques de horario, o cuando pregunte qué "
            "tiene agendado. Devuelve los eventos con su id (necesario para cancelar)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Fecha de inicio del rango, formato YYYY-MM-DD (hora Lima). Por defecto hoy.",
                },
                "days": {
                    "type": "integer",
                    "description": "Cuántos días cubrir desde start_date. Por defecto 7.",
                },
            },
        },
    },
    {
        "name": "create_meeting",
        "description": (
            "Agenda una reunión/evento en el calendario de Outlook de Marcos. Confirma fecha, "
            "hora, con quién y para qué antes de llamar. Las horas son hora local de Lima."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Título de la reunión."},
                "start": {
                    "type": "string",
                    "description": "Inicio en hora Lima, formato 'YYYY-MM-DDTHH:MM:SS' (ej. 2026-06-28T15:00:00).",
                },
                "end": {
                    "type": "string",
                    "description": "Fin en hora Lima, mismo formato. Si no se sabe, usa 1 hora después del inicio.",
                },
                "body": {"type": "string", "description": "Notas/agenda de la reunión (opcional)."},
                "location": {"type": "string", "description": "Lugar o enlace (opcional)."},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Correos de los invitados (opcional).",
                },
            },
            "required": ["subject", "start", "end"],
        },
    },
    {
        "name": "cancel_meeting",
        "description": (
            "Cancela/elimina un evento del calendario de Outlook por su id. "
            "Primero usa get_calendar para obtener el id correcto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "id del evento a cancelar (de get_calendar)."},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "send_whatsapp",
        "description": (
            "Envía un mensaje de WhatsApp desde la cuenta de Marcos conectada por WAHA. "
            "Úsalo solo cuando Marcos lo pida explícitamente. Confirma destinatario y texto antes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Número de teléfono con código de país, solo dígitos (ej. 51999888777).",
                },
                "text": {"type": "string", "description": "Texto del mensaje a enviar."},
            },
            "required": ["to", "text"],
        },
    },
    {
        "name": "add_goal",
        "description": "Agrega una meta/tarea/recordatorio a la lista de Marcos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Descripción de la meta o tarea."},
                "horizon": {
                    "type": "string",
                    "enum": ["today", "short", "mid", "long"],
                    "description": "Horizonte: today=hoy/urgente, short=0-3m, mid=3-6m, long=6-18m. Por defecto today.",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "complete_goal",
        "description": "Marca una meta/tarea como completada por su código (los últimos 6 caracteres del id).",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Código de la tarea (ver lista de metas)."},
            },
            "required": ["code"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Guarda en memoria un dato útil (un cliente, una decisión, un número, una preferencia, "
            "una reunión) para recordarlo en futuras conversaciones."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "El dato a recordar, en una o dos frases."},
            },
            "required": ["content"],
        },
    },
]


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _active_whatsapp_session(user_id: str) -> str | None:
    """Sesión WAHA conectada del usuario (WORKING preferida; si no, la más reciente)."""
    col = get_collection("agent_whatsapp_sessions")
    doc = await col.find_one({"user_id": user_id, "status": "WORKING"})
    if not doc:
        doc = await col.find_one({"user_id": user_id}, sort=[("created_at", -1)])
    return doc["session_id"] if doc else None


def _today_lima_date() -> str:
    return datetime.now(LIMA).strftime("%Y-%m-%d")


# ── Ejecutor ─────────────────────────────────────────────────────────────────

async def execute_tool(user_id: str, name: str, args: dict) -> str:
    """Ejecuta una herramienta y devuelve un texto para el tool_result."""
    try:
        if name == "get_calendar":
            from backend.agent_hub.integrations import outlook
            start_date = args.get("start_date") or _today_lima_date()
            days = int(args.get("days") or 7)
            start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=LIMA)
            end = start + timedelta(days=days)
            events = await outlook.get_calendar_events(user_id, start, end)
            if not events:
                return "No hay eventos en ese rango."
            lines = []
            for e in events:
                t = e.get("start", {}).get("dateTime", "")[:16].replace("T", " ")
                loc = e.get("location", {}).get("displayName", "")
                lines.append(
                    f"- [{e.get('id', '')[-12:]}] {t} — {e.get('subject', 'Sin título')}"
                    + (f" ({loc})" if loc else "")
                )
            return "Eventos:\n" + "\n".join(lines)

        if name == "create_meeting":
            from backend.agent_hub.integrations import outlook
            start = args["start"]
            end = args.get("end")
            if not end:
                dt = datetime.fromisoformat(start)
                end = (dt + timedelta(hours=1)).isoformat(timespec="seconds")
            ev = await outlook.create_event(
                user_id,
                subject=args["subject"],
                start=start,
                end=end,
                body=args.get("body", ""),
                location=args.get("location", ""),
                attendees=args.get("attendees"),
                time_zone="America/Lima",
            )
            return f"✅ Reunión agendada: «{args['subject']}» el {start[:16].replace('T', ' ')} (id {ev.get('id', '')[-12:]})."

        if name == "cancel_meeting":
            from backend.agent_hub.integrations import outlook
            await outlook.delete_event(user_id, args["event_id"])
            return "✅ Evento cancelado."

        if name == "send_whatsapp":
            from backend.agent_hub.integrations import whatsapp
            session_id = await _active_whatsapp_session(user_id)
            if not session_id:
                return "No hay una sesión de WhatsApp conectada. Conéctala en el panel (escanea el QR) y reintenta."
            digits = "".join(c for c in str(args["to"]) if c.isdigit())
            if not digits:
                return "Número inválido: indica el teléfono con código de país, solo dígitos."
            chat_id = f"{digits}@c.us"
            await whatsapp.send_message(session_id, chat_id, args["text"])
            return f"✅ WhatsApp enviado a {digits}."

        if name == "add_goal":
            from backend.agent_hub import coach
            gid = await coach.add_goal(user_id, args["title"], args.get("horizon", "today"), source="coach")
            return f"✅ Meta agregada [{gid[-6:]}]: {args['title']}"

        if name == "complete_goal":
            from backend.agent_hub import coach
            code = str(args["code"]).strip()
            goals = await coach.list_goals(user_id)
            match = next((g for g in goals if g["_id"][-6:] == code or g["_id"] == code), None)
            if not match:
                return f"No encontré la tarea «{code}»."
            await coach.set_goal_status(user_id, match["_id"], "done")
            return f"✅ Completada: «{match['title']}»."

        if name == "save_memory":
            from backend.agent_hub import coach
            await coach.save_knowledge(user_id, args["content"], source="coach")
            return "✅ Guardado en memoria."

        return f"Herramienta desconocida: {name}"
    except Exception as exc:  # noqa: BLE001 — el error vuelve al modelo como tool_result
        return f"Error al ejecutar {name}: {str(exc)[:200]}"
