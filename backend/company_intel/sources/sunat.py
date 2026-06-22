"""
SUNAT RUC resolution (Perú).

Primary: apis.net.pe v2 (needs APIS_NET_PE_TOKEN). Falls back gracefully to a
name-based discovery (handled by the pipeline via search) when no RUC/token.
"""
import re
from typing import Optional

import httpx

from backend.database import settings
from backend.company_intel.models import CompanyProfile
from backend.company_intel.sources.http import headers

RUC_RE = re.compile(r"^(?:10|15|17|20)\d{9}$")


def is_ruc(query: str) -> bool:
    return bool(RUC_RE.match(re.sub(r"\D", "", query or "")))


def clean_ruc(query: str) -> str:
    return re.sub(r"\D", "", query or "")


async def resolve_ruc(ruc: str) -> Optional[CompanyProfile]:
    """Resolve a RUC to a CompanyProfile via apis.net.pe. None if unavailable."""
    ruc = clean_ruc(ruc)
    if not is_ruc(ruc):
        return None
    token = settings.apis_net_pe_token
    if not token:
        # No token: return a minimal profile so the pipeline can still proceed.
        return CompanyProfile(query=ruc, ruc=ruc,
                              sources=["sunat:sin-token (define APIS_NET_PE_TOKEN para razón social)"])
    url = f"https://api.apis.net.pe/v2/sunat/ruc?numero={ruc}"
    h = {**headers(), "Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=h)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return CompanyProfile(query=ruc, ruc=ruc, sources=[f"sunat:error ({e})"])

    return CompanyProfile(
        query=ruc,
        ruc=ruc,
        legal_name=data.get("razonSocial") or data.get("nombre"),
        trade_name=data.get("nombreComercial"),
        status=data.get("estado"),
        condition=data.get("condicion"),
        address=_join_address(data),
        sources=["sunat:apis.net.pe"],
    )


def _join_address(data: dict) -> Optional[str]:
    parts = [data.get("direccion"), data.get("distrito"), data.get("provincia"),
             data.get("departamento")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None
