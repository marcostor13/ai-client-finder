from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProspectStatus(str, Enum):
    discovered = "discovered"
    enriched = "enriched"
    drafted = "drafted"
    pending_approval = "pending_approval"
    approved = "approved"
    sent = "sent"
    replied = "replied"
    bounced = "bounced"
    suppressed = "suppressed"
    rejected = "rejected"


class ProspectTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    rejected = "rejected"


class DraftStatus(str, Enum):
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    sent = "sent"


class SuppressionReason(str, Enum):
    opt_out = "opt_out"
    bounce = "bounce"
    complaint = "complaint"
    do_not_contact = "do_not_contact"
    manual = "manual"


# ── Pydantic schemas (used for API I/O and MongoDB documents) ─────────────────

class ProspectCreate(BaseModel):
    company_name: str
    company_domain: str
    company_size: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    contact_full_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_linkedin_url: Optional[str] = None
    icp_score: int = 0
    tier: ProspectTier = ProspectTier.C
    signals_detected: List[str] = Field(default_factory=list)
    source: str = "ddg_scraper"
    apollo_contact_id: Optional[str] = None
    status: ProspectStatus = ProspectStatus.discovered
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EmailDraftCreate(BaseModel):
    prospect_id: str
    subject: str
    body_text: str
    body_html: str
    personalization_notes: str = ""
    status: DraftStatus = DraftStatus.pending_approval
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    llm_provider: str = ""
    llm_model: str = ""
    llm_cost_usd: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SuppressionEntryCreate(BaseModel):
    email: str
    reason: SuppressionReason = SuppressionReason.manual
    source: str = "manual"
    added_at: datetime = Field(default_factory=datetime.utcnow)


class ICPConfigCreate(BaseModel):
    version: int = 1
    active: bool = True
    config_json: Dict[str, Any] = Field(default_factory=dict)
    updated_by: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OutboundMetricsCreate(BaseModel):
    date: str  # YYYY-MM-DD
    prospects_discovered: int = 0
    emails_drafted: int = 0
    emails_approved: int = 0
    emails_sent: int = 0
    replies_received: int = 0
    llm_cost_usd: float = 0.0
    apollo_credits_used: int = 0
    hunter_credits_used: int = 0
