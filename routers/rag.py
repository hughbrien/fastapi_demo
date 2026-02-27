import math
import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from opentelemetry import trace

router = APIRouter()
tracer = trace.get_tracer(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
RAG_MODEL = "qwen2.5:latest"

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
    if not union:
        return 0.0
    return len(intersection) / len(union)


def find_relevant_documents(query: str, top_k: int = 3) -> list[tuple[str, float]]:
    query_tokens = tokenize(query)
    scored = [
        (doc, jaccard_similarity(query_tokens, tokenize(doc)))
        for doc in corpus_of_documents
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


class RagRequest(BaseModel):
    query: str


class RagResponse(BaseModel):
    query: str
    answer: str
    context_documents: list[str]
    model: str


@router.post("/query", response_model=RagResponse)
async def rag_query(
    request: RagRequest,
    authorization: Optional[str] = Header(None),
):
    with tracer.start_as_current_span("rag.query") as span:
        span.set_attribute("rag.query", request.query)
        span.set_attribute("rag.model", RAG_MODEL)

        # Retrieve relevant documents
        relevant_docs = find_relevant_documents(request.query)
        context = "\n".join(f"- {doc}" for doc, _ in relevant_docs)
        context_list = [doc for doc, _ in relevant_docs]

        span.set_attribute("rag.num_docs_retrieved", len(relevant_docs))

        prompt = (
            f"You are a helpful assistant. Use the following context to answer the question.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {request.query}\n\n"
            f"Answer:"
        )

        span.add_event("Calling Ollama RAG model", {"model": RAG_MODEL, "url": OLLAMA_BASE_URL})

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": RAG_MODEL,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                result = response.json()
                answer = result.get("response", "").strip()
                span.set_attribute("rag.answer_length", len(answer))
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

        return RagResponse(
            query=request.query,
            answer=answer,
            context_documents=context_list,
            model=RAG_MODEL,
        )
