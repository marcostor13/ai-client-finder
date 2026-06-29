"""
Coach proactivo — cron (apscheduler) en zona Lima. Genera mensajes enfocados en
el plan de Marcos y los envía por Telegram. El estado (activado + chat_id +
horarios) vive en MongoDB (coach_config), así que sobrevive reinicios y la
frecuencia es configurable por usuario desde el dashboard.

Cada usuario con coach activo tiene sus propios jobs:
  morning / midday / evening  → diarios a la hora elegida
  money                       → viernes
  weekly                      → domingo
  enrich                      → miércoles (pide autorización para guardar RAG)
Un horario vacío ("") desactiva ese check-in.
"""
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.agent_hub import coach, gateway
from backend.agent_hub.gateway import AllModelsExhausted

scheduler = AsyncIOScheduler(timezone="America/Lima")
_started = False

# Día fijo de la semana para los check-ins no diarios (apscheduler day_of_week).
_KIND_DAY = {
    "morning": None, "midday": None, "evening": None,
    "money": "fri", "weekly": "sun", "enrich": "wed",
}

# Ventana horaria activa del pulso "hourly" (hora Lima). Corre en cada hora de
# este rango para no spamear de madrugada. El minuto sale del schedule del usuario.
HOURLY_HOURS = "8-22"

PROMPTS = {
    "morning": (
        "Es la mañana. Genera el mensaje de arranque del día para Marcos: salúdalo con "
        "energía, recuérdale su hábito clave (bloque de trabajo profundo de 90 min, sin "
        "celular, en lo de mayor S//día) y lístale en bullets las 2-3 tareas de HOY de mayor "
        "prioridad según sus metas vigentes. Cierra con una frase motivadora corta que "
        "refuerce su identidad de persona enfocada. Sé breve y concreto."
    ),
    "midday": (
        "Es mediodía. Recuérdale a Marcos hacer su acción de adquisición del día (10 mensajes "
        "en Sales Navigator a su nicho, o revisar la pauta). Luego pregúntale directamente si "
        "ya completó su bloque de trabajo profundo de la mañana. Una o dos frases, directo."
    ),
    "evening": (
        "Es la noche. Pídele a Marcos su reporte del día: pregúntale específicamente por cada "
        "tarea pendiente de HOY (menciónalas por su nombre) si la realizó o no. Dale feedback "
        "honesto y cálido sobre el avance, y recuérdale proteger el tiempo en familia sin "
        "celular. Si cumplió el hábito clave, celébralo (no romper la cadena)."
    ),
    "money": (
        "Es viernes: la 'cita con el dinero'. Guía a Marcos en 30 min: cobranzas pendientes, "
        "facturar lo entregado, actualizar su proyección de caja y PROVISIONAR impuestos de lo "
        "que entró. Pregúntale cuánto entró y cuánto sale esta semana. Recuérdale lo de "
        "contratar contador si sigue pendiente."
    ),
    "weekly": (
        "Es domingo: revisión semanal. Hazle a Marcos las 4 preguntas, una por una y numeradas: "
        "1) ¿cuánto entró y cuánto salió esta semana? 2) ¿qué proyecto avanzó a 'cobrable'? "
        "3) ¿mantuviste tu hábito clave (la cadena)? 4) ¿cuáles son tus 3 prioridades de la "
        "próxima semana? Cierra proponiendo enfoque para la semana que viene según el plan."
    ),
    "enrich": (
        "Propón a Marcos UN tema puntual y accionable relacionado con su plan (ej. un guion de "
        "mensaje de Sales Navigator para su nicho, una plantilla de cotización con precios "
        "subidos 30-50%, o un script para renegociar deuda) sobre el que podrías investigar y "
        "guardar el resultado en tu memoria para nutrirte. Explícalo en 2 frases y PIDE su "
        "autorización para guardarlo, diciéndole que responda 'sí guarda' para confirmarlo."
    ),
    "hourly": (
        "Es un pulso de cada hora. Analiza TODO el panorama de Marcos (sus metas vigentes en "
        "todos los horizontes, sus finanzas, sus hábitos y su plan de vida) y entrégale UNA "
        "sola intervención valiosa y variada — NO repitas el formato de los otros check-ins ni "
        "te repitas respecto a horas previas. Elige UN ángulo distinto cada vez entre: "
        "(a) una sugerencia concreta y accionable para avanzar ahora mismo, (b) una idea nueva "
        "(de negocio, ingreso, productividad o sistema) conectada a su plan, (c) un consejo u "
        "observación honesta sobre algo que podría estar descuidando, o (d) un reto corto para "
        "las próximas horas que lo saque de su zona de confort. Sé específico al plan, cálido y "
        "breve (máx 4-5 líneas). No saludes con 'buenos días'; es un pulso en medio del día. "
        "Empieza con un emoji que indique el ángulo elegido."
    ),
}


