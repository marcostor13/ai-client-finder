"""
Email Drafter — generates personalized cold emails using the LLM router.
"""
from datetime import datetime, timezone

from backend.database import get_collection
from backend.outbound import llm_router

_CALENDLY_BUTTON_TEXT = "Reservar 15 minutos →"

_SYSTEM_TEMPLATE = """Eres un especialista en outbound B2B para una agencia de desarrollo de software a medida.
Tu tarea es escribir un email de prospección en español, frío pero hiperpersonalizado, para el decisor de una empresa.

ANÁLISIS OBLIGATORIO DE LA EMPRESA (hazlo antes de escribir):
- Identifica su sector exacto y el problema más probable que tiene con su presencia digital o procesos internos.
- Conecta ese problema con lo que la agencia puede resolver de forma concreta.
- Si tiene señales de falta de digitalización: menciona el costo que está perdiendo.
- Si ya tiene presencia digital: identifica qué mejorar (velocidad, automatización, conversión).
- La propuesta debe sentirse AGRESIVA y ATRACTIVA: enfócate en el resultado económico, no en la tecnología.

REGLAS DURAS (no las rompas):
- Máximo 130 palabras en el cuerpo del email.
- Asunto: entre 6 y 9 palabras, sin signos de exclamación. Debe generar curiosidad o urgencia real.
- La llamada a la acción final debe siempre incluir el link de Calendly: {calendly_url}
- No uses spam words: "gratis", "oferta", "urgente", "exclusivo".
- Firma siempre con: "{owner_name}"
- El email debe cerrar con una pregunta o frase que invite a reservar la cita.

VOZ DE MARCA:
{brand_voice}

CASOS DE ÉXITO (cita uno si es relevante para esta empresa):
{case_studies}

FORMATO DE RESPUESTA (obligatorio, exactamente así):
ASUNTO: [asunto aquí]

[cuerpo del email aquí]

[firma con nombre y link de Calendly]"""

_DEFAULT_BRAND_VOICE = (
    "Tono directo y cercano. Enfócate en el problema del cliente, "
    "no en la tecnología. Sé breve y concreto."
)
_DEFAULT_OWNER = "Marcos Torres"
_DEFAULT_CALENDLY = "https://calendly.com/marcostor13/new-meeting"


def build_system_prompt(icp_config: dict) -> str:
    brand_voice = icp_config.get("brand_voice") or _DEFAULT_BRAND_VOICE
    case_studies = icp_config.get("case_studies") or []
    cs_text = (
        "\n".join(f"- {cs}" for cs in case_studies if cs.strip())
        or "- (configura tus casos de éxito en ICP Config)"
    )
    owner = icp_config.get("owner_name") or _DEFAULT_OWNER
    calendly = icp_config.get("calendly_url") or _DEFAULT_CALENDLY
    return _SYSTEM_TEMPLATE.format(
        brand_voice=brand_voice,
        case_studies=cs_text,
        owner_name=owner,
        calendly_url=calendly,
    )


def build_user_prompt(prospect: dict) -> str:
    company = prospect.get("company_name", "la empresa")
    domain = prospect.get("company_domain", "")
    description = (prospect.get("description") or "")[:200]
    location = prospect.get("location", "")
    contact_name = prospect.get("contact_full_name") or "el decisor"
    contact_title = prospect.get("contact_title") or "responsable"
    signals = prospect.get("signals_detected") or []
    score = prospect.get("icp_score", 0)
    website = prospect.get("website", "")

    signals_text = ", ".join(signals) if signals else "ninguna detectada"

    return (
        f"Empresa: {company}\n"
        f"Sitio web: {website or domain}\n"
        f"Descripción: {description}\n"
        f"Ubicación: {location}\n"
        f"Contacto: {contact_name} ({contact_title})\n"
        f"ICP score: {score}/100\n"
        f"Señales detectadas: {signals_text}\n\n"
        f"INSTRUCCIÓN: Analiza a fondo la empresa '{company}' basándote en su descripción y señales. "
        f"Identifica su mayor punto de dolor digital y escribe una propuesta agresiva y atractiva "
        f"que resuelva ese problema específico. Dirige el email a {contact_name}. "
        f"Termina con el link de Calendly para reservar la reunión."
    )


def _parse_response(text: str) -> tuple[str, str]:
    """Returns (subject, body) from LLM output."""
    lines = text.strip().splitlines()
    subject = ""
    body_lines: list[str] = []
    in_body = False

    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("ASUNTO:"):
            subject = stripped[7:].strip()
        elif subject and not in_body:
            if stripped == "":
                in_body = True
            else:
                in_body = True
                body_lines.append(line)
        elif in_body:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    if not subject and lines:
        subject = lines[0].strip()[:80]
        body = "\n".join(lines[1:]).strip()

    return subject, body


_CALENDLY_BTN_HTML = (
    '<div style="margin:24px 0 8px;">'
    '<a href="https://calendly.com/marcostor13/new-meeting" '
    'style="display:inline-block;padding:13px 28px;background:#6D28D9;color:#ffffff;'
    'text-decoration:none;border-radius:8px;font-weight:700;font-size:15px;'
    'font-family:Inter,sans-serif;letter-spacing:0.02em;">'
    'Reservar 15 minutos &rarr;'
    '</a>'
    '</div>'
)


def _to_html(body_text: str) -> str:
    paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]
    html_body = "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
    if "calendly.com" not in body_text:
        html_body += _CALENDLY_BTN_HTML
    return html_body


async def draft_email(prospect: dict, icp_config: dict) -> dict:
    """
    Generates and persists an EmailDraft for the given prospect.
    Returns the saved draft document. Idempotent: returns existing draft if one exists.
    """
    from bson import ObjectId

    prospect_id = str(prospect["_id"])
    drafts_col = get_collection("outbound_email_drafts")
    prospects_col = get_collection("outbound_prospects")

    existing = await drafts_col.find_one(
        {"prospect_id": prospect_id, "status": {"$in": ["pending_approval", "approved"]}}
    )
    if existing:
        existing["_id"] = str(existing["_id"])
        return existing

    system = build_system_prompt(icp_config)
    user_msg = build_user_prompt(prospect)

    response_text, provider, model = await llm_router.chat(
        messages=[{"role": "user", "content": user_msg}],
        system=system,
        temperature=0.4,
    )

    subject, body_text = _parse_response(response_text)
    body_html = _to_html(body_text)

    signals = prospect.get("signals_detected") or []
    notes = f"Señales usadas: {', '.join(signals)}" if signals else ""

    now = datetime.now(timezone.utc).isoformat()
    draft_doc = {
        "prospect_id": prospect_id,
        "contact_email": prospect.get("contact_email", ""),
        "company_name": prospect.get("company_name", ""),
        "contact_full_name": prospect.get("contact_full_name", ""),
        "icp_score": prospect.get("icp_score", 0),
        "tier": prospect.get("tier", ""),
        "signals_detected": signals,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "personalization_notes": notes,
        "status": "pending_approval",
        "reviewed_by": None,
        "reviewed_at": None,
        "sent_at": None,
        "llm_provider": provider,
        "llm_model": model,
        "llm_cost_usd": 0.0,
        "created_at": now,
        "updated_at": now,
    }

    result = await drafts_col.insert_one(draft_doc)
    draft_doc["_id"] = str(result.inserted_id)

    await prospects_col.update_one(
        {"_id": ObjectId(prospect_id)},
        {"$set": {"status": "drafted", "updated_at": now}},
    )

    print(f"[drafter] drafted for {prospect.get('company_name')} via {provider}/{model}")
    return draft_doc
