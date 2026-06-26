import os
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(BASE_DIR), ".env"))

class Settings(BaseSettings):
    mongodb_url: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name: str = os.getenv("DATABASE_NAME", "client_finder_db")
    jwt_secret: str = os.getenv("JWT_SECRET", "secret")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    claude_api_key: str = os.getenv("CLAUDE_API_KEY", "")
    # Outbound
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    apollo_api_key: str = os.getenv("APOLLO_API_KEY", "")
    hunter_api_key: str = os.getenv("HUNTER_API_KEY", "")
    # Company intel — SUNAT RUC lookup (bearer tokens, optional; cualquiera sirve)
    apis_net_pe_token: str = os.getenv("APIS_NET_PE_TOKEN", "")
    decolecta_token: str = os.getenv("DECOLECTA_TOKEN", "")
    brevo_smtp_user: str = os.getenv("BREVO_SMTP_USER", "")
    brevo_smtp_key: str = os.getenv("BREVO_SMTP_KEY", "")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    zoho_smtp_host: str = os.getenv("ZOHO_SMTP_HOST", "smtppro.zoho.com")
    zoho_smtp_port: int = int(os.getenv("ZOHO_SMTP_PORT", "587"))
    zoho_smtp_user: str = os.getenv("ZOHO_SMTP_USER", "")
    zoho_smtp_password: str = os.getenv("ZOHO_SMTP_PASSWORD", "")
    outbound_from_email: str = os.getenv("OUTBOUND_FROM_EMAIL", "")
    outbound_from_name: str = os.getenv("OUTBOUND_FROM_NAME", "")
    max_companies_per_day: int = int(os.getenv("MAX_COMPANIES_PER_DAY", "100"))
    max_emails_per_day: int = int(os.getenv("MAX_EMAILS_PER_DAY", "50"))
    max_sends_per_hour: int = int(os.getenv("MAX_SENDS_PER_HOUR", "10"))
    # AWS / S3
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    # Video processing
    youtube_client_id: str = os.getenv("YOUTUBE_CLIENT_ID", "")
    youtube_client_secret: str = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")
    # Free stock media for B-roll (images + videos) — Pexels free API tier
    pexels_api_key: str = os.getenv("PEXELS_API_KEY", "")

settings = Settings()

client = AsyncIOMotorClient(settings.mongodb_url)
db = client[settings.database_name]

def get_collection(name: str):
    return db[name]