def _fallback(kind: str) -> str:
    msgs = {
        "morning": "☀️ Buenos días, Marcos. Bloque de trabajo profundo de 90 min AHORA, sin celular, en lo de mayor S//día. Empieza por abrir el editor. No rompas la cadena.",
        "midday": "🎯 Mediodía: ¿ya hiciste tu bloque profundo? Ahora toca tu acción de adquisición: 10 mensajes en Sales Navigator o revisar la pauta.",
        "evening": "🌙 Cierre del día: ¿qué avanzaste hoy de tus tareas? Reporta lo que cobraste y lo que hiciste. Luego, familia sin celular.",
        "money": "💰 Viernes, cita con el dinero (30 min): cobranzas, facturar, actualizar proyección de caja y provisionar impuestos. ¿Cuánto entró esta semana?",
        "weekly": "📅 Revisión semanal: 1) ¿cuánto entró/salió? 2) ¿qué pasó a cobrable? 3) ¿cumpliste el hábito? 4) ¿tus 3 prioridades de la próxima semana?",
        "enrich": "💡 ¿Quieres que investigue y guarde algo útil para tu plan (un guion de Sales Nav, una plantilla de cotización)? Responde 'sí guarda' para confirmar.",
        "hourly": "⚡ Pulso: ¿en qué estás ahora mismo? Mira tu meta más cercana y da UN paso concreto en los próximos 25 min. Si ya avanzaste, sube la vara: ¿cuál es la acción que más mueve la aguja hoy?",
    }
    return msgs.get(kind, msgs["morning"])


async def generate_and_send(user_id: str, chat_id: str, kind: str) -> None:
    """Construye el contexto del coach, genera el mensaje y lo envía por Telegram."""
    from backend.agent_hub.integrations.telegram import send_reply

    instruction = PROMPTS.get(kind, PROMPTS["morning"])
    messages = await coach.build_context(user_id, query=instruction)
    messages.append({"role": "user", "content": instruction})

    used_fallback = False
    try:
        result = await gateway.route("text", messages)
        text = result.content
    except AllModelsExhausted:
        text = _fallback(kind)
        used_fallback = True
        await coach.log_event(user_id, f"LLM agotado ({kind}) → mensaje de respaldo", "warn")
    except Exception as e:
        print(f"[coach_scheduler] generate error ({kind}): {e}")
        text = _fallback(kind)
        used_fallback = True
        await coach.log_event(user_id, f"Error generando ({kind})", "warn", str(e))

    if kind == "evening":
        today = await coach.list_goals(user_id, status="pending")
        await coach.mark_asked(user_id, [g["_id"] for g in today if g["horizon"] == "today"])

    try:
        await send_reply(user_id, chat_id, text)
        await coach.log_event(
            user_id, f"Enviado a Telegram: {kind}", "success",
            ("(respaldo) " if used_fallback else "") + text[:120])
    except Exception as e:
        print(f"[coach_scheduler] send error ({kind}): {e}")
        await coach.log_event(user_id, f"Falló el envío a Telegram ({kind})", "error", str(e))


