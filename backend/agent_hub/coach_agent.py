"""
Loop agéntico del Coach — corre el ciclo de tool use con DeepSeek.

El gateway de modelos enruta texto pero no maneja function calling de forma
controlada; este módulo corre el loop de herramientas directamente contra
DeepSeek (API compatible con OpenAI, usa DEEPSEEK_API_KEY) para que el coach
EJECUTE acciones (agendar reuniones, WhatsApp, metas, memoria). Si DeepSeek no
está disponible o falla, cae al gateway de texto normal con el mismo contexto.

Uso:
    reply = await run_coach_turn(user_id, user_text, history)
donde `history` es una lista [{role, content}] de turnos previos (texto plano).
"""
import json
import os

import httpx

from backend.agent_hub import coach, coach_tools

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_TOOL_ITERS = 6


def _has_llm() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def _openai_tools() -> list[dict]:
    """Convierte los esquemas (formato Anthropic) al formato de OpenAI/DeepSeek."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in coach_tools.TOOLS
    ]


async def _fallback_to_gateway(user_id: str, user_text: str, history: list[dict]) -> str:
    """Sin DeepSeek o ante error: usa el gateway de texto con el contexto del coach (sin tools)."""
    from backend.agent_hub import gateway
    context = await coach.build_context(user_id, query=user_text, with_tools=False)
    messages = context + history + [{"role": "user", "content": user_text}]
    intent = await gateway.detect_intent(user_text)
    result = await gateway.route(intent, messages)
    if result.image_url:
        return f"[Imagen]: {result.image_url}"
    return result.content


async def _chat(messages: list[dict], tools: list[dict] | None) -> dict:
    """Una llamada a DeepSeek; devuelve el message del primer choice."""
    payload: dict = {"model": MODEL, "messages": messages, "temperature": 0.4}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    headers = {"Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}"}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(DEEPSEEK_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]


async def run_coach_turn(user_id: str, user_text: str, history: list[dict]) -> str:
    """Procesa un turno del coach con herramientas. Devuelve el texto de respuesta."""
    if not _has_llm():
        return await _fallback_to_gateway(user_id, user_text, history)

    # Contexto del coach (persona + plan + metas + conocimiento + nota de tools) como system.
    context_msgs = await coach.build_context(user_id, query=user_text, with_tools=True)
    system = "\n\n".join(m["content"] for m in context_msgs if m["role"] == "system")

    messages: list[dict] = [{"role": "system", "content": system}]
    for m in history:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_text})

    tools = _openai_tools()

    try:
        for _ in range(MAX_TOOL_ITERS):
            msg = await _chat(messages, tools)
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                return (msg.get("content") or "").strip() or "Listo."

            # Reinyecta el turno del asistente (debe incluir los tool_calls) + resultados.
            messages.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                out = await coach_tools.execute_tool(user_id, name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": out,
                })

        # Se agotaron las iteraciones: cierre breve sin más herramientas.
        final = await _chat(messages, None)
        return (final.get("content") or "").strip() or "Listo."
    except Exception:
        # Cualquier fallo de DeepSeek → degradar al gateway sin romper la conversación.
        return await _fallback_to_gateway(user_id, user_text, history)
