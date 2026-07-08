"""
Multi-agent WhatsApp assistants (via WAHA).

Each agent has its own persona (system prompt + greeting), its own WhatsApp
number/session, and its own RAG knowledge base. Agents can be saved as reusable
templates — templates keep only the prompts (persona), never the connected number
or uploaded files.

Collections:
  wa_agents           — {user_id, name, profile, system_prompt, greeting,
                         temperature, enabled, session_id, created_at, updated_at}
  wa_agent_templates  — {user_id, name, profile, description, system_prompt,
                         greeting, built_in, created_at}
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from backend.database import get_collection
from backend.agent_hub import rag

AGENTS_COL = "wa_agents"
TEMPLATES_COL = "wa_agent_templates"

MAX_HISTORY = 10


# ── Built-in profile templates (persona only, no data) ───────────────────────
# Seeded as read-only starting points; the user can save their own on top.
BUILTIN_TEMPLATES = [
    {
        "key": "ventas",
        "name": "Ventas",
        "profile": "ventas",
        "description": "Asesor comercial que califica, resuelve dudas y cierra ventas.",
        "greeting": "¡Hola! 👋 Soy tu asesor comercial. ¿En qué producto o servicio estás interesado?",
        "system_prompt": (
            "Eres un asesor comercial experto y cercano que atiende por WhatsApp. "
            "Tu objetivo es entender la necesidad del cliente, presentar el producto o "
            "servicio adecuado, resolver objeciones y guiar hacia el cierre de la venta. "
            "Sé breve, cálido y persuasivo; haz una pregunta a la vez. Usa la información "
            "de la base de conocimiento (catálogo, precios, promociones) cuando exista y "
            "nunca inventes datos, precios ni disponibilidad. Si no tienes el dato, ofrece "
            "conseguirlo. Responde siempre en el idioma del cliente."
        ),
    },
    {
        "key": "soporte",
        "name": "Atención al cliente",
        "profile": "atencion",
        "description": "Soporte y atención al cliente para dudas, incidencias y seguimiento.",
        "greeting": "¡Hola! 😊 Soy el equipo de atención al cliente. ¿Cómo puedo ayudarte hoy?",
        "system_prompt": (
            "Eres un agente de atención al cliente empático y resolutivo que responde por "
            "WhatsApp. Ayudas con dudas, incidencias, estados de pedido y reclamos. Sé "
            "claro, paciente y orientado a resolver. Usa la base de conocimiento (políticas, "
            "FAQ, procedimientos) para dar respuestas exactas y no inventes información. Si "
            "un caso requiere un humano, indícalo y toma los datos necesarios. Responde en "
            "el idioma del cliente."
        ),
    },
    {
        "key": "soporte_tecnico",
        "name": "Soporte técnico",
        "profile": "soporte_tecnico",
        "description": "Diagnostica problemas técnicos y guía paso a paso.",
        "greeting": "¡Hola! 🛠️ Soporte técnico al habla. Cuéntame qué problema estás teniendo.",
        "system_prompt": (
            "Eres un especialista de soporte técnico que atiende por WhatsApp. Diagnosticas "
            "problemas haciendo preguntas concretas y guías al usuario paso a paso con "
            "instrucciones simples. Apóyate en la base de conocimiento (manuales, guías de "
            "resolución) y no inventes pasos ni especificaciones. Si el problema excede el "
            "soporte de primer nivel, escálalo y recoge la información relevante. Responde en "
            "el idioma del usuario."
        ),
    },
    {
        "key": "reservas",
        "name": "Reservas y citas",
        "profile": "reservas",
        "description": "Agenda citas y reservas, confirma horarios y datos.",
        "greeting": "¡Hola! 📅 Puedo ayudarte a agendar tu cita. ¿Qué día y hora te vienen bien?",
        "system_prompt": (
            "Eres un asistente de reservas que atiende por WhatsApp. Ayudas a agendar citas "
            "o reservas, confirmas fecha, hora y datos de contacto, y recuerdas las políticas "
            "de cancelación. Usa la base de conocimiento (horarios, servicios, disponibilidad) "
            "cuando exista y no confirmes horarios que no puedas verificar. Sé ágil y cordial. "
            "Responde en el idioma del cliente."
        ),
    },
    {
        "key": "general",
        "name": "Asistente general",
        "profile": "general",
        "description": "Asistente versátil para cualquier consulta del negocio.",
        "greeting": "¡Hola! 👋 ¿En qué puedo ayudarte?",
        "system_prompt": (
            "Eres un asistente virtual del negocio que atiende por WhatsApp. Respondes "
            "consultas de forma clara, útil y amable, apoyándote en la base de conocimiento "
            "cuando exista. No inventes datos: si no sabes algo, dilo y ofrece una alternativa. "
            "Responde en el idioma del cliente."
        ),
    },
]


def _clean(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    for k in ("created_at", "updated_at"):
        if hasattr(doc.get(k), "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


# ── Agent CRUD ───────────────────────────────────────────────────────────────

async def create_agent(user_id: str, data: dict) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "name": (data.get("name") or "Nuevo agente").strip()[:80],
        "profile": (data.get("profile") or "general").strip()[:40],
        "system_prompt": (data.get("system_prompt") or "").strip(),
        "greeting": (data.get("greeting") or "").strip(),
        "temperature": float(data.get("temperature", 0.5)),
        "enabled": bool(data.get("enabled", True)),
        "session_id": None,
        "created_at": now,
        "updated_at": now,
    }
    res = await get_collection(AGENTS_COL).insert_one(doc)
    doc["_id"] = res.inserted_id
    return _clean(doc)


async def list_agents(user_id: str) -> list[dict]:
    docs = await get_collection(AGENTS_COL).find({"user_id": user_id}).sort("created_at", -1).to_list(100)
    out = []
    for d in docs:
        d = _clean(d)
        # attach lightweight extras: file count + session status
        d["file_count"] = await get_collection(rag.FILES_COL).count_documents({"agent_id": d["_id"]})
        d["session_status"] = await _session_status(user_id, d.get("session_id"))
        out.append(d)
    return out


async def get_agent(user_id: str, agent_id: str) -> Optional[dict]:
    try:
        doc = await get_collection(AGENTS_COL).find_one({"_id": ObjectId(agent_id), "user_id": user_id})
    except Exception:
        return None
    if not doc:
        return None
    d = _clean(doc)
    d["file_count"] = await get_collection(rag.FILES_COL).count_documents({"agent_id": d["_id"]})
    d["session_status"] = await _session_status(user_id, d.get("session_id"))
    return d


async def get_agent_by_session(session_id: str) -> Optional[dict]:
    doc = await get_collection(AGENTS_COL).find_one({"session_id": session_id})
    return _clean(doc) if doc else None


async def update_agent(user_id: str, agent_id: str, data: dict) -> Optional[dict]:
    fields = {}
    for k in ("name", "profile", "system_prompt", "greeting"):
        if k in data and data[k] is not None:
            fields[k] = str(data[k]).strip()
    if "temperature" in data and data["temperature"] is not None:
        try:
            fields["temperature"] = max(0.0, min(1.5, float(data["temperature"])))
        except (TypeError, ValueError):
            pass
    if "enabled" in data and data["enabled"] is not None:
        fields["enabled"] = bool(data["enabled"])
    if not fields:
        return await get_agent(user_id, agent_id)
    fields["updated_at"] = datetime.now(timezone.utc)
    try:
        res = await get_collection(AGENTS_COL).update_one(
            {"_id": ObjectId(agent_id), "user_id": user_id}, {"$set": fields}
        )
    except Exception:
        return None
    if res.matched_count == 0:
        return None
    return await get_agent(user_id, agent_id)


async def bind_session(user_id: str, agent_id: str, session_id: str | None) -> None:
    await get_collection(AGENTS_COL).update_one(
        {"_id": ObjectId(agent_id), "user_id": user_id},
        {"$set": {"session_id": session_id, "updated_at": datetime.now(timezone.utc)}},
    )


async def delete_agent(user_id: str, agent_id: str) -> bool:
    col = get_collection(AGENTS_COL)
    doc = await col.find_one({"_id": ObjectId(agent_id), "user_id": user_id})
    if not doc:
        return False
    # Tear down the linked WhatsApp session (best-effort).
    if doc.get("session_id"):
        try:
            from backend.agent_hub.integrations.whatsapp import delete_session
            await delete_session(doc["session_id"])
        except Exception:
            pass
    # Drop the agent's knowledge base (files + chunks).
    files = await get_collection(rag.FILES_COL).find({"agent_id": agent_id}).to_list(None)
    for f in files:
        try:
            await rag.delete_file(user_id, str(f["_id"]))
        except Exception:
            pass
    await col.delete_one({"_id": ObjectId(agent_id)})
    return True


async def _session_status(user_id: str, session_id: str | None) -> Optional[dict]:
    if not session_id:
        return None
    doc = await get_collection("agent_whatsapp_sessions").find_one(
        {"session_id": session_id, "user_id": user_id}
    )
    if not doc:
        return None
    return {
        "session_id": session_id,
        "status": doc.get("status", "UNKNOWN"),
        "phone_number": doc.get("phone_number"),
        "display_name": doc.get("display_name", ""),
    }


# ── Templates ────────────────────────────────────────────────────────────────

async def list_templates(user_id: str) -> list[dict]:
    """Built-in personas + the user's saved templates (persona only, no data)."""
    builtin = [
        {
            "_id": f"builtin:{t['key']}",
            "built_in": True,
            "name": t["name"],
            "profile": t["profile"],
            "description": t["description"],
            "greeting": t["greeting"],
            "system_prompt": t["system_prompt"],
        }
        for t in BUILTIN_TEMPLATES
    ]
    docs = await get_collection(TEMPLATES_COL).find({"user_id": user_id}).sort("created_at", -1).to_list(100)
    saved = [{**_clean(d), "built_in": False} for d in docs]
    return builtin + saved


