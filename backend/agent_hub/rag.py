"""RAG — file ingestion (S3 + text extraction + MongoDB chunks) and context retrieval."""
import io
import uuid
from datetime import datetime, timezone

import boto3
from bson import ObjectId

from backend.database import get_collection, settings

FILES_COL = "agent_files"
CHUNKS_COL = "agent_file_chunks"
CHUNK_WORDS = 500
CHUNK_OVERLAP = 75


# ── S3 ─────────────────────────────────────────────────────────────────────────

def _s3():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.s3_region,
    )


# ── Text extraction ─────────────────────────────────────────────────────────────

def _extract_text(data: bytes, content_type: str, filename: str) -> str:
    ct = content_type.lower()
    name = filename.lower()

    if ct == "application/pdf" or name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""

    if (ct in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or name.endswith((".docx", ".doc"))):
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception:
            return ""

    if ct.startswith("text/") or name.endswith(
        (".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".jsx", ".tsx", ".yaml", ".yml", ".xml")
    ):
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return ""

    return ""


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += CHUNK_WORDS - CHUNK_OVERLAP
    return chunks


# ── Public API ──────────────────────────────────────────────────────────────────

async def ingest_file(user_id: str, data: bytes, filename: str, content_type: str) -> dict:
    """Upload to S3, extract text, store chunks. Returns file metadata dict."""
    file_id = uuid.uuid4().hex
    s3_key = f"agent-hub/files/{user_id}/{file_id}/{filename}"

    s3 = _s3()
    s3.put_object(Bucket=settings.s3_bucket, Key=s3_key, Body=data, ContentType=content_type)
    s3_url = f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{s3_key}"

    text = _extract_text(data, content_type, filename)
    chunks = _chunk_text(text) if text.strip() else []

    now = datetime.now(timezone.utc)
    file_doc = {
        "user_id": user_id,
        "filename": filename,
        "s3_key": s3_key,
        "s3_url": s3_url,
        "content_type": content_type,
        "size": len(data),
        "chunk_count": len(chunks),
        "has_text": bool(chunks),
        "created_at": now,
    }
    result = await get_collection(FILES_COL).insert_one(file_doc)
    doc_id = str(result.inserted_id)

    if chunks:
        await get_collection(CHUNKS_COL).insert_many([
            {
                "file_id": doc_id,
                "user_id": user_id,
                "filename": filename,
                "chunk_index": i,
                "content": chunk,
                "created_at": now,
            }
            for i, chunk in enumerate(chunks)
        ])
        # idempotent — creates index only once
        try:
            await get_collection(CHUNKS_COL).create_index(
                [("content", "text"), ("filename", "text")]
            )
        except Exception:
            pass

    file_doc["_id"] = doc_id
    file_doc["created_at"] = now.isoformat()
    return file_doc


async def search_context(user_id: str, query: str, max_chunks: int = 4) -> str:
    """Full-text search over user's file chunks; returns formatted context string."""
    if not query.strip():
        return ""
    col = get_collection(CHUNKS_COL)
    try:
        cursor = col.find(
            {"$text": {"$search": query}, "user_id": user_id},
            {"score": {"$meta": "textScore"}, "content": 1, "filename": 1},
        ).sort([("score", {"$meta": "textScore"})]).limit(max_chunks)
        docs = await cursor.to_list(max_chunks)
    except Exception:
        return ""
    if not docs:
        return ""
    parts = [f"[{d['filename']}]\n{d['content']}" for d in docs]
    return "Relevant context from the user's uploaded files:\n\n" + "\n\n---\n\n".join(parts)


async def list_files(user_id: str) -> list[dict]:
    docs = await (
        get_collection(FILES_COL)
        .find({"user_id": user_id}, {"s3_key": 0})
        .sort("created_at", -1)
        .limit(100)
        .to_list(100)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
        if hasattr(d.get("created_at"), "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
    return docs


async def delete_file(user_id: str, file_id: str) -> bool:
    col = get_collection(FILES_COL)
    doc = await col.find_one({"_id": ObjectId(file_id), "user_id": user_id})
    if not doc:
        return False
    try:
        _s3().delete_object(Bucket=settings.s3_bucket, Key=doc["s3_key"])
    except Exception:
        pass
    await get_collection(CHUNKS_COL).delete_many({"file_id": file_id})
    await col.delete_one({"_id": ObjectId(file_id)})
    return True
