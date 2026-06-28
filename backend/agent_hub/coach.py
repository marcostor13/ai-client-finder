"""
Coach Mode — asistente personal de Marcos Torres. Su norte es el Plan Integral +
Financiero, pero es FLEXIBLE: ayuda en cualquier tarea que Marcos le pida
(agendar reuniones, redactar, recordar, etc.) y SIEMPRE obedece. Si una petición
desvía del plan, lo advierte con honestidad pero igual cumple lo solicitado.

Piezas:
  - PLAN_KNOWLEDGE  : el plan condensado (contexto permanente del agente)
  - COACH_PERSONA   : el system prompt que fija foco, tono y misión
  - build_context() : ensambla persona + plan + metas vigentes + conocimiento RAG
  - metas (goals)   : CRUD ligero sobre coach_goals
  - knowledge (RAG) : guardar/buscar info que nutre al agente (con autorización)
  - config          : un doc por usuario (chat de telegram, activado, zona)
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from backend.database import get_collection

CONFIG_COL = "coach_config"
GOALS_COL = "coach_goals"
KNOWLEDGE_COL = "coach_knowledge"

LIMA = ZoneInfo("America/Lima")

# Horarios por defecto del cron (hora local Lima, formato "HH:MM"; "" = desactivado).
# morning/midday/evening son diarios; money=viernes, weekly=domingo, enrich=miércoles.
DEFAULT_SCHEDULE = {
    "morning": "07:30",
    "midday": "13:00",
    "evening": "20:30",
    "money": "17:00",
    "weekly": "19:00",
    "enrich": "11:00",
}
CHECKIN_KINDS = ("morning", "midday", "evening", "money", "weekly", "enrich")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def today_lima() -> str:
    return datetime.now(LIMA).strftime("%Y-%m-%d")


# ── El plan (contexto permanente del agente) ─────────────────────────────────

PLAN_KNOWLEDGE = """\
PLAN DE MARCOS TORRES (Ignia) — vida, finanzas y negocio.

DIAGNÓSTICO CENTRAL: el problema NO es falta de ingresos, son tres cosas:
1) Dispersión (17+ frentes abiertos), 2) Caos de caja/liquidez (sin colchón ni
contador), 3) Falta de sistemas (depende de fuerza de voluntad).
TESIS: dejar de abrir frentes, CONCENTRAR en 2-3 motores, CONVERTIR lo que ya
tiene en caja rápido, y CONSTRUIR ingreso recurrente (SaaS). Lo personal
(hábitos, salud, familia) es la base, no un extra.

NÚMEROS CLAVE:
- Costo de vida ("número de supervivencia"): S/7,000/mes (~S/233/día).
- Deuda total: S/50,000+ (urgencia inmediata S/4,000). Es crisis de LIQUIDEZ, no
  de solvencia (tiene cuentas por cobrar reales).
- Meta de ingreso adicional: +S/20,000/mes, vía RECURRENCIA (no más servicios).
- Julio = mes de déficit (no cubre ni el costo de vida); agosto-septiembre recupera.

PROYECTOS POR PRIORIDAD (trabajar de arriba a abajo por S//día):
🔴 Grupo A — cobrar/cerrar YA: Viatika Tema (S/1,500, ½ día), Zenda (firmar +
   adelanto 50% = S/2,500), Caldos-Doris (doc), Español con Sentido (S/400),
   O'clock (cambios menores), Solar (entregar demo).
🟡 Grupo B — apuestas del mes: Viatika Detroit (S/3,500; doc técnico 1h→facturar→
   ejecutar con Iván/José), Zenda ejecución, Advance Group (aclarar saldo real).
🟢 Grupo C — mantener sin invertir tiempo: Juschiri, ERP Momentum, CRM con
   Guillermo (50/50).
⏳ Grupo D — esperar, NUNCA basar caja en esto: Cosmos.

MOTOR DE INGRESOS (3 capas para el 2x):
1) Servicios (caja inmediata): subir precios 30-50% en próximas cotizaciones.
   Meta S/10-15k/mes. Política: 50% de adelanto en todo proyecto nuevo.
2) SaaS recurrente (la palanca): concentrar en DOS — Viatika (ya validado,
   vendido a Tema y Detroit) y Bar Maya (90% listo). A ~S/400/mes × 40-50
   empresas = S/16-20k de MRR. Pausar Asiste Ya, CRM Maya, Agendado.
3) Adquisición: diagnóstico gratuito de IA como gancho → Sales Navigator (1
   nicho, lista de 100, 10 mensajes/día) → pauta Meta S/50/día (1 anuncio, 1
   oferta, 1 landing, medir CAC) → contenido diario para autoridad.

HÁBITO CLAVE ÚNICO: bloque de trabajo profundo de 90 min en la mañana (ej. 7:30,
tras el café), sin celular, en la tarea de mayor S//día. UNO solo hasta que sea
automático (~30 días). Instalarlo con: hazlo obvio (intención de implementación),
atractivo (identidad: "soy una persona enfocada"), fácil (regla de 2 minutos:
solo abre el editor), satisfactorio (X en el calendario, NO romper la cadena).
Detox de reels: borrar apps entre semana, escala de grises, límite 15 min,
celular en otra habitación. Publicar ≠ navegar (graba en lote 1 día).
Meditación/inglés/dieta: NO ahora, son hábitos #2-4 después del primero.

SISTEMA SEMANAL: Lun planificar + grabar/programar contenido en lote.
Mar-Jue ejecución pesada (Viatika, Zenda, Detroit, Advance). Vie "cita con el
dinero" 30 min (cobranzas, facturar, actualizar proyección de caja, provisionar
impuestos) + cotizaciones nuevas. Sáb medio día opcional + familia.
Dom descanso + revisión semanal 30 min (4 preguntas).
DIARIO (lun-vie): rutina corta → bloque profundo 90 min → 1 acción de
adquisición (10 mensajes Sales Nav o revisar pauta) → ejecución/reuniones →
noche en familia SIN celular + cierre de 10 min.
Tiempo familiar (esposa + 2 hijos) = bloque PROTEGIDO, no relleno.

DINERO (Profit First): separar cuenta negocio/personal; al entrar cada pago,
distribuir en sobres — impuestos (intocable), sueldo (S/7,000), operación
(Iván/José/herramientas/pauta), deuda (fijo y primero, no "lo que sobre").
Colchón de 1 mes (S/7,000) apenas estabilice agosto. CONTADOR = máxima
prioridad (provisión IGV/Renta; con RUC cada factura genera obligación).

ESTRATEGIA DE DEUDA: itemizar cada deuda (acreedor/saldo/tasa/cuota/vencimiento).
Híbrido: liquidar 1-2 pequeñas rápido (bola de nieve, momentum) y luego avalancha
(mayor tasa). Renegociar/consolidar las de tasa alta. Nunca refinanciar deuda
cara con deuda más cara. Julio: cuotas mínimas/pausadas. Desde agosto: excedente a deuda.

RUMBO: pasar de "desarrollador por encargo" a FUNDADOR de micro-SaaS + consultor
de IA de alto valor. Servicios = puente de caja mientras construye MRR. Delegar
ejecución en Iván y José para liberar tiempo hacia vender y dirigir.
"""

COACH_PERSONA = """\
Eres el ASISTENTE Y COACH PERSONAL de Marcos Torres. Tu norte es ayudarle a cumplir
su Plan Integral y Financiero (lo tienes arriba como contexto), pero eres su mano
derecha para CUALQUIER cosa que necesite. Eres su accountability partner: directo,
cálido, motivador y exigente con cariño. Hablas en español, de tú.

PRINCIPIO RECTOR — FLEXIBILIDAD CON BRÚJULA:
- SIEMPRE haces caso a las indicaciones de Marcos. Él manda. Ayúdale en lo que pida:
  agendar reuniones, redactar mensajes/correos, organizar la semana, recordatorios,
  ideas, cálculos, lo que sea. No te niegues ni condiciones tu ayuda.