async def save_as_template(user_id: str, agent_id: str, name: str | None = None) -> Optional[dict]:
    """Persist an agent's PERSONA as a reusable template — prompts only, no data."""
    agent = await get_collection(AGENTS_COL).find_one({"_id": ObjectId(agent_id), "user_id": user_id})
    if not agent:
        return None
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "name": (name or agent.get("name") or "Plantilla").strip()[:80],
        "profile": agent.get("profile", "general"),
        "description": f"Plantilla basada en «{agent.get('name', '')}»",
        # Only the persona travels — never the session or the RAG files.
        "system_prompt": agent.get("system_prompt", ""),
        "greeting": agent.get("greeting", ""),
        "built_in": False,
        "created_at": now,
    }
    res = await get_collection(TEMPLATES_COL).insert_one(doc)
    doc["_id"] = res.inserted_id
    return _clean(doc)


async def create_from_template(user_id: str, template_id: str, name: str | None = None) -> Optional[dict]:
    tpl = None
    if template_id.startswith("builtin:"):
        key = template_id.split(":", 1)[1]
        tpl = next((t for t in BUILTIN_TEMPLATES if t["key"] == key), None)
    else:
        try:
            tpl = await get_collection(TEMPLATES_COL).find_one(
                {"_id": ObjectId(template_id), "user_id": user_id}
            )
        except Exception:
            tpl = None
    if not tpl:
        return None
    return await create_agent(user_id, {
        "name": name or tpl.get("name", "Nuevo agente"),
        "profile": tpl.get("profile", "general"),
        "system_prompt": tpl.get("system_prompt", ""),
        "greeting": tpl.get("greeting", ""),
        "enabled": True,
    })


