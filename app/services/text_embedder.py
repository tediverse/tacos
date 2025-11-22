from openai import OpenAI

from app.settings import settings


def embed_text(text: str, client: OpenAI | None = None) -> list[float]:
    """Generate an embedding vector for given text."""
    client = client or OpenAI(api_key=settings.OPENAI_API_KEY or None)
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding
