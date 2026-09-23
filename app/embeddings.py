"""Factory for the embeddings model, switching between local Ollama and OpenAI."""
from app.config import settings


def get_embeddings():
    if settings.provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.openai_embed_model,
            api_key=settings.openai_api_key,
        )

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )
