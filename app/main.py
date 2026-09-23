"""FastAPI app wiring the router agent + RAG agent into a small HR support chat API."""
import re
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
# stage: "confirm" (awaiting yes/no) -> "details" (awaiting employee ID + official email)
_pending_escalations: dict[str, dict[str, str]] = {}
_AFFIRMATIVE = {"y", "yes", "yeah", "yep", "sure", "please", "confirm", "ok", "okay"}
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_EMPLOYEE_ID_RE = re.compile(r"\b[A-Za-z]{0,4}\d{3,10}\b")


def _is_affirmative(text: str) -> bool:
    return text.strip().lower() in _AFFIRMATIVE


def _parse_employee_details(text: str) -> tuple[str, str] | None:
    email_match = _EMAIL_RE.search(text)
    if not email_match:
        return None
    remainder = text[: email_match.start()] + text[email_match.end() :]
    id_match = _EMPLOYEE_ID_RE.search(remainder)
    if not id_match:
        return None
    return id_match.group(0), email_match.group(0)


@app.get("/")
def index():
    return FileResponse(_static_dir / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": settings.provider}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    pending = _pending_escalations.get(request.session_id)
    if pending and pending["stage"] == "confirm":
        _pending_escalations.pop(request.session_id, None)
        if _is_affirmative(request.message):
            pending["stage"] = "details"
            _pending_escalations[request.session_id] = pending
            return ChatResponse(
                answer=(
                    "Sure — please share your Employee ID and official email address "
                    "(e.g. \"EMP1234, jane.doe@company.com\") so the team can follow up with you."
                ),
                intent="ESCALATION_AWAITING_DETAILS",
                needs_confirmation=True,
            )
        return ChatResponse(
            answer="No problem, I won't send an email. Let me know if there's anything else I can help with.",
            intent="ESCALATION_DECLINED",
        )

    if pending and pending["stage"] == "details":
        details = _parse_employee_details(request.message)
        if not details:
            return ChatResponse(
                answer=(
                    "I couldn't quite make out an Employee ID and email address there. "
                    "Could you share both like this: \"EMP1234, jane.doe@company.com\"?"
                ),
                intent="ESCALATION_AWAITING_DETAILS",
                needs_confirmation=True,
            )
        _pending_escalations.pop(request.session_id, None)
        employee_id, employee_email = details
        result = rag_agent.escalate(pending["message"], pending["reason"], employee_id, employee_email)
        return ChatResponse(
            answer=(
                f"Thanks! I've sent a detailed email to the {result.department} team on your "
                f"behalf — they'll reach out to you at {employee_email} soon."
            ),
            intent="ESCALATION_CONFIRMED",
            escalated=True,
            escalated_to=result.department,
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
            answer=(
                "👋 Hey there! I'm your HR support assistant — happy to help with leave, "
                "payroll, benefits, onboarding, or any company policy questions."
            ),
            intent=route.intent,
        )

    result = rag_agent.answer(request.message)
    if result.needs_confirmation:
        _pending_escalations[request.session_id] = {
            "stage": "confirm",
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