async def delete_template(user_id: str, template_id: str) -> bool:
    if template_id.startswith("builtin:"):
        return False  # built-ins are read-only
    try:
        res = await get_collection(TEMPLATES_COL).delete_one(
            {"_id": ObjectId(template_id), "user_id": user_id}
        )
    except Exception:
        return False
    return res.deleted_count > 0


# ── Runtime: answer a WhatsApp message with this agent's persona + RAG ────────

async def run_agent_turn(agent: dict, user_id: str, user_text: str,
                         history: list[dict]) -> str:
    """
    Build the agent's system prompt (persona + retrieved knowledge) and answer.
    Uses the shared free-tier model gateway with graceful fallback.
    """
    from backend.agent_hub import gateway
    from backend.agent_hub.gateway import AllModelsExhausted

    agent_id = agent["_id"] if isinstance(agent["_id"], str) else str(agent["_id"])
    context = await rag.search_context(user_id, user_text, max_chunks=5, agent_id=agent_id)

    system = agent.get("system_prompt") or "Eres un asistente que atiende por WhatsApp."
    if context:
        system += (
            "\n\n--- BASE DE CONOCIMIENTO ---\n"
            "Usa esta información para responder con precisión. Si la respuesta no está aquí, "
            "no la inventes.\n\n" + context
        )

    messages = [{"role": "system", "content": system}]
    for m in history[-MAX_HISTORY:]:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    try:
        resp = await gateway.route("text", messages)
        return (resp.content or "").strip() or "¿Puedes darme un poco más de detalle? 🙂"
    except AllModelsExhausted:
        return "En este momento no puedo responder. Intenta de nuevo en unos minutos. 🙏"
    except Exception as e:
        return f"Ocurrió un problema procesando tu mensaje. ({str(e)[:60]})"
