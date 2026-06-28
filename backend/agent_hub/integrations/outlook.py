"""Microsoft Graph OAuth2 + Calendar CRUD."""
import os
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
import httpx
import msal

from backend.database import get_collection

COL = "agent_outlook_connections"
_SCOPES = ["Calendars.ReadWrite", "User.Read"]


def _fernet() -> Fernet:
    key = os.getenv("MS_TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError("MS_TOKEN_ENCRYPTION_KEY not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


def _msal_app() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=os.getenv("MS_CLIENT_ID", ""),
        client_credential=os.getenv("MS_CLIENT_SECRET", ""),
        authority="https://login.microsoftonline.com/common",
    )


def get_auth_url(state: str = "") -> str:
    app = _msal_app()
    redirect_uri = os.getenv("MS_REDIRECT_URI", "")
    return app.get_authorization_request_url(
        scopes=_SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )


async def exchange_code_for_tokens(user_id: str, code: str) -> None:
    app = _msal_app()
    redirect_uri = os.getenv("MS_REDIRECT_URI", "")
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=_SCOPES,
        redirect_uri=redirect_uri,
    )
    if "error" in result:
        raise ValueError(result.get("error_description", result["error"]))

    f = _fernet()
    access_enc = f.encrypt(result["access_token"].encode()).decode()
    refresh_enc = f.encrypt(result["refresh_token"].encode()).decode()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=result.get("expires_in", 3600))
    account = result.get("id_token_claims", {})
    email = account.get("preferred_username", account.get("email", ""))
    name = account.get("name", "")

    col = get_collection(COL)
    await col.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "ms_account_email": email,
            "ms_account_name": name,
            "access_token_enc": access_enc,
            "refresh_token_enc": refresh_enc,
            "token_expires_at": expires_at,
            "scopes": _SCOPES,
            "connected_at": datetime.now(timezone.utc),
            "last_refreshed_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


async def _get_valid_access_token(user_id: str) -> str:
    col = get_collection(COL)
    doc = await col.find_one({"user_id": user_id})
    if not doc:
        raise ValueError("Outlook not connected")

    f = _fernet()
    expires_at = doc["token_expires_at"]
    if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) >= expires_at - timedelta(minutes=5):
        # Refresh
        refresh_token = f.decrypt(doc["refresh_token_enc"].encode()).decode()
        app = _msal_app()
        result = app.acquire_token_by_refresh_token(refresh_token, scopes=_SCOPES)
        if "error" in result:
            raise ValueError("Token refresh failed: " + result.get("error_description", ""))
        new_access_enc = f.encrypt(result["access_token"].encode()).decode()
        new_expires = datetime.now(timezone.utc) + timedelta(seconds=result.get("expires_in", 3600))
        if "refresh_token" in result:
            new_refresh_enc = f.encrypt(result["refresh_token"].encode()).decode()
            await col.update_one({"user_id": user_id}, {"$set": {
                "access_token_enc": new_access_enc,
                "refresh_token_enc": new_refresh_enc,
                "token_expires_at": new_expires,
                "last_refreshed_at": datetime.now(timezone.utc),
            }})
        else:
            await col.update_one({"user_id": user_id}, {"$set": {
                "access_token_enc": new_access_enc,
                "token_expires_at": new_expires,
                "last_refreshed_at": datetime.now(timezone.utc),
            }})
        return result["access_token"]

    return f.decrypt(doc["access_token_enc"].encode()).decode()


async def get_calendar_events(user_id: str, start: datetime, end: datetime) -> list[dict]:
    token = await _get_valid_access_token(user_id)
    params = {
        "$select": "id,subject,start,end,location,bodyPreview",
        "startDateTime": start.isoformat(),
        "endDateTime": end.isoformat(),
        "$orderby": "start/dateTime",
        "$top": "20",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me/calendarView",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        resp.raise_for_status()
    return resp.json().get("value", [])


def _dt_str(value) -> str:
    """Acepta datetime o cadena ISO y devuelve 'YYYY-MM-DDTHH:MM:SS' (sin tz)."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).isoformat(timespec="seconds")
    s = str(value).strip()
    # normaliza 'Z' y recorta cualquier offset, dejando hora local de la zona dada
    if s.endswith("Z"):
        s = s[:-1]
    return s


async def create_event(
    user_id: str,
    subject: str,
    start,
    end,
    body: str = "",
    time_zone: str = "America/Lima",
    location: str = "",
    attendees: list[str] | None = None,
) -> dict:
    token = await _get_valid_access_token(user_id)
    payload: dict = {
        "subject": subject,
        "start": {"dateTime": _dt_str(start), "timeZone": time_zone},
        "end": {"dateTime": _dt_str(end), "timeZone": time_zone},
        "body": {"contentType": "text", "content": body},
    }
    if location:
        payload["location"] = {"displayName": location}
    if attendees:
        payload["attendees"] = [
            {"emailAddress": {"address": a}, "type": "required"} for a in attendees
        ]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://graph.microsoft.com/v1.0/me/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
    return resp.json()


async def delete_event(user_id: str, event_id: str) -> None:
    token = await _get_valid_access_token(user_id)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()


async def get_todays_events_summary(user_id: str) -> str:
    """Return a plain-text summary of today's events for context injection."""
    try:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        events = await get_calendar_events(user_id, start, end)
        if not events:
            return "No calendar events today."
        lines = [f"Today's events ({now.strftime('%Y-%m-%d')}):"]
        for e in events:
            t = e.get("start", {}).get("dateTime", "")[:16].replace("T", " ")
            lines.append(f"- {t}: {e.get('subject', 'Untitled')}")
        return "\n".join(lines)
    except Exception:
        return ""


async def get_connection_status(user_id: str) -> dict:
    col = get_collection(COL)
    doc = await col.find_one({"user_id": user_id})
    if not doc:
        return {"connected": False}
    return {
        "connected": True,
        "account_email": doc.get("ms_account_email", ""),
        "account_name": doc.get("ms_account_name", ""),
        "connected_at": doc.get("connected_at", "").isoformat() if hasattr(doc.get("connected_at"), "isoformat") else "",
        "token_expires_at": doc.get("token_expires_at", "").isoformat() if hasattr(doc.get("token_expires_at"), "isoformat") else "",
    }
