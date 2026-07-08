"""
Report synthesis using the existing LLM router (DeepSeek → Groq → OpenAI).

Produces three concise Spanish reports from the collected, factual data:
  1. company_overview  — información de la empresa
  2. products_services — productos/servicios
  3. weaknesses        — informe de falencias (tipo SWOT, orientado a oportunidades)

The LLM only summarizes data we collected; it must not invent facts.
"""
import json
from typing import List

from backend.outbound import llm_router
from backend.company_intel.models import (CompanyProfile, IntelReport, Person,
                                          ProductService)

_SYSTEM = (
    "Eres un analista de inteligencia comercial B2B. Redactas informes claros y "
    "concisos en español, SOLO a partir de los datos proporcionados. Si un dato no "
    "está, dilo explícitamente ('no encontrado'); NUNCA inventes nombres, cifras ni "
    "hechos. Responde en texto plano con viñetas cuando ayude."
)


def _facts(company: CompanyProfile, people: List[Person],
           products: List[ProductService]) -> str:
    payload = {
        "empresa": {
            "razon_social": company.legal_name,
            "nombre_comercial": company.trade_name,
            "ruc": company.ruc,
            "estado": company.status,
            "condicion": company.condition,
            "direccion": company.address,
            "web": company.website,
            "industria": company.industry,
            "emails": company.emails[:10],
            "telefonos": company.phones[:10],
            "redes": [s.network + ": " + s.url for s in company.socials],
        },
        "personas": [
            {"nombre": p.name, "cargo": p.title, "rango": int(p.rank)}
            for p in people[:30]
        ],
        "productos_servicios": [
            {"nombre": pr.name, "descripcion": pr.description} for pr in products[:30]
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def _ask(system: str, user: str) -> tuple:
    text, provider, model = await llm_router.chat(
        messages=[{"role": "user", "content": user}], system=system, temperature=0.3
    )
    return text.strip(), f"{provider}:{model}"


async def generate_report(company: CompanyProfile, people: List[Person],
                          products: List[ProductService]) -> IntelReport:
    facts = _facts(company, people, products)
    name = company.legal_name or company.trade_name or company.query

    overview_q = (
        f"DATOS:\n{facts}\n\n"
        f"Redacta un informe breve (máx 150 palabras) de la información de la empresa "
        f"'{name}': qué es, sector aparente, ubicación, estado legal/SUNAT, presencia "
        f"digital y tamaño aproximado según el equipo identificado."
    )
    products_q = (
        f"DATOS:\n{facts}\n\n"
        f"Redacta un informe breve (máx 150 palabras) de los productos y servicios de "
        f"'{name}' según lo encontrado en su web. Lista los principales. Si no hay datos "
        f"suficientes, indícalo."
    )
    weaknesses_q = (
        f"DATOS:\n{facts}\n\n"
        f"Redacta un informe de FALENCIAS de '{name}' orientado a oportunidades de mejora "
        f"y de venta (máx 180 palabras). Analiza señales observables: presencia digital "
        f"débil, web desactualizada/sin info de equipo, falta de canales de contacto, "
        f"ausencia en redes, etc. Marca claramente qué es observación directa y qué es "
        f"hipótesis a validar. No inventes datos financieros."
    )

    overview, gen = await _ask(_SYSTEM, overview_q)
    products_txt, _ = await _ask(_SYSTEM, products_q)
    weaknesses, _ = await _ask(_SYSTEM, weaknesses_q)

    return IntelReport(
        company_overview=overview,
        products_services=products_txt,
        weaknesses=weaknesses,
        generated_by=gen,
    )
