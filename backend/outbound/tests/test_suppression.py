from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.outbound.suppression import is_suppressed


def _make_collection(find_one_return=None):
    col = MagicMock()
    col.find_one = AsyncMock(return_value=find_one_return)
    return col


# ── Caso 1: Email inválido rechazado sin tocar BD ────────────────────────────

@pytest.mark.asyncio
async def test_invalid_email_rejected():
    suppressed, reason = await is_suppressed("not-an-email")
    assert suppressed is True
    assert reason == "invalid_email"


@pytest.mark.asyncio
async def test_empty_email_rejected():
    suppressed, reason = await is_suppressed("")
    assert suppressed is True
    assert reason == "invalid_email"


# ── Caso 2: Dominio bloqueado ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_blocked_domain_google():
    suppressed, reason = await is_suppressed("ceo@google.com")
    assert suppressed is True
    assert "blocked_domain" in reason


@pytest.mark.asyncio
async def test_blocked_domain_gov():
    suppressed, reason = await is_suppressed("info@ministerio.gov.pe")
    assert suppressed is True
    assert "blocked_domain" in reason


# ── Caso 3: Email en lista de supresión ──────────────────────────────────────

@pytest.mark.asyncio
async def test_email_in_suppression_list():
    suppression_entry = {"email": "opted@out.com", "reason": "opt_out"}

    with patch("backend.outbound.suppression.get_collection") as mock_gc:
        mock_gc.return_value = _make_collection(find_one_return=suppression_entry)
        suppressed, reason = await is_suppressed("opted@out.com")

    assert suppressed is True
    assert reason == "opt_out"


# ── Caso 4: Contactado en los últimos 90 días ─────────────────────────────────

@pytest.mark.asyncio
async def test_contacted_recently():
    recent_sent = {
        "contact_email": "recent@company.com",
        "status": "sent",
        "sent_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
    }

    def side_effect(collection_name):
        col = MagicMock()
        if collection_name == "outbound_suppression":
            col.find_one = AsyncMock(return_value=None)
        else:
            col.find_one = AsyncMock(return_value=recent_sent)
        return col

    with patch("backend.outbound.suppression.get_collection", side_effect=side_effect):
        suppressed, reason = await is_suppressed("recent@company.com")

    assert suppressed is True
    assert reason == "contacted_recently"


# ── Caso 5: Email limpio — pasa todos los checks ─────────────────────────────

@pytest.mark.asyncio
async def test_clean_email_not_suppressed():
    def side_effect(collection_name):
        col = MagicMock()
        col.find_one = AsyncMock(return_value=None)
        return col

    with patch("backend.outbound.suppression.get_collection", side_effect=side_effect):
        suppressed, reason = await is_suppressed("ceo@newclient.com")

    assert suppressed is False
    assert reason == ""


# ── Caso 6: Normalización de email (espacios, mayúsculas) ────────────────────

@pytest.mark.asyncio
async def test_email_normalization():
    # Blocked domain check happens before DB, so no mock needed
    suppressed, reason = await is_suppressed("  CEO@Google.COM  ")
    assert suppressed is True
    assert "blocked_domain" in reason
