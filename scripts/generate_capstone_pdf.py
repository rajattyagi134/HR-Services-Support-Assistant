"""One-off generator for the capstone project documentation PDF.

Run with:
    python scripts/generate_capstone_pdf.py
Outputs to: docs/HR_Support_Assistant_Capstone_Project.pdf
"""
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(exist_ok=True)
PDF_PATH = DOCS_DIR / "HR_Support_Assistant_Capstone_Project.pdf"

NAVY = colors.HexColor("#1f3a5f")
TEAL = colors.HexColor("#0f7a75")
LIGHT_BLUE = colors.HexColor("#dceaf7")
LIGHT_TEAL = colors.HexColor("#d8f0ee")
AMBER = colors.HexColor("#f7e6c4")
GREY = colors.HexColor("#4a4a4a")


# --------------------------------------------------------------------------- #
# Architecture diagram (built with reportlab shapes, rendered to a PNG)
# --------------------------------------------------------------------------- #
def build_architecture_diagram() -> Drawing:
    """Two-pass render: all boxes first, then all arrows/labels on top, so labels
    are never hidden behind a box fill (z-order bug) and every coordinate stays
    within [0, width] so the Drawing centers correctly on the page."""
    width, height = 780, 900
    d = Drawing(width, height)
    box_calls = []
    arrow_calls = []

    def box(cx, cy, w, h, text, fill=LIGHT_BLUE, stroke=NAVY, font_size=9.5, text_color=colors.black):
        box_calls.append((cx - w / 2, cy - h / 2, w, h, text, fill, stroke, font_size, text_color))
        return cx, cy, w, h

    def arrow(x1, y1, x2, y2, color=GREY, label=None):
        arrow_calls.append((x1, y1, x2, y2, color, label))

    def edge(box_def, side):
        cx, cy, w, h = box_def
        return {
            "top": (cx, cy + h / 2), "bottom": (cx, cy - h / 2),
            "left": (cx - w / 2, cy), "right": (cx + w / 2, cy),
        }[side]

    d.add(String(width / 2, height - 24, "System Architecture", fontSize=15,
                  fontName="Helvetica-Bold", fillColor=NAVY, textAnchor="middle"))

    MAIN_CX, ESC_CX = 390, 570

    b_user = box(MAIN_CX, height - 100, 180, 40, "User\n(Browser Chat UI)", fill=AMBER)
    b_api = box(MAIN_CX, height - 180, 260, 42, "FastAPI Backend\nPOST /api/chat  |  /api/ingest")
    b_router = box(MAIN_CX, height - 275, 300, 56,
                    "Agent 1 - RouterAgent\nGuardrails (length, injection, topic gate)\n+ LLM intent classification",
                    fill=LIGHT_TEAL)
    b_offtopic = box(90, height - 275, 170, 46, "Blocked / Off-topic\nresponse returned to user", fill=AMBER)
    b_rag = box(MAIN_CX, height - 400, 300, 58,
                 "Agent 2 - RagAgent\nRetrieve top-k chunks -> grounded LLM answer\nPII redaction + groundedness check",
                 fill=LIGHT_TEAL)
    b_chroma = box(90, height - 400, 170, 46, "ChromaDB\n(collection: hr_docs)")
    b_llm = box(690, height - 400, 170, 50, "LLM Provider\nOllama (dev) / OpenAI (prod)")
    b_answer = box(280, height - 500, 260, 40, "Answer + sources\nreturned to user", fill=AMBER)
    b_confirm = box(ESC_CX, height - 505, 280, 58,
                     "Confirmation step\n\"Escalate by email? yes/no\" ->\ncollect Employee ID + email",
                     fill=AMBER)
    b_escalate = box(ESC_CX, height - 610, 290, 56,
                      "Agent 3 - EscalationAgent\nClassify department (IT / PAYROLL / HR)\nDraft professional email",
                      fill=LIGHT_TEAL)
    b_mailhog = box(ESC_CX, height - 700, 200, 42, "MailHog SMTP\n(localhost:1025)")
    b_inbox = box(ESC_CX, height - 780, 290, 42, "IT / Payroll / HR team inbox\n(MailHog UI: localhost:8025)", fill=AMBER)

    arrow(*edge(b_user, "bottom"), *edge(b_api, "top"))
    arrow(*edge(b_api, "bottom"), *edge(b_router, "top"))
    arrow(*edge(b_router, "left"), *edge(b_offtopic, "right"), label="off-topic / unsafe")
    arrow(*edge(b_router, "bottom"), *edge(b_rag, "top"), label="HR_QUESTION")
    arrow(*edge(b_rag, "left"), *edge(b_chroma, "right"), label="similarity search")
    arrow(*edge(b_rag, "right"), *edge(b_llm, "left"), label="chat completion")
    arrow(MAIN_CX - 60, edge(b_rag, "bottom")[1], edge(b_answer, "top")[0], edge(b_answer, "top")[1], label="grounded")
    arrow(MAIN_CX + 60, edge(b_rag, "bottom")[1], edge(b_confirm, "top")[0], edge(b_confirm, "top")[1],
          label="not found / low confidence")
    arrow(*edge(b_confirm, "bottom"), *edge(b_escalate, "top"))
    arrow(*edge(b_escalate, "bottom"), *edge(b_mailhog, "top"), label="SMTP")
    arrow(*edge(b_mailhog, "bottom"), *edge(b_inbox, "top"), label="delivers to")

    # Pass 1: box fills + labels.
    for x, y, w, h, text, fill, stroke, font_size, text_color in box_calls:
        d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=stroke, strokeWidth=1.2, rx=6, ry=6))
        lines = text.split("\n")
        n = len(lines)
        for i, line in enumerate(lines):
            ty = y + h / 2 + (n - 1) * 6.5 - i * 13
            d.add(String(x + w / 2, ty, line, fontSize=font_size, fillColor=text_color,
                          textAnchor="middle", fontName="Helvetica-Bold" if i == 0 else "Helvetica"))

    # Pass 2: arrows + labels, drawn on top so they are never hidden by a box fill.
    import math

    for x1, y1, x2, y2, color, label in arrow_calls:
        d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.3))
        ang = math.atan2(y2 - y1, x2 - x1)
        size = 6
        p1 = (x2 - size * math.cos(ang - 0.4), y2 - size * math.sin(ang - 0.4))
        p2 = (x2 - size * math.cos(ang + 0.4), y2 - size * math.sin(ang + 0.4))
        d.add(Polygon([x2, y2, p1[0], p1[1], p2[0], p2[1]], fillColor=color, strokeColor=color))
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            is_horizontal = abs(y2 - y1) < abs(x2 - x1)
            ly = my + 8 if is_horizontal else my
            lx = mx if is_horizontal else mx + 6
            anchor = "middle" if is_horizontal else "start"
            d.add(String(lx, ly, label, fontSize=7.5, fillColor=GREY, textAnchor=anchor))

    return d


