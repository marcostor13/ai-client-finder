# Instrucciones operativas — ANTES de pegarle el prompt a Claude Code

Esto NO lo puede hacer Claude Code por ti. Son decisiones humanas y setup de cuentas. Hazlas primero, toma te ~2 horas.

---

## 1. Cuentas y API keys a crear (30 min)

### Anthropic API
- Entra a https://console.anthropic.com, crea API key.
- Compra $20 de créditos iniciales para empezar.
- Guarda la key como `ANTHROPIC_API_KEY` en tu `.env`.

### Apollo.io
- Crea cuenta gratis en https://apollo.io.
- Ve a Settings → Integrations → API → genera una API key.
- Guárdala como `APOLLO_API_KEY`.
- Tu plan Free te da 10.000 email credits al año. Suficiente para ~200 empresas/mes con 1 contacto cada una durante los primeros meses.

### Instantly.ai (el más importante)
- Crea cuenta en https://instantly.ai.
- Contrata plan **Growth** ($30/mes con anual, o $37/mes mensual). Esto NO es opcional si quieres que el sistema funcione más de 3 semanas.
- **Compra o configura un dominio secundario** para envío. NO uses tu dominio principal nunca. Ejemplo: si tu agencia es `miagencia.com`, compra `miagencia-team.com` o `go-miagencia.com` ($12/año en Cloudflare).
- En Instantly, conecta 2–3 buzones de ese dominio secundario (Google Workspace $7/buzón/mes, o usa Puzzle Inbox $3/buzón).
- **Activa warm-up en los 3 buzones** y déjalos 3–4 semanas calentándose ANTES de enviar cold email real. Durante ese tiempo puedes construir e ir probando el sistema contra una campaña de prueba con tus propios emails.
- Crea una campaña en Instantly llamada "Outbound Agencia" y copia el `campaign_id` de la URL. Guárdalo como `INSTANTLY_CAMPAIGN_ID`.
- Genera API key en Settings → Integrations. Guárdala como `INSTANTLY_API_KEY`.

Costo fijo mensual: $30 Instantly + $21 Google Workspace (3 buzones) + $1 dominio = **~$52/mes**. Más ~$5–20/mes de créditos Anthropic según volumen.

---

## 2. Config DNS del dominio secundario (20 min)

En tu registrar (Cloudflare, GoDaddy, etc.) configura estos registros para el dominio secundario. Instantly te da los valores exactos en el panel de onboarding, pero por si acaso:

- **MX record**: apunta a Google Workspace.
- **SPF record** (TXT): `v=spf1 include:_spf.google.com ~all`
- **DKIM record** (TXT): Google te da el valor en Admin → Apps → Gmail → Authenticate email.
- **DMARC record** (TXT): `v=DMARC1; p=none; rua=mailto:tu-email-personal@miagencia.com`
- **Domain forwarding**: redirige `miagencia-team.com` a tu dominio principal `miagencia.com` con HTTP 301. Esto es clave: si alguien googlea el dominio desde el email, debe aterrizar en tu web real.

Verifica que todo está bien con https://mxtoolbox.com/SuperTool.aspx antes de conectar los buzones a Instantly.

---

## 3. Preparar tu ICP y case studies (30 min)

Esto es lo que va a alimentar al sistema. Sin esto, los emails salen genéricos.

Crea un archivo `icp_inicial.json` con este contenido y ajústalo:

```json
{
  "version": 1,
  "apollo_filters": {
    "employee_ranges": ["50,200", "20,50"],
    "industries": ["Retail", "Logistics", "Real Estate", "Healthcare", "Manufacturing"],
    "countries": ["Peru", "Mexico", "Colombia", "Chile", "Spain"],
    "technologies_exclude": ["Shopify", "Salesforce"]
  },
  "scoring_weights": {
    "size": 20, "industry": 20, "geo": 10, "signals": 30, "revenue": 20
  },
  "ideal_revenue_min_usd": 2000000,
  "ideal_revenue_max_usd": 50000000,
  "brand_voice": "Directa, técnica pero sin jerga, empática con el problema del decisor, nunca vendedora agresiva. Hablamos como socios técnicos, no como proveedores. En español neutro para LATAM o castellano para España según el país del contacto.",
  "case_studies": [
    {
      "client_type": "Retail mid-market familiar",
      "problem": "Excel + ERP legacy saturado, 3 personas full-time manteniéndolo",
      "solution": "Plataforma web custom con sync al ERP existente",
      "result": "Reducción 70% tiempo de carga de órdenes, ROI en 8 meses"
    },
    {
      "client_type": "Logística regional",
      "problem": "Cotizaciones manuales por WhatsApp, pérdida de leads",
      "solution": "SaaS interno de cotización con API pública para clientes",
      "result": "40% más cotizaciones cerradas en los primeros 3 meses"
    }
  ],
  "decision_maker_titles": [
    "CEO", "CTO", "COO", "Head of Technology", "Head of Digital",
    "Director de Tecnología", "Gerente General", "Director de Operaciones"
  ],
  "owner_notification_email": "tu-email@miagencia.com",
  "owner_name": "Tu Nombre",
  "owner_calendly": "https://calendly.com/tu-usuario/30min"
}
```

