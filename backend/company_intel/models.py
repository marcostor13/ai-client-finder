"""Pydantic models for the company_intel module."""
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Seniority ranking ──────────────────────────────────────────────────────────
# Lower rank number = higher in the org. Used to order people top→bottom.
class SeniorityRank(int, Enum):
    OWNER = 0          # Dueño / Fundador / Presidente del directorio
    C_LEVEL = 1        # Gerente General / CEO / CFO / CTO / Director
    VP = 2             # Subgerente / VP / Director de área
    MANAGER = 3        # Gerente de área / Jefe
    LEAD = 4           # Coordinador / Supervisor / Líder
    SENIOR = 5         # Senior / Especialista
    STAFF = 6          # Analista / Asistente / Ejecutivo
    UNKNOWN = 9


class SocialProfile(BaseModel):
    network: str                      # linkedin | facebook | instagram | x | tiktok | youtube
    url: str
    handle: Optional[str] = None
    public: bool = True               # solo registramos perfiles públicos
    source: str = ""                  # de dónde salió (search snippet, website, apollo...)


class Person(BaseModel):
    name: str
    title: Optional[str] = None       # cargo textual
    rank: SeniorityRank = SeniorityRank.UNKNOWN
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    socials: List[SocialProfile] = Field(default_factory=list)
    location: Optional[str] = None
    sources: List[str] = Field(default_factory=list)   # trazabilidad de cada dato
    confidence: float = 0.5           # 0..1 — qué tan confiable es el match


class ProductService(BaseModel):
    name: str
    kind: str = "unknown"             # product | service | unknown
    description: Optional[str] = None
    source: str = ""


class CompanyProfile(BaseModel):
    query: str                        # lo que ingresó el usuario (RUC o nombre)
    ruc: Optional[str] = None
    legal_name: Optional[str] = None  # razón social
    trade_name: Optional[str] = None  # nombre comercial
    status: Optional[str] = None      # estado SUNAT (ACTIVO, etc.)
    condition: Optional[str] = None   # condición (HABIDO, etc.)
    address: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    emails: List[str] = Field(default_factory=list)    # correos generales de la empresa
    phones: List[str] = Field(default_factory=list)
    socials: List[SocialProfile] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


class IntelReport(BaseModel):
    company_overview: str = ""        # informe de información de la empresa
    products_services: str = ""       # informe de productos/servicios
    weaknesses: str = ""              # informe de falencias (tipo SWOT)
    generated_by: Optional[str] = None   # provider/model LLM usado


class JobStatus(str, Enum):
    PENDING = "pending"
    RESOLVING = "resolving"      # resolviendo empresa (SUNAT)
    CRAWLING = "crawling"        # crawleando web
    DISCOVERING = "discovering"  # descubriendo personas
    ENRICHING = "enriching"      # enriqueciendo contactos
    ANALYZING = "analyzing"      # generando informes
    DONE = "done"
    FAILED = "failed"


class IntelJob(BaseModel):
    id: Optional[str] = None
    query: str
    country: str = "PE"
    status: JobStatus = JobStatus.PENDING
    progress: int = 0                 # 0..100
    message: str = ""
    company: Optional[CompanyProfile] = None
    people: List[Person] = Field(default_factory=list)
    products: List[ProductService] = Field(default_factory=list)
    report: Optional[IntelReport] = None
    error: Optional[str] = None
    owner_email: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ── Seniority classification ────────────────────────────────────────────────────
# Keyword → rank. Order matters: checked from most senior to least.
_SENIORITY_LEXICON: List[tuple] = [
    (SeniorityRank.OWNER, ["dueño", "fundador", "founder", "owner", "presidente del directorio",
                            "presidente ejecutivo", "chairman", "socio principal"]),
    (SeniorityRank.C_LEVEL, ["gerente general", "ceo", "chief executive", "director general",
                             "cfo", "cto", "coo", "cmo", "chief ", "gerente corporativo"]),
    (SeniorityRank.VP, ["subgerente", "vicepresidente", "vice president", "vp ", "director de",
                        "directora de", "director ", "directora "]),
    (SeniorityRank.MANAGER, ["gerente", "jefe", "jefa", "manager", "head of"]),
    (SeniorityRank.LEAD, ["coordinador", "coordinadora", "supervisor", "supervisora", "líder",
                          "lider", "lead", "encargado", "encargada"]),
    (SeniorityRank.SENIOR, ["senior", "especialista", "specialist", "consultor", "consultora"]),
    (SeniorityRank.STAFF, ["analista", "asistente", "ejecutivo", "ejecutiva", "asesor", "asesora",
                           "representante", "auxiliar", "practicante", "junior", "vendedor"]),
]


def classify_seniority(title: Optional[str]) -> SeniorityRank:
    """Map a free-text job title to a SeniorityRank (top→bottom ordering)."""
    if not title:
        return SeniorityRank.UNKNOWN
    t = title.lower()
    for rank, keywords in _SENIORITY_LEXICON:
        if any(k in t for k in keywords):
            return rank
    return SeniorityRank.UNKNOWN