# --------------------------------------------------------------------------- #
# Document content
# --------------------------------------------------------------------------- #
styles = getSampleStyleSheet()
styles.add(ParagraphStyle("H1Custom", parent=styles["Heading1"], textColor=NAVY, spaceBefore=18, spaceAfter=10))
styles.add(ParagraphStyle("H2Custom", parent=styles["Heading2"], textColor=TEAL, spaceBefore=12, spaceAfter=6))
styles.add(ParagraphStyle("BodyCustom", parent=styles["BodyText"], alignment=TA_LEFT, leading=15, spaceAfter=8))
styles.add(ParagraphStyle("BulletCustom", parent=styles["BodyText"], leading=14, spaceAfter=4))
styles.add(ParagraphStyle("CodeBlock", parent=styles["Code"], backColor=colors.HexColor("#f3f3f3"),
                           borderPadding=6, leading=12, fontSize=8.5))
styles.add(ParagraphStyle("CoverTitle", parent=styles["Title"], fontSize=26, textColor=NAVY,
                           alignment=TA_CENTER, leading=32))
styles.add(ParagraphStyle("CoverSub", parent=styles["Heading2"], fontSize=15, textColor=TEAL,
                           alignment=TA_CENTER, spaceBefore=16))
styles.add(ParagraphStyle("CoverMeta", parent=styles["Normal"], fontSize=12, textColor=colors.black,
                           alignment=TA_CENTER, spaceBefore=6))
