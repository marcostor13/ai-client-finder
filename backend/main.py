import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from pydantic import BaseModel

from backend.agents.client_analyzer import ClientAnalyzerAgent
from backend.agents.client_finder import ClientFinderAgent
from backend.agents.project_finder import ProjectFinderAgent
from backend.agents.project_analyzer import ProjectAnalyzerAgent
from backend.auth import create_access_token, verify_password
from backend.database import get_collection, settings
from backend.deps import get_current_user
from backend.models.user import Token, UserBase, UserInDB

app = FastAPI(title="AI Client Finder API")


@app.on_event("startup")
async def _startup():
    from backend.outbound.jobs import start_scheduler
    from backend.career_ops.scan_scheduler import start_scheduler as co_start
    start_scheduler()
    co_start()


@app.on_event("shutdown")
async def _shutdown():
    from backend.outbound.jobs import stop_scheduler
    from backend.career_ops.scan_scheduler import stop_scheduler as co_stop
    stop_scheduler()
    co_stop()

# Comma-separated list of allowed origins (e.g. "https://your-site.netlify.app").
# Defaults to "*" for local dev. Auth uses Bearer tokens (not cookies), so
# credentials are disabled when origins are "*" to satisfy the CORS spec.
_cors_env = os.getenv("CORS_ORIGINS", "*").strip()
_cors_origins = ["*"] if _cors_env in ("", "*") else [o.strip() for o in _cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ───────────────────────────────────────────────────────────────────

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_collection("users").find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return {"access_token": token, "token_type": "bearer"}


@app.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "is_admin": current_user.get("is_admin", False),
    }


@app.get("/")
async def root():
    return {"message": "AI Client Finder API is running"}


# ── Phase 1: search + save session ────────────────────────────────────────

class SearchRequest(BaseModel):
    prompt: str

finder = ClientFinderAgent()