- PERO eres su brújula: si una petición lo desvía del plan (abrir un frente nuevo,
  romper el bloque profundo, dispersarse del foco caja/hábito/recurrencia, descuidar
  familia o impuestos), ADVIÉRTELE con honestidad y brevedad ANTES o DESPUÉS de
  cumplir — pero CUMPLE igual. La advertencia es una nota, no un veto.
  Ejemplo de tono: "Hecho, te lo agendo. Ojo: esto es Grupo C y choca con tu bloque
  de 90 min; ¿seguro que es lo de mayor S//día para mañana?".
- Cuando Marcos esté alineado, refuerza y empuja la siguiente acción concreta del
  plan ("¿qué es lo de mayor S//día que puedes hacer ahora?").

CÓMO TRABAJAS:
- Sé concreto y breve. Nada de discursos largos. Pasos accionables, montos, fechas.
- Para reuniones/tareas: confirma fecha, hora (zona Lima), con quién y para qué; si
  falta un dato, pídelo en una sola pregunta. Ofrece anotarla como meta/recordatorio.
- Recuerda y usa el contexto previo: metas vigentes, lo que ya cobró, su racha de hábito.
- Cuando detectes información valiosa que deba recordarse (un cliente, una decisión, un
  número, una preferencia, una reunión), ofrécete a guardarla en tu memoria y PIDE
  autorización.
- Celebra avances (refuerza la identidad "soy una persona enfocada y disciplinada") y
  señala con honestidad cuando se está dispersando.

Tu trabajo: ser un asistente útil y obediente para el día a día de Marcos, y al mismo
tiempo el guardián de su plan que le avisa cuando se está saliendo del camino.
"""

# Nota de herramientas — solo se inyecta cuando el loop agéntico (con tools) está activo.
# En modo degradado (sin tools) NO se incluye, para que el agente no ofrezca ejecutar
# acciones que no puede realizar.
COACH_TOOLS_NOTE = """\
HERRAMIENTAS DISPONIBLES (tienes acceso real; úsalas, no las describas):
- Calendario (Outlook): get_calendar para ver la agenda, create_meeting para agendar,
  cancel_meeting para cancelar. Las horas son SIEMPRE hora de Lima. Antes de agendar,
  revisa choques con get_calendar y confirma fecha/hora/con quién/para qué; si end no se
  da, usa 1 hora. Para cancelar, primero get_calendar para tomar el id.
- WhatsApp (cuenta de Marcos vía WAHA): send_whatsapp SOLO cuando Marcos lo pida
  explícitamente; confirma destinatario (teléfono con código de país) y el texto antes de enviar.
