"""Chat / escalation / ingestion request-response contracts."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = "default"


class SourceChunk(BaseModel):
    source: str
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk] = []
    intent: str
    blocked: bool = False
    escalated: bool = False
    escalated_to: str | None = None
    needs_confirmation: bool = False


class IngestResponse(BaseModel):
    files_ingested: list[str]
    chunks_added: int
