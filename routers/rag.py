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
    "ollama/qwen2.5:latest":               {"api_base": OLLAMA_BASE_URL},
    "anthropic/claude-haiku-4-5-20251001": {},
    "anthropic/claude-sonnet-4-6":         {},
}
DEFAULT_MODEL = "ollama/qwen2.5:latest"

corpus_of_documents = [
    "Take a leisurely walk in the park and enjoy the fresh air.",
    "Visit a local museum and discover something new.",
    "Attend a live music concert and feel the rhythm.",
    "Go for a hike and admire the natural scenery.",
    "Have a picnic with friends and share some laughs.",
    "Explore a new cuisine by dining at an ethnic restaurant.",
    "Take a yoga class and stretch your body and mind.",
    "Join a local sports league and enjoy some friendly competition.",
    "Attend a workshop or lecture on a topic you're interested in.",
    "Visit an amusement park and ride the roller coasters.",
]


def tokenize(text: str) -> set:
    return set(text.lower().split())


def jaccard_similarity(query_tokens: set, doc_tokens: set) -> float:
    intersection = query_tokens & doc_tokens
    union = query_tokens | doc_tokens
    return len(intersection) / len(union) if union else 0.0


def find_relevant_documents(query: str, top_k: int = 3) -> list[tuple[str, float]]:
    query_tokens = tokenize(query)
    scored = [(doc, jaccard_similarity(query_tokens, tokenize(doc))) for doc in corpus_of_documents]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


class RagRequest(BaseModel):
    query: str
    model: str = DEFAULT_MODEL


class RagResponse(BaseModel):
    query: str
    answer: str
    context_documents: list[str]
    model: str


@router.get("/models")
async def list_models():
    return {"models": list(AVAILABLE_MODELS.keys()), "default": DEFAULT_MODEL}


@router.post("/query", response_model=RagResponse)
async def rag_query(
    request: RagRequest,
    authorization: Optional[str] = Header(None),
):
    if request.model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model '{request.model}'. Available: {list(AVAILABLE_MODELS)}")



    relevant_docs = find_relevant_documents(request.query)
    context = "\n".join(f"- {doc}" for doc, _ in relevant_docs)
    context_list = [doc for doc, _ in relevant_docs]

    messages = [{
        "role": "user",
        "content": (
            f"You are a helpful assistant. Use the following context to answer the question.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {request.query}\n\nAnswer:"
        ),
    }]

    model_kwargs = AVAILABLE_MODELS[request.model]

    try:
        response = await acompletion(
            model=request.model,
            messages=messages,
            timeout=60.0,
            **model_kwargs,
        )
        answer = response.choices[0].message.content.strip()
    except litellm.exceptions.APIConnectionError:
        raise HTTPException(status_code=503, detail=f"Cannot connect to model provider for '{request.model}'.")
    except litellm.exceptions.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid or missing API key for the selected provider.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return RagResponse(
        query=request.query,
        answer=answer,
        context_documents=context_list,
        model=request.model,
    )