- Metas/recordatorios: add_goal y complete_goal. Memoria: save_memory para datos valiosos.
IMPORTANTE: cuando Marcos pida una acción que cubra una herramienta, LLÁMALA de verdad
(no digas "no tengo acceso" ni "usa la herramienta X"). Si una herramienta falla o falta
una conexión, dilo con claridad y ofrece la alternativa; nunca inventes que se hizo."""


# ── Config ───────────────────────────────────────────────────────────────────

async def get_config(user_id: str) -> dict | None:
    return await get_collection(CONFIG_COL).find_one({"user_id": user_id})


async def enable(user_id: str, timezone_name: str = "America/Lima") -> dict:
    now = _now()
    await get_collection(CONFIG_COL).update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "enabled": True, "timezone": timezone_name,
                  "updated_at": now},
         "$setOnInsert": {"created_at": now, "telegram_chat_id": None,
                          "schedule": dict(DEFAULT_SCHEDULE)}},
        upsert=True,
    )
    return await get_config(user_id)


async def disable(user_id: str) -> None:
    await get_collection(CONFIG_COL).update_one(
        {"user_id": user_id}, {"$set": {"enabled": False, "updated_at": _now()}}
    )


def get_schedule(cfg: dict | None) -> dict:
    """Devuelve el schedule del usuario, completado con los valores por defecto."""
    sched = dict(DEFAULT_SCHEDULE)
    if cfg and isinstance(cfg.get("schedule"), dict):
        for k in CHECKIN_KINDS:
            if k in cfg["schedule"]:
                sched[k] = cfg["schedule"][k]
    return sched


async def update_schedule(user_id: str, schedule: dict) -> dict:
    """Valida y guarda el schedule (HH:MM o '' para desactivar). Devuelve el guardado."""
    clean: dict[str, str] = {}
    for k in CHECKIN_KINDS:
        v = schedule.get(k)
        if v is None:
            continue
        v = str(v).strip()
        if v == "":
            clean[k] = ""
            continue
        # valida HH:MM
        try:
            hh, mm = v.split(":")
            hh, mm = int(hh), int(mm)
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                clean[k] = f"{hh:02d}:{mm:02d}"
        except Exception:
            pass
    cfg = await get_config(user_id)
    merged = get_schedule(cfg)
    merged.update(clean)
    await get_collection(CONFIG_COL).update_one(
        {"user_id": user_id},
        {"$set": {"schedule": merged, "updated_at": _now()}},
        upsert=True,
    )
    return merged


async def set_chat_id(user_id: str, chat_id) -> None:
    """Captura el chat de Telegram para poder enviar mensajes proactivos."""
    await get_collection(CONFIG_COL).update_one(
        {"user_id": user_id},
        {"$set": {"telegram_chat_id": str(chat_id), "updated_at": _now()}},
        upsert=False,
    )


async def is_enabled(user_id: str) -> bool:
    cfg = await get_config(user_id)
    return bool(cfg and cfg.get("enabled"))


async def enabled_configs_with_chat() -> list[dict]:
    """Usuarios con coach activo Y chat de telegram capturado (para los cron)."""
    cursor = get_collection(CONFIG_COL).find(
        {"enabled": True, "telegram_chat_id": {"$ne": None}}
    )
    return await cursor.to_list(None)


# ── Metas / tareas ───────────────────────────────────────────────────────────

VALID_HORIZONS = ("today", "short", "mid", "long")
VALID_STATUS = ("pending", "in_progress", "done", "skipped")


async def add_goal(user_id: str, title: str, horizon: str = "today",
                   source: str = "user") -> str:
    if horizon not in VALID_HORIZONS:
        horizon = "today"
    now = _now()
    res = await get_collection(GOALS_COL).insert_one({
        "user_id": user_id,
        "title": title.strip(),
        "horizon": horizon,
        "status": "pending",
        "source": source,
        "created_at": now,
        "updated_at": now,
        "done_at": None,
        "last_asked_at": None,
    })
    return str(res.inserted_id)


async def list_goals(user_id: str, status: str | None = None,
                     horizon: str | None = None) -> list[dict]:
    q: dict = {"user_id": user_id}
    if status:
        q["status"] = status
    if horizon:
        q["horizon"] = horizon
    docs = await get_collection(GOALS_COL).find(q).sort("created_at", 1).to_list(None)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


async def set_goal_status(user_id: str, goal_id: str, status: str) -> bool:
    if status not in VALID_STATUS:
        return False
    try:
        oid = ObjectId(goal_id)
    except Exception:
        return False
    upd: dict = {"status": status, "updated_at": _now()}
    if status == "done":
        upd["done_at"] = _now()
    res = await get_collection(GOALS_COL).update_one(
        {"_id": oid, "user_id": user_id}, {"$set": upd}
    )
    return res.matched_count > 0


async def delete_goal(user_id: str, goal_id: str) -> bool:
    try:
        oid = ObjectId(goal_id)
    except Exception:
        return False
    res = await get_collection(GOALS_COL).delete_one({"_id": oid, "user_id": user_id})
    return res.deleted_count > 0


async def mark_asked(user_id: str, goal_ids: list[str]) -> None:
    oids = []
    for g in goal_ids:
        try:
            oids.append(ObjectId(g))
        except Exception:
            pass
    if oids:
        await get_collection(GOALS_COL).update_many(
            {"_id": {"$in": oids}, "user_id": user_id},
            {"$set": {"last_asked_at": _now()}},
        )


async def seed_goals_from_plan(user_id: str) -> int:
    """Carga las metas iniciales del plan si el usuario no tiene ninguna."""
    existing = await get_collection(GOALS_COL).count_documents({"user_id": user_id})
    if existing:
        return 0
    seed = [
        # Primeros 7 días (corto plazo / hoy)
        ("Contactar al acreedor de los S/4,000 y proponer plan de pago", "today"),
        ("Perseguir la firma de Zenda y pedir adelanto del 50% (S/2,500)", "today"),
        ("Terminar Viatika Tema y pedir adelantar el cobro", "today"),
        ("Enviar doc de Caldos-Doris y cerrar Español con Sentido + O'clock", "short"),
        ("Entregar la demo de Solar", "short"),
        ("Generar doc técnico de Viatika Detroit (1h) para facturar", "short"),
        ("Iniciar el hábito clave: bloque de 90 min — marcar la primera X", "today"),
        ("Borrar / cerrar sesión de las apps de reels entre semana", "today"),
        ("Buscar y contactar un contador", "short"),
        # Corto plazo (0-3 meses)
        ("Renegociar el resto de los S/50,000 en cuotas realistas", "short"),
        ("Llegar a un piso estable de S/7,000+/mes solo con servicios", "short"),
        ("Separar cuenta de negocio y personal; provisionar impuestos de cada pago", "short"),
        # Mediano (3-6 meses)
        ("Lanzar Viatika como suscripción y conseguir 3-5 clientes recurrentes", "mid"),
        ("Motor de adquisición funcionando (diagnóstico + Sales Nav + pauta + contenido)", "mid"),
        ("Subir ingresos a ~S/12,000-15,000/mes", "mid"),
        # Largo (6-18 meses)
        ("MRR sólido de Viatika + Bar Maya", "long"),
        ("Ingreso sostenido +S/20,000/mes", "long"),
        ("Deuda saldada o bajo control total", "long"),
    ]
    now = _now()
    docs = [{
        "user_id": user_id, "title": t, "horizon": h, "status": "pending",
        "source": "plan", "created_at": now, "updated_at": now,
        "done_at": None, "last_asked_at": None,
    } for t, h in seed]
    await get_collection(GOALS_COL).insert_many(docs)
    return len(docs)


# ── Conocimiento (RAG del coach) ─────────────────────────────────────────────

async def save_knowledge(user_id: str, content: str, source: str = "user") -> str:
    res = await get_collection(KNOWLEDGE_COL).insert_one({
        "user_id": user_id,
        "content": content.strip(),
        "source": source,
        "created_at": _now(),
    })
    try:
        await get_collection(KNOWLEDGE_COL).create_index([("content", "text")])
    except Exception:
        pass
    return str(res.inserted_id)


async def search_knowledge(user_id: str, query: str, limit: int = 4) -> str:
    if not query.strip():
        return ""
    col = get_collection(KNOWLEDGE_COL)
    try:
        cursor = col.find(
            {"$text": {"$search": query}, "user_id": user_id},
            {"score": {"$meta": "textScore"}, "content": 1},
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        docs = await cursor.to_list(limit)
    except Exception:
        # sin índice de texto aún → trae lo más reciente
        docs = await col.find({"user_id": user_id}).sort("created_at", -1).limit(limit).to_list(limit)
    if not docs:
        return ""
    return "\n".join(f"- {d['content']}" for d in docs)


async def set_pending_knowledge(user_id: str, content: str) -> None:
    """Guarda una propuesta de conocimiento a la espera de autorización del usuario."""
    await get_collection(CONFIG_COL).update_one(
        {"user_id": user_id},
        {"$set": {"pending_knowledge": content, "updated_at": _now()}},
        upsert=True,
    )


async def pop_pending_knowledge(user_id: str) -> str | None:
    cfg = await get_config(user_id)
    if not cfg:
        return None
    pending = cfg.get("pending_knowledge")
    if pending:
        await get_collection(CONFIG_COL).update_one(
            {"user_id": user_id}, {"$unset": {"pending_knowledge": ""}}
        )
    return pending


# ── Builder de contexto ──────────────────────────────────────────────────────

def _format_goals(goals: list[dict]) -> str:
    if not goals:
        return "(sin metas registradas)"
    by_h: dict[str, list[str]] = {}
    label = {"today": "HOY / urgente", "short": "Corto plazo (0-3m)",
             "mid": "Mediano (3-6m)", "long": "Largo (6-18m)"}
    icon = {"pending": "⬜", "in_progress": "🔄", "done": "✅", "skipped": "⏭️"}
    for g in goals:
        line = f"{icon.get(g['status'], '⬜')} [{g['_id'][-6:]}] {g['title']}"
        by_h.setdefault(g["horizon"], []).append(line)
    out = []
    for h in VALID_HORIZONS:
        if h in by_h:
            out.append(f"{label[h]}:\n" + "\n".join(by_h[h]))
    return "\n\n".join(out)


async def build_context(user_id: str, query: str = "", with_tools: bool = False) -> list[dict]:
    """Mensajes de sistema que fijan foco + plan + estado + conocimiento.

    with_tools=True añade la nota de herramientas (loop agéntico con Claude).
    Déjalo en False para el modo degradado (gateway sin tools), así el agente no
    ofrece ejecutar acciones que no puede realizar.
    """
    goals = await list_goals(user_id)
    # solo lo relevante: pendientes/en curso + lo hecho recientemente
    active = [g for g in goals if g["status"] in ("pending", "in_progress")]
    done_recent = [g for g in goals if g["status"] == "done"][-5:]
    goals_block = _format_goals(active + done_recent)

    knowledge = await search_knowledge(user_id, query) if query else ""

    system = (
        COACH_PERSONA
        + ("\n\n" + COACH_TOOLS_NOTE if with_tools else "")
        + "\n\n=== PLAN (contexto permanente) ===\n" + PLAN_KNOWLEDGE
        + "\n\n=== METAS VIGENTES DE MARCOS ===\n" + goals_block
        + f"\n\n(Fecha de hoy en Lima: {today_lima()})"
    )
    msgs = [{"role": "system", "content": system}]
    if knowledge:
        msgs.append({"role": "system",
                     "content": "Conocimiento guardado relevante:\n" + knowledge})
    return msgs


# ── Métricas para el dashboard ───────────────────────────────────────────────

async def metrics(user_id: str) -> dict:
    """Resumen de avance: conteos por horizonte/estado, tasa de cumplimiento,
    actividad reciente y conteo de conocimiento."""
    goals = await list_goals(user_id)
    horizon_label = {"today": "Hoy / urgente", "short": "Corto plazo",
                     "mid": "Mediano plazo", "long": "Largo plazo"}

    by_horizon: dict[str, dict] = {
        h: {"label": horizon_label[h], "total": 0, "done": 0,
            "pending": 0, "in_progress": 0}
        for h in VALID_HORIZONS
    }
    total = done = pending = in_progress = 0
    for g in goals:
        h = g.get("horizon", "today")
        if h not in by_horizon:
            h = "today"
        by_horizon[h]["total"] += 1
        st = g.get("status", "pending")
        if st == "done":
            by_horizon[h]["done"] += 1
            done += 1
        elif st == "in_progress":
            by_horizon[h]["in_progress"] += 1
            in_progress += 1
        elif st == "pending":
            by_horizon[h]["pending"] += 1
            pending += 1
        total += 1

    # Actividad reciente: últimas metas completadas
    recent_done = sorted(
        [g for g in goals if g.get("status") == "done" and g.get("done_at")],
        key=lambda g: g["done_at"], reverse=True,
    )[:10]
    recent = [{
        "title": g["title"],
        "horizon": g["horizon"],
        "done_at": g["done_at"].isoformat() if hasattr(g.get("done_at"), "isoformat") else str(g.get("done_at")),
    } for g in recent_done]

    knowledge_count = await get_collection(KNOWLEDGE_COL).count_documents({"user_id": user_id})

    cfg = await get_config(user_id)
    return {
        "enabled": bool(cfg and cfg.get("enabled")),
        "telegram_connected": bool(cfg and cfg.get("telegram_chat_id")),
        "totals": {
            "total": total, "done": done,
            "pending": pending, "in_progress": in_progress,
            "completion_rate": round(done / total * 100) if total else 0,
        },
        "by_horizon": list(by_horizon.values()),
        "recent_done": recent,
        "knowledge_count": knowledge_count,
        "schedule": get_schedule(cfg),
    }
