"""
Loop agéntico del Coach — corre el ciclo de tool use con Claude.

El gateway de modelos (free-tier) no soporta function calling, así que el coach
usa Claude (CLAUDE_API_KEY) directamente cuando necesita ejecutar acciones
(agendar reuniones, WhatsApp, metas, memoria). Si Claude no está disponible,
cae al gateway de texto normal con el mismo contexto.

Uso:
    reply = await run_coach_turn(user_id, user_text, history)
donde `history` es una lista [{role, content}] de turnos previos (texto plano).
"""
import os

from anthropic import AsyncAnthropic

from backend.agent_hub import coach, coach_tools

MODEL = "claude-opus-4-8"
MAX_TOOL_ITERS = 6


def _has_claude() -> bool:
    return bool(os.getenv("CLAUDE_API_KEY"))


async def _fallback_to_gateway(user_id: str, user_text: str, history: list[dict]) -> str:
    """Sin Claude o ante error: usa el gateway de texto con el contexto del coach."""
    from backend.agent_hub import gateway
    context = await coach.build_context(user_id, query=user_text, with_tools=False)
    messages = context + history + [{"role": "user", "content": user_text}]
    intent = await gateway.detect_intent(user_text)
    result = await gateway.route(intent, messages)
    if result.image_url:
        return f"[Imagen]: {result.image_url}"
    return result.content


async def run_coach_turn(user_id: str, user_text: str, history: list[dict]) -> str:
    """Procesa un turno del coach con herramientas. Devuelve el texto de respuesta."""
    if not _has_claude():
        return await _fallback_to_gateway(user_id, user_text, history)

    # El contexto del coach (persona + plan + metas + conocimiento + nota de tools) va como system.
    context_msgs = await coach.build_context(user_id, query=user_text, with_tools=True)
    system = "\n\n".join(m["content"] for m in context_msgs if m["role"] == "system")

    messages: list[dict] = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    # Anthropic exige que el primer mensaje sea 'user': descarta turnos assistant iniciales.
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    messages.append({"role": "user", "content": user_text})

    client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))

    try:
        for _ in range(MAX_TOOL_ITERS):
            resp = await client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=system,
                tools=coach_tools.TOOLS,
                messages=messages,
            )

            if resp.stop_reason != "tool_use":
                return _first_text(resp) or "Listo."

            # Ejecuta cada tool_use y devuelve los resultados en un solo turno user.
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = await coach_tools.execute_tool(user_id, block.name, block.input or {})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": out,
                    })
            messages.append({"role": "user", "content": tool_results})

        # Se agotaron las iteraciones: pide un cierre breve sin más herramientas.
        final = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return _first_text(final) or "Listo."
    except Exception:
        # Cualquier fallo de Claude → degradar al gateway sin romper la conversación.
        return await _fallback_to_gateway(user_id, user_text, history)


def _first_text(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
