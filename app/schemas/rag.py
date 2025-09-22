from pydantic import BaseModel
from typing import List


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class PromptRequest(BaseModel):
    messages: List[ChatMessage]

    # {
    #   "messages": [
    #     { "role": "user", "content": "Why did Ted build you?" },
    #     { "role": "assistant", "content": "So I can fetch his resume faster than his dumbbell progress." },
    #     { "role": "user", "content": "Nice." }
    #   ]
    # }
