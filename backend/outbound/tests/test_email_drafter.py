from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.outbound.email_drafter import (
    build_system_prompt,
    build_user_prompt,
    _parse_response,
    draft_email,
)


# ── build_system_prompt ───────────────────────────────────────────────────────

def test_build_system_prompt_includes_brand_voice():
    icp = {"brand_voice": "Tono muy directo y sin rodeos."}
    result = build_system_prompt(icp)
    assert "Tono muy directo y sin rodeos." in result


def test_build_system_prompt_includes_case_studies():
    icp = {"case_studies": ["Ayudamos a clínica ABC a triplicar citas.", "Modernizamos el ERP de Logística XYZ."]}
    result = build_system_prompt(icp)
    assert "clínica ABC" in result
    assert "Logística XYZ" in result


def test_build_system_prompt_uses_defaults_when_empty():
    result = build_system_prompt({})
    assert "Tono directo" in result
    assert "Marcos" in result
    assert "calendly" in result


def test_build_system_prompt_custom_owner_and_calendly():
    icp = {"owner_name": "Rodrigo", "calendly_url": "https://cal.com/rodrigo"}
    result = build_system_prompt(icp)
    assert "Rodrigo" in result
    assert "https://cal.com/rodrigo" in result


def test_build_system_prompt_skips_empty_case_studies():
    icp = {"case_studies": ["", "  ", "Caso real aquí."]}
    result = build_system_prompt(icp)
    assert "Caso real aquí." in result
    # Empty strings should not appear as list items
    assert "- \n" not in result


# ── build_user_prompt ─────────────────────────────────────────────────────────

def test_build_user_prompt_includes_company_and_contact():
    prospect = {
        "company_name": "Dental Lima",
        "company_domain": "dentallima.pe",
        "contact_full_name": "Carlos Ríos",
        "contact_title": "CEO",
        "icp_score": 75,
        "signals_detected": ["geo:lima", "industry:dental"],
    }
    result = build_user_prompt(prospect)
    assert "Dental Lima" in result
    assert "Carlos Ríos" in result
    assert "CEO" in result
    assert "geo:lima" in result
    assert "75/100" in result


def test_build_user_prompt_handles_missing_fields():
    result = build_user_prompt({})
    assert "la empresa" in result
    assert "el decisor" in result
    assert "ninguna detectada" in result


# ── _parse_response ───────────────────────────────────────────────────────────

def test_parse_response_standard_format():
    text = "ASUNTO: Cómo modernizar tu clínica en Lima\n\nHola Carlos,\n\nVi que usas WordPress..."
    subject, body = _parse_response(text)
    assert subject == "Cómo modernizar tu clínica en Lima"
    assert "Hola Carlos" in body
    assert "WordPress" in body


def test_parse_response_case_insensitive_prefix():
    text = "asunto: Seis palabras para el asunto aquí\n\nCuerpo del email."
    subject, body = _parse_response(text)
    assert "Seis palabras" in subject
    assert "Cuerpo" in body


def test_parse_response_fallback_on_missing_asunto():
    text = "Primera línea como asunto\nResto del texto aquí."
    subject, body = _parse_response(text)
    assert subject == "Primera línea como asunto"
    assert "Resto" in body


def test_parse_response_strips_whitespace():
    text = "  ASUNTO:   Asunto con espacios   \n\n  Cuerpo limpio.  "
    subject, body = _parse_response(text)
    assert subject == "Asunto con espacios"
    assert body == "Cuerpo limpio."


# ── draft_email ───────────────────────────────────────────────────────────────

def _make_col(find_one_return=None, insert_id="abc123"):
    col = MagicMock()
    col.find_one = AsyncMock(return_value=find_one_return)
    insert_result = MagicMock()
    insert_result.inserted_id = insert_id
    col.insert_one = AsyncMock(return_value=insert_result)
    col.update_one = AsyncMock()
    return col


@pytest.mark.asyncio
async def test_draft_email_returns_existing_if_pending():
    existing_draft = {"_id": "existing_id", "prospect_id": "p1", "status": "pending_approval"}
    prospect = {"_id": "p1", "company_name": "Test Co"}

    def col_side(name):
        col = MagicMock()
        col.find_one = AsyncMock(return_value=existing_draft)
        return col

    with patch("backend.outbound.email_drafter.get_collection", side_effect=col_side):
        result = await draft_email(prospect, {})

    assert result["status"] == "pending_approval"
    assert result["_id"] == "existing_id"


@pytest.mark.asyncio
async def test_draft_email_creates_new_draft():
    # Must be a valid 24-char hex ObjectId string
    prospect = {
        "_id": "507f1f77bcf86cd799439011",
        "company_name": "Dental Lima",
        "company_domain": "dentallima.pe",
        "contact_email": "ceo@dentallima.pe",
        "contact_full_name": "Carlos Ríos",
        "icp_score": 80,
        "tier": "A",
        "signals_detected": ["geo:lima", "industry:dental"],
    }

    drafts_col = _make_col(find_one_return=None)
    prospects_col = _make_col()

    def col_side(name):
        if name == "outbound_email_drafts":
            return drafts_col
        return prospects_col

    llm_response = "ASUNTO: Hola decisor esta es tu asunto\n\nEstimado Carlos, bla bla bla."

    with (
        patch("backend.outbound.email_drafter.get_collection", side_effect=col_side),
        patch("backend.outbound.email_drafter.llm_router.chat", new=AsyncMock(return_value=(llm_response, "groq", "llama-3.3-70b"))),
    ):
        result = await draft_email(prospect, {})

    assert result["company_name"] == "Dental Lima"
    assert "Hola decisor" in result["subject"]
    assert result["status"] == "pending_approval"
    assert result["llm_provider"] == "groq"
    # Verify prospect was updated
    prospects_col.update_one.assert_called_once()