Lo vas a cargar vía la UI de `ICPConfigForm.jsx` cuando Claude Code termine la Fase 1. Pero tenerlo escrito ya te fuerza a clarificar tu ICP, que es el 80% del éxito del sistema.

---

## 4. Compliance y opt-out (15 min de lectura obligatoria)

- Si contactas a personas en **UE (España, Portugal)**, GDPR exige base legítima (legítimo interés B2B funciona, pero debes poder justificarlo). Opt-out inmediato en cada email. Retener logs de consentimiento/supresión.
- **Perú (Ley 29733)**: similar. Opt-out obligatorio.
- **México (LFPDPPP)**: aviso de privacidad debe ser accesible. Incluye link a tu política en el footer del email.
- **USA**: CAN-SPAM. Opt-out debe funcionar dentro de 10 días. Debes incluir dirección postal real en el footer.

**Pide a Claude Code que el footer de cada email incluya automáticamente:**
```
[Nombre agencia] — [Ciudad, País] — [Dirección si aplica]
Si no quieres recibir más emails, haz clic aquí: {unsubscribe_link}
```

---

## 5. Timeline realista

| Semana | Qué pasa |
|--------|----------|
| 1 | Compras dominio, configuras DNS, conectas buzones en Instantly, empieza warm-up. Claude Code ejecuta Fase 1 (Apollo + scoring + ICP config). Tú validas. |
| 2 | Claude Code ejecuta Fase 2 (drafts + cola). Warm-up sigue. Tú validas drafts contra tu juicio sin enviar todavía. |
| 3 | Claude Code ejecuta Fase 3 (envío + métricas). Warm-up a 50%. Primeros envíos de prueba a 3–5 emails tuyos (familia, emails personales) para verificar deliverability. |
| 4 | Warm-up casi completo. Primera tanda real de 5–10 emails/día. Tú revisas cada uno antes de aprobar. |
| 5–8 | Escala gradual a 20–30 emails/día. Ajustas ICP según quién responde. |
| 9+ | Sistema en régimen. Revisas métricas una vez por semana. |

**No intentes enviar 50 emails/día en la semana 2.** El dominio te durará 3 semanas antes de ir a spam y tendrás que empezar de cero con otro dominio.

---

## 6. Qué hacer cuando algo falla

| Síntoma | Causa probable | Qué hacer |
|---------|----------------|-----------|
| Reply rate < 2% en la semana 4 | ICP mal definido o emails genéricos | Revisa los drafts rechazados, ajusta `brand_voice` y case studies en `ICPConfig` |
| Bounce rate > 3% | Apollo te dio emails malos | Activa verificación en Instantly antes de enviar (cuesta créditos extra) |
| Deliverability baja (emails van a spam) | Warm-up insuficiente o dominio quemado | Pausa campaña 2 semanas, sube warm-up. Si no mejora, cambia de dominio |
| Apollo se queda sin credits a mitad de mes | Cuota Free agotada | Sube a Basic $49/mes o reduce `MAX_COMPANIES_PER_DAY` |
| Claude API costos > $30/mes | Prompt sin caching | Verifica que `cache_control` esté activado en system prompt, debería bajar 85% |

---

## 7. Cómo pegar el prompt a Claude Code

1. Abre terminal en la raíz de tu proyecto (el que tiene el backend Python y el frontend React).
2. Corre `claude` para iniciar Claude Code.
3. Crea un `.env` con las 3 API keys + `INSTANTLY_CAMPAIGN_ID`. No lo commitees (añade a `.gitignore`).
4. Abre el archivo `prompt-claude-code-outbound.md` que te entregué, copia TODO su contenido.
5. Pégalo en Claude Code como primer mensaje.
6. Claude te va a responder proponiendo qué va a reutilizar del módulo de empresas existente. Revisa y di "adelante con Fase 1" cuando estés conforme.
7. Al terminar Fase 1, Claude debe PARAR. Si no para, dile "para y muéstrame tests" explícitamente.
8. Revisa tests, corre el job manualmente una vez, verifica que pobla la tabla `Prospect` con datos reales de Apollo. Si algo falla, corrige con Claude Code antes de seguir.
9. Di "adelante con Fase 2". Repite validación. Idem Fase 3 y 4.

**Nunca le digas "hazlo todo de una vez" a Claude Code**. Las fases existen por una razón: cada una tiene decisiones que necesitan tu juicio humano, especialmente la Fase 2 (calidad de emails) y la Fase 3 (primer envío real).