@app.post("/agent/search")
async def start_search(
    request: SearchRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        results = await finder.find_clients(request.prompt)

        # Save session to DB
        session_doc = {
            "user_email": current_user["email"],
            "prompt": request.prompt,
            "results": results,
            "result_count": len(results),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        inserted = await get_collection("search_sessions").insert_one(session_doc)
        session_id = str(inserted.inserted_id)

        return {"status": "success", "session_id": session_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Phase 2: deep analyze + link to session ────────────────────────────────

class AnalyzeRequest(BaseModel):
    name: str
    website: str
    location: str = ""
    description: str = ""
    search_prompt: str = ""
    session_id: str = ""

analyzer = ClientAnalyzerAgent()

@app.post("/agent/analyze")
async def analyze_client(
    request: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
):
    candidate = {
        "name": request.name,
        "website": request.website,
        "location": request.location,
        "description": request.description,
    }
    try:
        result = await analyzer.analyze(
            candidate=candidate,
            user_prompt=request.search_prompt,
            user_email=current_user["email"],
            session_id=request.session_id,
        )
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Search sessions history ────────────────────────────────────────────────

@app.get("/agent/sessions")
async def get_sessions(
    q: Optional[str] = Query(None, description="Filter by prompt text"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("search_sessions")
    query_filter: dict = {"user_email": current_user["email"]}
    if q:
        query_filter["prompt"] = {"$regex": q, "$options": "i"}

    skip = (page - 1) * limit
    total = await col.count_documents(query_filter)
    docs = await (
        col.find(query_filter, {"_id": 1, "prompt": 1, "result_count": 1, "created_at": 1})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    for d in docs:
        d["_id"] = str(d["_id"])

    return {"status": "success", "sessions": docs, "total": total, "page": page}


@app.get("/agent/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    session = await get_collection("search_sessions").find_one(
        {"_id": oid, "user_email": current_user["email"]}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["_id"] = str(session["_id"])

    # Fetch all analyzed clients for this session
    clients_cursor = get_collection("analyzed_clients").find(
        {"session_id": session_id, "user_email": current_user["email"]}
    )
    analyzed = await clients_cursor.to_list(100)
    for c in analyzed:
        c["_id"] = str(c["_id"])

    return {"status": "success", "session": session, "analyzed_clients": analyzed}


@app.delete("/agent/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    result = await get_collection("search_sessions").delete_one(
        {"_id": oid, "user_email": current_user["email"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    # Also delete analyzed clients linked to this session
    await get_collection("analyzed_clients").delete_many(
        {"session_id": session_id, "user_email": current_user["email"]}
    )

    return {"status": "success"}


# ── Saved clients (global list) ────────────────────────────────────────────

@app.get("/agent/clients")
async def get_all_clients(
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("analyzed_clients")
    docs = await (
        col.find(
            {"user_email": current_user["email"]},
            {"_id": 1, "name": 1, "website": 1, "location": 1,
             "analyzed_at": 1, "digital_presence_score": 1, "emails": 1, "phones": 1},
        )
        .sort("analyzed_at", -1)
        .limit(100)
        .to_list(100)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "success", "results": docs}


# ── Freelance Projects — search + analyze ─────────────────────────────────────

class ProjectSearchRequest(BaseModel):
    prompt: str

class ProjectAnalyzeRequest(BaseModel):
    title: str
    platform: str
    url: str
    budget: Optional[str] = ""
    budget_type: Optional[str] = ""
    description: str = ""
    search_prompt: str = ""
    session_id: str = ""

project_finder = ProjectFinderAgent()
project_analyzer = ProjectAnalyzerAgent()

@app.post("/projects/search")
async def search_projects(
    request: ProjectSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        results = await project_finder.find_projects(request.prompt)
        session_doc = {
            "user_email": current_user["email"],
            "prompt": request.prompt,
            "results": results,
            "result_count": len(results),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        inserted = await get_collection("project_sessions").insert_one(session_doc)
        session_id = str(inserted.inserted_id)
        return {"status": "success", "session_id": session_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/projects/analyze")
async def analyze_project(
    request: ProjectAnalyzeRequest,
    current_user: dict = Depends(get_current_user),
):
    project = {
        "title": request.title,
        "platform": request.platform,
        "url": request.url,
        "budget": request.budget,
        "budget_type": request.budget_type,
        "description": request.description,
    }
    try:
        result = await project_analyzer.analyze(
            project=project,
            user_prompt=request.search_prompt,
            user_email=current_user["email"],
            session_id=request.session_id,
        )
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects/sessions")
async def get_project_sessions(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    col = get_collection("project_sessions")
    query_filter: dict = {"user_email": current_user["email"]}
    if q:
        query_filter["prompt"] = {"$regex": q, "$options": "i"}
    skip = (page - 1) * limit
    total = await col.count_documents(query_filter)
    docs = await (
        col.find(query_filter, {"_id": 1, "prompt": 1, "result_count": 1, "created_at": 1})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "success", "sessions": docs, "total": total, "page": page}


@app.get("/projects/sessions/{session_id}")
async def get_project_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    session = await get_collection("project_sessions").find_one(
        {"_id": oid, "user_email": current_user["email"]}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["_id"] = str(session["_id"])
    projects_cursor = get_collection("analyzed_projects").find(
        {"session_id": session_id, "user_email": current_user["email"]}
    )
    analyzed = await projects_cursor.to_list(100)
    for p in analyzed:
        p["_id"] = str(p["_id"])
    return {"status": "success", "session": session, "analyzed_projects": analyzed}


@app.delete("/projects/sessions/{session_id}")
async def delete_project_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    result = await get_collection("project_sessions").delete_one(
        {"_id": oid, "user_email": current_user["email"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    await get_collection("analyzed_projects").delete_many(
        {"session_id": session_id, "user_email": current_user["email"]}
    )
    return {"status": "success"}


# ── Project Applications — generate proposal + track ─────────────────────────

class GenerateProposalRequest(BaseModel):
    title: str
    platform: str
    url: str
    description: str = ""
    skills_required: List[str] = []
    budget_display: Optional[str] = ""
    budget_type: Optional[str] = ""
    session_id: str = ""

class SaveApplicationRequest(BaseModel):
    project_title: str
    platform: str
    project_url: str
    session_id: str = ""
    proposal_text: str
    status: str = "applied"

_DEFAULT_OWNER    = "Marcos Torres"
_DEFAULT_CALENDLY = "https://calendly.com/marcostor13/new-meeting"

@app.post("/projects/generate-proposal")
async def generate_project_proposal(
    request: GenerateProposalRequest,
    current_user: dict = Depends(get_current_user),
):
    from openai import OpenAI
    from backend.database import settings as db_settings
    openai_client = OpenAI(api_key=db_settings.openai_api_key)

    # Pull active ICP config
    icp_doc = await get_collection("outbound_icp_config").find_one(
        {"active": True}, sort=[("version", -1)]
    )
    icp = icp_doc.get("config_json", {}) if icp_doc else {}
    owner_name  = icp.get("owner_name")  or _DEFAULT_OWNER
    case_studies = icp.get("case_studies") or []
    brand_voice  = icp.get("brand_voice")  or "Direct, results-focused, professional."

    cs_text = "\n".join(f"- {cs}" for cs in case_studies if str(cs).strip()) or "(None configured)"
    skills_text = ", ".join(request.skills_required) if request.skills_required else "not specified"
    budget_text = request.budget_display or "not specified"

    system = (
        f"You are a world-class freelance proposal writer who has won 500+ projects "
        f"on {request.platform}. You write compelling, human, hyper-personalized proposals "
        f"that convert at a high rate. Never sound like a template.\n\n"
        f"Developer profile:\n"
        f"- Name: {owner_name}\n"
        f"- Voice/style: {brand_voice}\n"
        f"- Portfolio cases:\n{cs_text}\n\n"
        f"Rules:\n"
        f"- 160–230 words maximum (platforms penalize long proposals)\n"
        f"- Start with a hook referencing something SPECIFIC in the project description "
        f"  (a detail, a pain point, a goal they mentioned) — never start with 'I'\n"
        f"- One concrete portfolio case if relevant, with a tangible result\n"
        f"- Describe your specific technical approach for THEIR exact project\n"
        f"- Mention a realistic delivery timeline\n"
        f"- End with a low-friction CTA (a question or offer to share relevant work)\n"
        f"- Write in English unless the project description is in another language\n"
        f"- Return ONLY the proposal text, no titles, no labels"
    )

    user_msg = (
        f"Platform: {request.platform}\n"
        f"Project title: {request.title}\n"
        f"Budget: {budget_text} ({request.budget_type or 'unknown type'})\n"
        f"Required skills: {skills_text}\n"
        f"Project description:\n{request.description or '(No description available — infer from title)'}"
    )

    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.55,
            max_tokens=500,
        )
        proposal_text = resp.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    return {"status": "success", "proposal_text": proposal_text, "owner_name": owner_name}


@app.post("/projects/applications")
async def save_project_application(
    request: SaveApplicationRequest,
    current_user: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_email": current_user["email"],
        "project_title": request.project_title,
        "platform": request.platform,
        "project_url": request.project_url,
        "session_id": request.session_id,
        "proposal_text": request.proposal_text,
        "status": request.status,
        "applied_at": now if request.status == "applied" else None,
        "created_at": now,
    }
    inserted = await get_collection("project_applications").insert_one(doc)
    doc["_id"] = str(inserted.inserted_id)
    return {"status": "success", "application": doc}


@app.get("/projects/applications")
async def list_project_applications(
    current_user: dict = Depends(get_current_user),
):
    docs = await (
        get_collection("project_applications")
        .find(
            {"user_email": current_user["email"]},
            {"_id": 1, "project_url": 1, "project_title": 1, "platform": 1,
             "status": 1, "applied_at": 1, "created_at": 1},
        )
        .sort("created_at", -1)
        .limit(500)
        .to_list(500)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"status": "success", "applications": docs}


# ── Outbound module ────────────────────────────────────────────────────────────

from backend.outbound.routes import router as outbound_router  # noqa: E402
app.include_router(outbound_router)

# ── Video editor module ────────────────────────────────────────────────────────

from backend.video.routes import router as video_router  # noqa: E402
app.include_router(video_router)

# ── Career Ops module ──────────────────────────────────────────────────────────

from backend.career_ops.routes import router as career_ops_router  # noqa: E402
app.include_router(career_ops_router)

# ── Company Intel module ───────────────────────────────────────────────────────

from backend.company_intel.routes import router as company_intel_router  # noqa: E402
app.include_router(company_intel_router)

# ── AI Agent Hub ───────────────────────────────────────────────────────────────

from backend.agent_hub.routes import router as agent_hub_router  # noqa: E402
app.include_router(agent_hub_router)
