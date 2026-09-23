"""FastAPI app wiring the router agent + RAG agent into a small HR support chat API."""
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.rag_agent import RagAgent
from app.agents.router_agent import RouterAgent
from app.config import settings
from app.ingestion import ingest_pdf
from app.schemas import ChatRequest, ChatResponse, IngestResponse, SourceChunk

app = FastAPI(title="HR Support GenAI Demo")

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

router_agent = RouterAgent()
rag_agent = RagAgent()

# In-memory pending-escalation state per session (fine for a single-process learning project).
_pending_escalations: dict[str, dict[str, str]] = {}
_AFFIRMATIVE = {"y", "yes", "yeah", "yep", "sure", "please", "confirm", "ok", "okay"}


def _is_affirmative(text: str) -> bool:
    return text.strip().lower() in _AFFIRMATIVE


@app.get("/")
def index():
    return FileResponse(_static_dir / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": settings.provider}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    pending = _pending_escalations.pop(request.session_id, None)
    if pending:
        if _is_affirmative(request.message):
            result = rag_agent.escalate(pending["message"], pending["reason"])
            return ChatResponse(
                answer=f"Okay, I've notified the {result.department} team by email.",
                intent="ESCALATION_CONFIRMED",
                escalated=True,
                escalated_to=result.department,
            )
        return ChatResponse(
            answer="No problem, I won't send an email. Let me know if there's anything else I can help with.",
            intent="ESCALATION_DECLINED",
        )

    route = router_agent.route(request.message)

    if not route.allowed:
        return ChatResponse(
            answer=route.reason or "I can't help with that request.",
            intent=route.intent,
            blocked=True,
        )

    if route.intent == "GREETING":
        return ChatResponse(
            answer="Hello! I'm the HR support assistant. Ask me about leave, payroll, benefits, or company policies.",
            intent=route.intent,
        )

    result = rag_agent.answer(request.message)
    if result.needs_confirmation:
        _pending_escalations[request.session_id] = {
            "message": request.message,
            "reason": result.escalation_reason or "",
        }
    return ChatResponse(
        answer=result.answer,
        sources=[SourceChunk(**s) for s in result.sources],
        intent=route.intent,
        escalated=result.escalated,
        escalated_to=result.escalated_to,
        needs_confirmation=result.needs_confirmation,
    )


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(files: list[UploadFile]):
    pdf_dir = settings.resolve_path(settings.pdf_dir)
    files_ingested: list[str] = []
    total_chunks = 0

    for upload in files:
        if not upload.filename.lower().endswith(".pdf"):
            continue
        dest = pdf_dir / upload.filename
        with dest.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
        chunks = ingest_pdf(dest)
        if chunks:
            files_ingested.append(upload.filename)
            total_chunks += chunks

    return IngestResponse(files_ingested=files_ingested, chunks_added=total_chunks)
