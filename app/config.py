"""Central application settings loaded from environment / .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    llm_provider: str | None = None  # overrides the ENV-based default when set

    # Ollama (local/dev)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_embed_model: str = "nomic-embed-text"

    # OpenAI (prod)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    # Storage
    chroma_dir: str = "data/chroma_db"
    pdf_dir: str = "data/pdfs"

    # RAG / guardrails tuning
    top_k: int = 4
    max_input_chars: int = 2000
    min_relevant_score: float = 0.3

    # Escalation email (MailHog for local dev: smtp on 1025, web UI on 8025)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "hr-support-bot@example.com"
    it_team_email: str = "it-support@example.com"
    payroll_team_email: str = "payroll@example.com"
    hr_team_email: str = "hr-team@example.com"

    @property
    def provider(self) -> str:
        """Resolve which LLM backend to use: explicit override wins, else ENV decides."""
        if self.llm_provider:
            return self.llm_provider
        return "openai" if self.env == "prod" else "ollama"

    def resolve_path(self, relative: str) -> Path:
        path = BASE_DIR / relative
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
