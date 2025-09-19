import os

from openai import OpenAI

client = OpenAI()


def embed_text(text: str) -> list[float]:
    """Generate an embedding vector for given text."""
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding
