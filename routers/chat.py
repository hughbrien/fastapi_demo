import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from opentelemetry import trace

router = APIRouter()
tracer = trace.get_tracer(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
CHAT_MODEL = "llama3.2:latest"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    message: str
    model: str
    history: list[ChatMessage]


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    authorization: Optional[str] = Header(None),
):
    with tracer.start_as_current_span("chat.message") as span:
        span.set_attribute("chat.model", CHAT_MODEL)
        span.set_attribute("chat.history_length", len(request.history))
        span.set_attribute("chat.message_length", len(request.message))

        # Build message history for Ollama chat API
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.history
        ]
        messages.append({"role": "user", "content": request.message})

        span.add_event("Calling Ollama chat model", {"model": CHAT_MODEL, "url": OLLAMA_BASE_URL})

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": CHAT_MODEL,
                        "messages": messages,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                result = response.json()
                assistant_content = result.get("message", {}).get("content", "").strip()
                span.set_attribute("chat.response_length", len(assistant_content))
            except httpx.ConnectError:
                raise HTTPException(
                    status_code=503,
                    detail=f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. Ensure Ollama is running."
                )
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=502,
                    detail=f"Ollama returned error: {e.response.status_code}"
                )

        updated_history = list(request.history) + [
            ChatMessage(role="user", content=request.message),
            ChatMessage(role="assistant", content=assistant_content),
        ]

        return ChatResponse(
            message=assistant_content,
            model=CHAT_MODEL,
            history=updated_history,
        )
