# HR Support GenAI Demo

A small learning project demonstrating a 2-agent RAG chatbot with ChromaDB,
guardrails/validation, and a minimal FastAPI + HTML/JS UI.

## Architecture

```
User -> FastAPI (/api/chat)
          -> Agent 1: RouterAgent      (guardrails: length, prompt-injection, topic gate + LLM intent classification)
          -> Agent 2: RagAgent         (Chroma similarity search -> grounded LLM answer, or escalation)
          -> Agent 3: EscalationAgent  (classifies IT/PAYROLL/HR and emails the right team via MailHog)
```

- **Agent 1 – RouterAgent** ([app/agents/router_agent.py](app/agents/router_agent.py)): validates
  the input (length, prompt-injection patterns), then classifies intent as
  `HR_QUESTION`, `GREETING`, `OFF_TOPIC`, or `UNSAFE`. Off-topic/unsafe messages are blocked before
  they ever reach the RAG pipeline.
- **Agent 2 – RagAgent** ([app/agents/rag_agent.py](app/agents/rag_agent.py)): retrieves the most
  relevant chunks from ChromaDB, asks the LLM to answer **only** from that context, redacts PII in
  the output, and checks groundedness. If no relevant context is found (or the answer isn't
  grounded), it hands off to the `EscalationAgent`.
- **Agent 3 – EscalationAgent** ([app/agents/escalation_agent.py](app/agents/escalation_agent.py)):
  classifies the unresolved request into `IT`, `PAYROLL`, or `HR`, then emails the corresponding
  team (via SMTP — MailHog locally) with the redacted message and escalation reason.
- **Guardrails** ([app/guardrails.py](app/guardrails.py)): regex-based PII redaction (SSN, email,
  phone, credit card), prompt-injection detection, input length limits, and an HR-topic keyword
  gate — kept dependency-free on purpose for a learning project.
- **Vector store**: ChromaDB, persisted to `data/chroma_db/`, collection `hr_docs`.
- **LLM/embeddings provider switch** ([app/config.py](app/config.py), [app/llm.py](app/llm.py),
  [app/embeddings.py](app/embeddings.py)): `ENV=dev` uses local **Ollama** (free, offline);
  `ENV=prod` (or `LLM_PROVIDER=openai`) uses **OpenAI**.

## Project layout

```
app/
  agents/
    router_agent.py      # Agent 1: guardrails + intent routing
    rag_agent.py          # Agent 2: retrieval + grounded answer + escalation
    escalation_agent.py   # Agent 3: IT/PAYROLL/HR classification + email notification
  config.py              # env-driven settings (dev/prod provider switch, SMTP)
  llm.py / embeddings.py # provider factories (Ollama <-> OpenAI)
  vectorstore.py         # Chroma wrapper
  ingestion.py           # PDF -> chunks -> embeddings -> Chroma
  guardrails.py          # PII redaction, injection/topic checks
  schemas.py             # pydantic request/response models
  main.py                # FastAPI app (chat, ingest, health endpoints)
  static/                # minimal HTML/CSS/JS chat UI
data/
  pdfs/                  # drop HR policy PDFs here (or upload via UI)
  chroma_db/             # persisted vector store (gitignored)
scripts/
  ingest.py              # CLI: ingest every PDF in data/pdfs
tests/
  test_guardrails.py
```

## Setup

1. Create and activate a virtual environment, then install dependencies:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and adjust as needed:

   ```powershell
   copy .env.example .env
   ```

3. **Dev mode (local, free)** — install [Ollama](https://ollama.com), then pull the models used:

   ```powershell
   ollama pull llama3.1
   ollama pull nomic-embed-text
   ```

   Keep `ENV=dev` in `.env` (default).

4. **Prod mode (OpenAI)** — set in `.env`:

   ```
   ENV=prod
   OPENAI_API_KEY=sk-...
   ```

5. **Escalation email (local dev)** — run [MailHog](https://github.com/mailhog/MailHog) to catch
   emails sent to IT/Payroll/HR without a real mail server:

   ```powershell
   docker run -d --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog
   ```

   Then open http://localhost:8025 to view escalation emails. `SMTP_HOST`/`SMTP_PORT` in `.env`
   already default to MailHog's `localhost:1025`; adjust `IT_TEAM_EMAIL`, `PAYROLL_TEAM_EMAIL`,
   and `HR_TEAM_EMAIL` to whatever addresses you want to test with.

## Ingest HR policy PDFs

Put PDF files in `data/pdfs/` then run:

```powershell
python scripts/ingest.py
```

Or drag-and-drop PDFs from the running web UI (uses `POST /api/ingest`).

## Run the app

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and start chatting.

## Run tests

```powershell
pytest
```

## Notes / next steps for learning

- Swap the keyword-based topic gate in `guardrails.py` for a proper classifier or
  a library like `guardrails-ai` or `nemo-guardrails` once comfortable with the basics.
- Add conversation memory (currently each `/api/chat` call is stateless per message).
- Add authentication before exposing this beyond local experimentation.
- Try LangGraph to make the router -> RAG -> escalation flow an explicit graph instead of
  plain Python function calls.
- Swap MailHog for a real SMTP provider (or a queue) and add retry/dead-lettering for failed
  escalation emails in production.
