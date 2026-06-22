import pytest
from backend.outbound.icp_scorer import score_company


# ── Caso 1: Fit perfecto ──────────────────────────────────────────────────────

def test_perfect_fit():
    company = {
        "name": "Clínica Dental Miraflores",
        "description": (
            "Clínica dental en lima con página en wordpress. "
            "Queremos modernizar nuestra presencia digital y automatizar citas. "
            "Contacto solo por whatsapp."
        ),
        "location": "Lima, Perú",
        "website": "http://clinicadental.pe",
    }
    score, signals, tier = score_company(company)

    assert score >= 60, f"Expected tier A (>=60), got {score}"
    assert tier == "A"
    assert any("geo:" in s for s in signals)
    assert any("industry:" in s for s in signals)
    assert "has_website" in signals
    assert any("gap:" in s for s in signals)


# ── Caso 2: Industria fuera del ICP ──────────────────────────────────────────

def test_industry_out_of_icp():
    company = {
        "name": "Banco Nacional del Norte",
        "description": "Entidad financiera con 500 sucursales en todo el país.",
        "location": "Lima, Perú",
        "website": "http://banconacional.pe",
    }
    score, signals, tier = score_company(company)

    assert not any("industry:" in s for s in signals), "Should not match any ICP industry"
    # Geo + website = 15 + 10 = 25 → tier B or C, not A
    assert score < 60


# ── Caso 3: Geo fuera del ICP ─────────────────────────────────────────────────

def test_geo_out_of_icp():
    company = {
        "name": "Dental Studio NYC",
        "description": "Dental clinic in New York specializing in cosmetic dentistry.",
        "location": "New York, USA",
        "website": "http://dentalstudionyc.com",
    }
    score, signals, tier = score_company(company)

    assert not any("geo:" in s for s in signals), "Should not match LATAM geo"
    # industry (25) + has_website (10) = 35 → tier B
    assert score < 60


# ── Caso 4: Sin señales de brecha digital ────────────────────────────────────

def test_no_digital_gap_signals():
    company = {
        "name": "Restaurante La Tradición Lima",
        "description": "Restaurante gourmet en lima con plataforma de reservas online avanzada.",
        "location": "Lima",
        "website": "http://latradicion.pe",
    }
    score, signals, tier = score_company(company)

    assert not any("gap:" in s for s in signals), "Should not detect digital gap signals"
    # geo (15) + industry (25) + website (10) + rich_desc (10) = 60 → tier A at boundary
    # No gap signals: score won't exceed 60 much without them
    assert score <= 70


# ── Caso 5: Score tan bajo que es rejected ───────────────────────────────────

def test_rejected_company():
    # No geo LATAM, no target industry, no website, no digital gap, no positive signals
    company = {
        "name": "Generic Holdings International",
        "description": "A large conglomerate with diverse interests.",
        "location": "New York",
        "website": "",
    }
    score, signals, tier = score_company(company)

    assert tier == "rejected", f"Expected rejected, got tier={tier} score={score}"
    assert score < 20


# ── Caso 6: Custom weights desde ICPConfig ───────────────────────────────────

def test_custom_weights_override():
    company = {
        "name": "Spa Relax Colombia",
        "description": "Spa de masajes en bogota.",
        "location": "Bogotá",
        "website": "http://sparelax.co",
    }
    custom_weights = {"geo": 50, "industry": 50, "has_website": 0, "digital_gap": 0, "description": 0}
    score, signals, tier = score_company(company, weights=custom_weights)

    assert score == 100  # geo(50) + industry(50)
    assert tier == "A"


# ── Caso 7: Empresa sin website tiene penalización implícita ─────────────────

def test_no_website_misses_10_pts():
    company_with = {
        "name": "Clínica Salud Lima",
        "description": "Clinica medica en lima tradicional.",
        "location": "Lima",
        "website": "http://clinicasalud.pe",
    }
    company_without = {**company_with, "website": ""}

    score_with, _, _ = score_company(company_with)
    score_without, signals_without, _ = score_company(company_without)

    assert score_with == score_without + 10
    assert "has_website" not in signals_without


# ── Caso 8: Score se clampea a 100 ───────────────────────────────────────────

def test_score_clamped_at_100():
    company = {
        "name": "Clínica Dental Lima wordpress whatsapp",
        "description": (
            "clinica dental en lima con wordpress sin presencia digital. "
            "tradicional familiar artesanal. Queremos modernizar y automatizar. " * 3
        ),
        "location": "Lima Peru Miraflores",
        "website": "http://dental.pe",
    }
    score, _, _ = score_company(company)
    assert score <= 100
