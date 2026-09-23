"""Agent 2: retrieves grounded context from Chroma and answers, or escalates by email."""
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.escalation_agent import EscalationAgent
from app.config import settings
from app.guardrails import check_groundedness, redact_pii
from app.llm import get_llm
from app.vectorstore import get_vectorstore

_SYSTEM_PROMPT = """You are an HR support assistant. Answer ONLY using the context
provided below, which comes from official HR policy documents. If the context does
not contain the answer, say clearly that you don't know and that the request will be
escalated to the HR team. Never invent policy details. Keep answers concise and cite
the source file name(s) you used in parentheses at the end."""


@dataclass
class RagResult:
    answer: str
    sources: list[dict] = field(default_factory=list)
    escalated: bool = False
    escalated_to: str | None = None
    needs_confirmation: bool = False
    escalation_reason: str | None = None


class RagAgent:
    """Retrieval-augmented answering agent (Agent 2)."""

    def __init__(self):
        self._llm = get_llm(temperature=0.1)
        self._escalation_agent = EscalationAgent()

    def answer(self, message: str) -> RagResult:
        store = get_vectorstore()
        docs_with_scores = store.similarity_search_with_relevance_scores(
            message, k=settings.top_k
        )
        relevant = [
            (doc, score)
            for doc, score in docs_with_scores
            if score >= settings.min_relevant_score
        ]

        if not relevant:
            return RagResult(
                answer=(
                    "I couldn't find this in our HR policy documents. Would you like me to "
                    "notify the relevant team by email? (yes/no)"
                ),
                needs_confirmation=True,
                escalation_reason="No relevant HR documents found.",
            )

        context = "\n\n".join(f"[{doc.metadata.get('source', 'unknown')}]\n{doc.page_content}" for doc, _ in relevant)
        prompt = f"Context:\n{context}\n\nQuestion: {message}"
        response = self._llm.invoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        answer_text = redact_pii(response.content.strip())

        if not check_groundedness(answer_text, retrieved_any=True):
            return RagResult(
                answer=(
                    "I'm not confident enough in an answer from our policies. Would you like "
                    "me to notify the relevant team by email? (yes/no)"
                ),
                needs_confirmation=True,
                escalation_reason="Low-confidence / ungrounded answer.",
            )

        sources = [
            {"source": doc.metadata.get("source", "unknown"), "snippet": doc.page_content[:200]}
            for doc, _ in relevant
        ]
        return RagResult(answer=answer_text, sources=sources)

    def escalate(self, message: str, reason: str):
        """Sends the escalation email after the user has confirmed."""
        return self._escalation_agent.escalate(message, reason)

