from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    evaluated = "evaluated"
    applied = "applied"
    responded = "responded"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    discarded = "discarded"


class EvalGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class CareerProfile(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    portfolio_url: str = ""
    github: str = ""
    primary_roles: List[str] = Field(default_factory=list)
    headline: str = ""
    exit_story: str = ""
    superpowers: List[str] = Field(default_factory=list)
    proof_points: List[Dict[str, str]] = Field(default_factory=list)
    target_range: str = ""          # legacy text field, kept for compatibility
    target_min: int = 0             # monthly minimum, in selected currency
    target_max: int = 0             # monthly maximum, in selected currency
    salary_period: str = "monthly"  # "monthly" | "annual"
    currency: str = "USD"
    minimum_salary: str = ""
    location_flexibility: str = ""
    country: str = ""
    city: str = ""
    timezone: str = ""
    visa_status: str = ""
    deal_breakers: List[str] = Field(default_factory=list)
    must_haves: List[str] = Field(default_factory=list)
    preferred_countries: List[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class EvaluateJobRequest(BaseModel):
    job_text: str
    job_url: str = ""
    job_title: str = ""
    company_name: str = ""


class UpdateApplicationRequest(BaseModel):
    status: ApplicationStatus
    notes: str = ""