styles.add(ParagraphStyle("TableHeader", parent=styles["BodyText"], fontName="Helvetica-Bold",
                           fontSize=9, leading=11, textColor=colors.white))
styles.add(ParagraphStyle("TableCell", parent=styles["BodyText"], fontSize=9, leading=11.5))


def p(text, style="BodyCustom"):
    return Paragraph(text, styles[style])


def bullets(items):
    return ListFlowable(
        [ListItem(p(i, "BulletCustom"), leftIndent=6) for i in items],
        bulletType="bullet", start="•", leftIndent=14,
    )


def code_block(text):
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(escaped.replace("\n", "<br/>"), styles["CodeBlock"])


def simple_table(data, col_widths=None):
    wrapped = []
    for row_idx, row in enumerate(data):
        wrapped_row = []
        for cell in row:
            if isinstance(cell, str):
                style = "TableHeader" if row_idx == 0 else "TableCell"
                wrapped_row.append(Paragraph(cell, styles[style]))
            else:
                wrapped_row.append(cell)
        wrapped.append(wrapped_row)

    t = Table(wrapped, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f8fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def build_pdf():
    doc = SimpleDocTemplate(
        str(PDF_PATH), pagesize=A4,
        topMargin=2.2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
        title="Multi-Agent RAG based HR Support Assistant",
        author="Rajat Tyagi",
    )

    story = []

    # ---------------- Cover page ----------------
    story.append(Spacer(1, 4 * cm))
    story.append(p("Multi Agent RAG based HR Support Assistant", "CoverTitle"))
    story.append(Spacer(1, 0.6 * cm))
    story.append(p("Final Capstone Project", "CoverSub"))
    story.append(Spacer(1, 1.2 * cm))
    story.append(p("by <b>Rajat Tyagi</b>", "CoverMeta"))
    story.append(p("Employee ID: 2261727", "CoverMeta"))
    story.append(Spacer(1, 2 * cm))
    story.append(p(
        "A 3-agent Retrieval-Augmented Generation (RAG) chatbot that answers HR policy questions "
        "from company PDF documents, guarded by input/output safety checks, and automatically "
        "escalates unresolved queries to the right team (IT, Payroll, or HR) via email.",
        "CoverMeta"))
    story.append(PageBreak())

    # ---------------- Table of contents (manual) ----------------
    story.append(p("Table of Contents", "H1Custom"))
    toc_items = [
        "1. Project Overview",
        "2. Objectives",
        "3. System Architecture",
        "4. Multi-Agent Design",
        "5. Guardrails & Safety",
        "6. Escalation & Email Workflow",
        "7. Technology Stack",
        "8. Project Structure",
        "9. Configuration (Environment Variables)",
        "10. Setup & Installation",
        "11. Running the Application",
        "12. Ingesting HR Policy Documents",
        "13. Testing",
        "14. API Reference",
        "15. Learning Outcomes & Future Enhancements",
        "16. Conclusion",
    ]
    story.append(bullets(toc_items))
    story.append(PageBreak())

    # ---------------- 1. Overview ----------------
    story.append(p("1. Project Overview", "H1Custom"))
    story.append(p(
        "The HR Support GenAI Assistant is a learning-oriented capstone project that demonstrates how "
        "to build a production-style Retrieval-Augmented Generation (RAG) chatbot for internal HR "
        "support. Employees can ask natural-language questions about leave, payroll, benefits, "
        "onboarding, and company policy. The system retrieves the most relevant passages from ingested "
        "HR policy PDFs, grounds the LLM's answer strictly in that content, and — when it cannot find a "
        "confident, grounded answer — automatically drafts and sends a professional escalation email to "
        "the correct internal team (IT, Payroll, or HR) after confirming with the employee.", "BodyCustom"))
    story.append(p(
        "The project intentionally keeps its dependency footprint small (regex-based guardrails instead "
        "of a heavyweight moderation library, MailHog instead of a production mail server) so every "
        "moving part remains easy to read, run locally, and reason about end-to-end.", "BodyCustom"))

    # ---------------- 2. Objectives ----------------
    story.append(p("2. Objectives", "H1Custom"))
    story.append(bullets([
        "Build a multi-agent architecture where each agent has a single, well-defined responsibility.",
        "Ground every answer in verifiable source documents to avoid hallucinated HR policy advice.",
        "Apply layered guardrails: input validation, prompt-injection detection, topic gating, PII redaction, "
        "and output groundedness checks.",
        "Support a transparent dev/prod switch between a free local LLM (Ollama) and a hosted LLM (OpenAI) "
        "without changing application code.",
        "Automate escalation of unanswered queries to the correct business team via a human-in-the-loop "
        "(confirm before sending) email workflow.",
        "Ship a minimal, dependency-light web UI for chatting and uploading policy PDFs.",
    ]))

    # ---------------- 3. Architecture ----------------
    story.append(p("3. System Architecture", "H1Custom"))
    story.append(p(
        "The request flow is a straight pipeline through three cooperating agents sitting behind a single "
        "FastAPI endpoint. Agent 1 gates and classifies the request, Agent 2 performs retrieval-grounded "
        "answering, and Agent 3 handles escalation and email notification when Agent 2 cannot help.",
        "BodyCustom"))
    diagram = build_architecture_diagram()
    scale = 0.6
    diagram.width *= scale
    diagram.height *= scale
    diagram.scale(scale, scale)
    story.append(diagram)
    story.append(PageBreak())

    # ---------------- 4. Multi-agent design ----------------
    story.append(p("4. Multi-Agent Design", "H1Custom"))

    story.append(p("4.1 Agent 1 — RouterAgent", "H2Custom"))
    story.append(p(
        "File: <font face='Helvetica-Oblique'>app/agents/router_agent.py</font>. This is the first line of "
        "defense. It runs input guardrails (message length, prompt-injection pattern matching) and a cheap "
        "keyword pre-filter for obvious HR topics before falling back to an LLM call that classifies the "
        "message into one of four intents.", "BodyCustom"))
    story.append(simple_table([
        ["Intent", "Meaning", "Behaviour"],
        ["HR_QUESTION", "A genuine HR/policy/payroll/benefits question", "Forwarded to Agent 2 (RagAgent)"],
        ["GREETING", "Small talk / hello", "Answered directly with a friendly greeting"],
        ["OFF_TOPIC", "Unrelated to HR (coding help, trivia, etc.)", "Blocked with a polite refusal"],
        ["UNSAFE", "Jailbreak attempts, abuse, secret extraction", "Blocked before reaching any LLM/RAG call"],
    ], col_widths=[3.3 * cm, 6.7 * cm, 6.5 * cm]))

    story.append(Spacer(1, 8))
    story.append(p("4.2 Agent 2 — RagAgent", "H2Custom"))
    story.append(p(
        "File: <font face='Helvetica-Oblique'>app/agents/rag_agent.py</font>. Performs the core RAG loop:",
        "BodyCustom"))
    story.append(bullets([
        "Runs a similarity search against ChromaDB (collection <font face='Helvetica-Oblique'>hr_docs</font>) "
        "and keeps only chunks whose relevance score passes <font face='Helvetica-Oblique'>MIN_RELEVANT_SCORE</font>.",
        "If no relevant chunk is found, it does not answer from memory — it asks the user for confirmation "
        "before escalating.",
        "Otherwise, it prompts the LLM with a strict system instruction to answer only from the retrieved "
        "context and cite the source file name(s).",
        "Redacts PII (SSN, email, phone, credit card) from the generated answer.",
        "Runs a groundedness check; low-confidence/ungrounded answers also trigger the escalation "
        "confirmation flow instead of being shown to the user as fact.",
    ]))

    story.append(Spacer(1, 8))
    story.append(p("4.3 Agent 3 — EscalationAgent", "H2Custom"))
    story.append(p(
        "File: <font face='Helvetica-Oblique'>app/agents/escalation_agent.py</font>. Once the employee "
        "confirms they want to escalate and supplies their Employee ID and official email address, this "
        "agent:", "BodyCustom"))
    story.append(bullets([
        "Classifies the request into exactly one owning team — IT, PAYROLL, or HR — using a dedicated LLM "
        "prompt.",
        "Looks up that team's mailbox from configuration (IT_TEAM_EMAIL / PAYROLL_TEAM_EMAIL / "
        "HR_TEAM_EMAIL).",
        "Drafts a complete, professional email with a descriptive subject line "
        "(\"HR Support Escalation - &lt;Employee ID&gt; needs &lt;Team&gt; assistance\"), the employee's "
        "ID/email, the escalation reason, the original (PII-redacted) request, and a Reply-To header set to "
        "the employee's email so the team can respond directly.",
        "Sends the email over SMTP — MailHog for local development, any real SMTP server in production.",
    ]))

    # ---------------- 5. Guardrails ----------------
    story.append(p("5. Guardrails & Safety", "H1Custom"))
    story.append(p(
        "File: <font face='Helvetica-Oblique'>app/guardrails.py</font>. Implemented with plain regular "
        "expressions on purpose, to keep the safety layer transparent and dependency-free for a learning "
        "project.", "BodyCustom"))
    story.append(bullets([
        "<b>Length check</b> — rejects messages longer than MAX_INPUT_CHARS.",
        "<b>Prompt-injection detection</b> — blocks phrases like \"ignore previous instructions\", "
        "\"developer mode\", or requests to reveal the system prompt.",
        "<b>Topic gate</b> — a keyword allow-list (leave, payroll, benefits, policy, etc.) used as a fast "
        "pre-filter before the LLM intent classification.",
        "<b>PII redaction</b> — regex-based redaction of SSNs, emails, phone numbers, and credit-card-like "
        "numbers from both escalation emails and generated answers.",
        "<b>Groundedness check</b> — rejects answers that appear confident but were not backed by retrieved "
        "context.",
    ]))

    # ---------------- 6. Escalation workflow ----------------
    story.append(p("6. Escalation & Email Workflow", "H1Custom"))
    story.append(p(
        "Escalation is a human-in-the-loop, multi-turn conversation rather than a silent background action, "
        "so the employee always stays in control of whether an email is sent on their behalf. State is kept "
        "in-memory per <font face='Helvetica-Oblique'>session_id</font> in "
        "<font face='Helvetica-Oblique'>app/main.py</font>.", "BodyCustom"))
    story.append(bullets([
        "<b>Step 1 — Confirm:</b> RagAgent could not answer confidently, so the bot asks: "
        "\"...Would you like me to notify the relevant team by email? (yes/no)\".",
        "<b>Step 2 — Collect details:</b> if the user says yes, the bot asks for their Employee ID and "
        "official email address, e.g. <font face='Helvetica-Oblique'>\"EMP1234, jane.doe@company.com\"</font>.",
        "<b>Step 3 — Send:</b> once both values are parsed successfully, EscalationAgent classifies the "
        "department and sends the drafted email; the bot confirms back to the user which team was notified.",
        "If the user declines at Step 1, or the details cannot be parsed, no email is ever sent.",
    ]))

    # ---------------- 7. Tech stack ----------------
    story.append(p("7. Technology Stack", "H1Custom"))
    story.append(simple_table([
        ["Layer", "Technology"],
        ["API framework", "FastAPI + Uvicorn"],
        ["Orchestration", "LangChain (langchain, langchain-community, langchain-text-splitters)"],
        ["LLM (dev)", "Ollama — llama3.1 (chat), nomic-embed-text (embeddings), local & free"],
        ["LLM (prod)", "OpenAI — gpt-4o-mini (chat), text-embedding-3-small (embeddings)"],
        ["Vector store", "ChromaDB, persisted to data/chroma_db, collection hr_docs"],
        ["PDF ingestion", "pypdf + LangChain text splitters"],
        ["Validation", "Pydantic v2 / pydantic-settings"],
        ["Guardrails", "Custom regex-based checks (no extra dependency)"],
        ["Email delivery (dev)", "MailHog (SMTP catch-all on 1025, web UI on 8025)"],
        ["Frontend", "Vanilla HTML / CSS / JavaScript"],
        ["Testing", "pytest, httpx"],
    ], col_widths=[4.5 * cm, 12 * cm]))

    story.append(PageBreak())

    # ---------------- 8. Project structure ----------------
    story.append(p("8. Project Structure", "H1Custom"))
    story.append(code_block(
        "app/\n"
        "  agents/\n"
        "    router_agent.py      # Agent 1: guardrails + intent routing\n"
        "    rag_agent.py         # Agent 2: retrieval + grounded answer + escalation trigger\n"
        "    escalation_agent.py  # Agent 3: department classification + email notification\n"
        "  config.py              # env-driven settings (dev/prod provider switch, SMTP)\n"
        "  llm.py / embeddings.py # provider factories (Ollama <-> OpenAI)\n"
        "  vectorstore.py         # Chroma wrapper\n"
        "  ingestion.py           # PDF -> chunks -> embeddings -> Chroma\n"
        "  guardrails.py          # PII redaction, injection/topic checks\n"
        "  schemas.py             # pydantic request/response models\n"
        "  main.py                # FastAPI app (chat, ingest, health endpoints)\n"
        "  static/                # minimal HTML/CSS/JS chat UI\n"
        "data/\n"
        "  pdfs/                  # drop HR policy PDFs here (or upload via UI)\n"
        "  chroma_db/             # persisted vector store (gitignored)\n"
        "scripts/\n"
        "  ingest.py              # CLI: ingest every PDF in data/pdfs\n"
        "tests/\n"
        "  test_guardrails.py"
    ))

    # ---------------- 9. Configuration ----------------
    story.append(p("9. Configuration (Environment Variables)", "H1Custom"))
    story.append(p(
        "All settings live in <font face='Helvetica-Oblique'>app/config.py</font> and are loaded from a "
        "local <font face='Helvetica-Oblique'>.env</font> file via pydantic-settings.", "BodyCustom"))
    story.append(simple_table([
        ["Variable", "Purpose", "Default"],
        ["ENV", "\"dev\" -> Ollama, \"prod\" -> OpenAI", "dev"],
        ["LLM_PROVIDER", "Force \"ollama\" or \"openai\" explicitly", "(unset)"],
        ["OLLAMA_BASE_URL / OLLAMA_MODEL / OLLAMA_EMBED_MODEL", "Local model config", "llama3.1 / nomic-embed-text"],
        ["OPENAI_API_KEY / OPENAI_MODEL / OPENAI_EMBED_MODEL", "Hosted model config", "gpt-4o-mini / text-embedding-3-small"],
        ["CHROMA_DIR / PDF_DIR", "Storage locations", "data/chroma_db / data/pdfs"],
        ["TOP_K / MAX_INPUT_CHARS / MIN_RELEVANT_SCORE", "RAG & guardrail tuning", "4 / 2000 / 0.3"],
        ["SMTP_HOST / SMTP_PORT / SMTP_FROM", "Outbound mail server for escalations", "localhost / 1025"],
        ["IT_TEAM_EMAIL / PAYROLL_TEAM_EMAIL / HR_TEAM_EMAIL", "Escalation recipients per department", "example.com addresses"],
    ], col_widths=[6.3 * cm, 6.7 * cm, 3.5 * cm]))

    story.append(PageBreak())

    # ---------------- 10. Setup ----------------
    story.append(p("10. Setup & Installation", "H1Custom"))
    story.append(p("10.1 Create and activate a virtual environment, then install dependencies:", "H2Custom"))
    story.append(code_block(
        "python -m venv .venv\n"
        ".venv\\Scripts\\Activate.ps1\n"
        "pip install -r requirements.txt"
    ))
    story.append(p("10.2 Copy the environment template:", "H2Custom"))
    story.append(code_block("copy .env.example .env"))
    story.append(p("10.3 Dev mode (local, free) — install Ollama and pull the models used:", "H2Custom"))
    story.append(code_block(
        "ollama pull llama3.1\n"
        "ollama pull nomic-embed-text"
    ))
    story.append(p("Keep ENV=dev in .env (default).", "BodyCustom"))
    story.append(p("10.4 Prod mode (OpenAI) — set in .env:", "H2Custom"))
    story.append(code_block("ENV=prod\nOPENAI_API_KEY=sk-..."))
    story.append(p("10.5 Escalation email (local dev) — run MailHog to catch escalation emails:", "H2Custom"))
    story.append(code_block(
        "docker run -d --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog"
    ))
    story.append(p(
        "Then open http://localhost:8025 to view every escalation email sent by the assistant. "
        "SMTP_HOST/SMTP_PORT in .env already default to MailHog's localhost:1025.", "BodyCustom"))

    # ---------------- 11. Running ----------------
    story.append(p("11. Running the Application", "H1Custom"))
    story.append(code_block("uvicorn app.main:app --reload"))
    story.append(p("Then open http://127.0.0.1:8000 in a browser and start chatting.", "BodyCustom"))

    # ---------------- 12. Ingestion ----------------
    story.append(p("12. Ingesting HR Policy Documents", "H1Custom"))
    story.append(p("Option A — CLI: drop PDFs into data/pdfs/ then run:", "BodyCustom"))
    story.append(code_block("python scripts/ingest.py"))
    story.append(p("Option B — Web UI: drag-and-drop PDFs from the running chat UI "
                    "(calls POST /api/ingest).", "BodyCustom"))

    # ---------------- 13. Testing ----------------
    story.append(p("13. Testing", "H1Custom"))
    story.append(code_block("pytest"))
    story.append(p(
        "tests/test_guardrails.py covers the regex-based guardrail logic (length limits, prompt-injection "
        "detection, PII redaction, HR keyword gating).", "BodyCustom"))

    # ---------------- 14. API reference ----------------
    story.append(p("14. API Reference", "H1Custom"))
    story.append(simple_table([
        ["Endpoint", "Method", "Description"],
        ["/", "GET", "Serves the chat web UI (index.html)"],
        ["/api/health", "GET", "Returns service status and active LLM provider"],
        ["/api/chat", "POST", "Main chat endpoint; drives routing, RAG answering, and the "
                              "escalation confirm/collect/send state machine"],
        ["/api/ingest", "POST", "Uploads one or more PDFs, chunks and embeds them into ChromaDB"],
    ], col_widths=[3 * cm, 2.2 * cm, 11.3 * cm]))

    # ---------------- 15. Future enhancements ----------------
    story.append(p("15. Learning Outcomes & Future Enhancements", "H1Custom"))
    story.append(p("What this project demonstrates:", "H2Custom"))
    story.append(bullets([
        "Designing a multi-agent pipeline where each agent has a single responsibility.",
        "Grounding LLM output in retrieved evidence and refusing to answer when evidence is insufficient.",
        "Layered, dependency-light guardrails suitable for learning before adopting a full framework.",
        "A configurable, provider-agnostic LLM/embedding layer (local vs. hosted).",
        "A human-in-the-loop escalation workflow with professional, automatically drafted email.",
    ]))
    story.append(p("Potential next steps:", "H2Custom"))
    story.append(bullets([
        "Swap the keyword-based topic gate for a proper classifier or a library such as guardrails-ai or "
        "nemo-guardrails.",
        "Persist conversation memory beyond a single stateless message per turn.",
        "Add authentication/authorization before exposing this beyond local experimentation.",
        "Model the router -> RAG -> escalation flow explicitly as a graph (e.g. LangGraph).",
        "Replace MailHog with a production SMTP provider and add retry / dead-lettering for failed "
        "escalation emails.",
    ]))

    # ---------------- 16. Conclusion ----------------
    story.append(p("16. Conclusion", "H1Custom"))
    story.append(p(
        "This capstone project delivers a working, end-to-end example of a safe, grounded, multi-agent RAG "
        "assistant for internal HR support — covering retrieval-augmented answering, layered guardrails, "
        "and an automated yet consent-driven escalation workflow to the right internal team by email. It is "
        "intentionally small and readable so every design decision can be traced back to a single file.",
        "BodyCustom"))

    doc.build(story)
    print(f"PDF written to: {PDF_PATH}")


if __name__ == "__main__":
    build_pdf()