async def _run(user_id: str, kind: str) -> None:
    """Job: resuelve el chat actual del usuario y envía el check-in."""
    cfg = await coach.get_config(user_id)
    if not cfg or not cfg.get("enabled"):
        await coach.log_event(user_id, f"Check-in {kind} omitido: coach desactivado", "warn")
        return
    if not cfg.get("telegram_chat_id"):
        await coach.log_event(
            user_id, f"Check-in {kind} omitido: sin chat de Telegram",
            "error", "Escríbele al bot una vez (con el coach activado) para capturar tu chat.")
        return
    await coach.log_event(user_id, f"Disparando check-in: {kind}", "info")
    await generate_and_send(user_id, cfg["telegram_chat_id"], kind)


def _job_id(user_id: str, kind: str) -> str:
    return f"coach:{user_id}:{kind}"


def _remove_user_jobs(user_id: str) -> None:
    for kind in coach.CHECKIN_KINDS:
        job = scheduler.get_job(_job_id(user_id, kind))
        if job:
            job.remove()


def apply_user_schedule(user_id: str, schedule: dict) -> None:
    """(Re)registra los jobs de un usuario según su schedule. Vacío => sin job."""
    _ensure_started()
    _remove_user_jobs(user_id)
    for kind, hhmm in schedule.items():
        if kind not in coach.CHECKIN_KINDS or not hhmm:
            continue
        try:
            hh, mm = (int(x) for x in hhmm.split(":"))
        except Exception:
            continue
        if kind == "hourly":
            # Pulso cada hora: ignora HH, corre en cada hora de la ventana activa.
            cron_kwargs = {"hour": HOURLY_HOURS, "minute": mm}
        else:
            cron_kwargs = {"hour": hh, "minute": mm}
            day = _KIND_DAY.get(kind)
            if day:
                cron_kwargs["day_of_week"] = day
        # Pass the coroutine directly so AsyncIOScheduler awaits it ON the event
        # loop. (A sync lambda would run in a worker thread where
        # asyncio.ensure_future raises "no running event loop" and nothing sends.)
        scheduler.add_job(
            _run, "cron", args=[user_id, kind],
            id=_job_id(user_id, kind), replace_existing=True,
            misfire_grace_time=3600, **cron_kwargs,
        )


def next_runs(user_id: str) -> dict:
    """Próxima ejecución de cada check-in (ISO) para mostrar en el dashboard."""
    out: dict[str, str | None] = {}
    for kind in coach.CHECKIN_KINDS:
        job = scheduler.get_job(_job_id(user_id, kind))
        out[kind] = job.next_run_time.isoformat() if job and job.next_run_time else None
    return out


def _ensure_started() -> None:
    global _started
    if not _started:
        scheduler.start()
        _started = True


async def _load_all() -> None:
    """Al arrancar, registra los jobs de todos los usuarios con coach activo."""
    configs = await coach.enabled_configs_with_chat()
    for cfg in configs:
        apply_user_schedule(cfg["user_id"], coach.get_schedule(cfg))
    if configs:
        print(f"[coach_scheduler] loaded schedules for {len(configs)} user(s)")


def start_scheduler() -> None:
    _ensure_started()
    asyncio.ensure_future(_load_all())
    print("[coach_scheduler] started — proactive coach (America/Lima)")


def stop_scheduler() -> None:
    global _started
    if _started and scheduler.running:
        scheduler.shutdown(wait=False)
        _started = False


async def trigger_now(user_id: str, kind: str = "morning") -> bool:
    """Dispara un check-in manual (para probar). Devuelve False si no hay chat."""
    cfg = await coach.get_config(user_id)
    if not cfg or not cfg.get("telegram_chat_id"):
        await coach.log_event(
            user_id, f"Prueba {kind}: sin chat de Telegram", "error",
            "Escríbele al bot una vez (con el coach activado) para capturar tu chat.")
        return False
    await coach.log_event(user_id, f"Prueba manual: {kind}", "info")
    await generate_and_send(user_id, cfg["telegram_chat_id"], kind)
    return True
