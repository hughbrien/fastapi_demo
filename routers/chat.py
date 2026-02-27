from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from opentelemetry import trace
from litellm import acompletion
import litellm

router = APIRouter()
tracer = trace.get_tracer(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"

AVAILABLE_MODELS = {
    "ollama/llama3.2:latest":              {"api_base": OLLAMA_BASE_URL},
    "anthropic/claude-haiku-4-5-20251001": {},
    "anthropic/claude-sonnet-4-6":         {},
}
DEFAULT_MODEL = "ollama/llama3.2:latest"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    model: str = DEFAULT_MODEL


class ChatResponse(BaseModel):
    message: str
    model: str
    history: list[ChatMessage]


@router.get("/models")
async def list_models():
    return {"models": list(AVAILABLE_MODELS.keys()), "default": DEFAULT_MODEL}


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    authorization: Optional[str] = Header(None),
):
    if request.model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model '{request.model}'. Available: {list(AVAILABLE_MODELS)}")

    with tracer.start_as_current_span("chat.message") as span:
        span.set_attribute("chat.model", request.model)
        span.set_attribute("chat.history_length", len(request.history))
        span.set_attribute("chat.message_length", len(request.message))

        messages = [{"role": msg.role, "content": msg.content} for msg in request.history]
        messages.append({"role": "user", "content": request.message})

        model_kwargs = AVAILABLE_MODELS[request.model]
        span.add_event("Calling LiteLLM chat model", {"model": request.model})

        try:
            response = await acompletion(
                model=request.model,
                messages=messages,
                timeout=120.0,
                **model_kwargs,
            )
            assistant_content = response.choices[0].message.content.strip()
            span.set_attribute("chat.response_length", len(assistant_content))
        except litellm.exceptions.APIConnectionError:
            raise HTTPException(status_code=503, detail=f"Cannot connect to model provider for '{request.model}'.")
        except litellm.exceptions.AuthenticationError:
            raise HTTPException(status_code=401, detail="Invalid or missing API key for the selected provider.")
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

        updated_history = list(request.history) + [
            ChatMessage(role="user", content=request.message),
            ChatMessage(role="assistant", content=assistant_content),
        ]

        return ChatResponse(
            message=assistant_content,
            model=request.model,
            history=updated_history,
        )
