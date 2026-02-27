# TraceLoop Instrumentation of Downstream HTTP / API Calls in FastAPI

## How TraceLoop Instruments FastAPI

TraceLoop uses **OpenTelemetry's auto-instrumentation** libraries under the hood. For FastAPI + Uvicorn, it patches:

- `opentelemetry-instrumentation-fastapi` — creates a server span for each incoming request
- `opentelemetry-instrumentation-httpx` or `opentelemetry-instrumentation-requests` — creates child spans for outgoing HTTP calls

```python
from traceloop.sdk import Traceloop
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

Traceloop.init(app_name="my-service")
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()  # patches outgoing HTTP
```

---

## The Threading/Async Problem with Spans

This is where the async model matters a lot. OpenTelemetry propagates trace context via **Python's `contextvars.ContextVar`**, which is the async-safe equivalent of thread-local storage.

### `async def` handlers — Context propagates correctly ✅

Because `async def` handlers run on the same event loop thread and Python's `contextvars` are coroutine-aware, the trace context flows naturally from the incoming request span down into any `await`-ed outgoing calls.

```python
import httpx

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    async with httpx.AsyncClient() as client:
        # ✅ TraceLoop/OTEL will automatically create a child span here
        # Parent span context flows via ContextVar
        response = await client.get(f"https://upstream-api/items/{item_id}")
    return response.json()
```

You'll see: `GET /items/{item_id}` → child span `GET https://upstream-api/items/{item_id}`

### `sync def` handlers — Context can be LOST ⚠️

When FastAPI offloads a `sync def` handler to a **thread pool executor**, the `ContextVar` context is **copied** into the new thread at dispatch time. This usually works, but there are gotchas:

```python
import requests  # sync library

@app.get("/items/{item_id}")
def get_item_sync(item_id: int):
    # ⚠️ Context is copied to the thread — usually works
    # but only if using opentelemetry-instrumentation-requests
    response = requests.get(f"https://upstream-api/items/{item_id}")
    return response.json()
```

The risk: if you manually create threads or use `concurrent.futures` inside a handler, those **child threads do NOT inherit the context** automatically, and your spans become orphaned.

---

## The Key Rules for Guaranteed Child Spans

### 1. Use `httpx.AsyncClient` (not `requests`) in `async def` handlers

```python
# ✅ Correct — async client, async handler
@app.get("/data")
async def get_data():
    async with httpx.AsyncClient() as client:
        r = await client.get("https://other-service/api")
    return r.json()
```

### 2. If you must use `requests` in a sync handler, instrument it

```python
from opentelemetry.instrumentation.requests import RequestsInstrumentor
RequestsInstrumentor().instrument()  # patches requests library globally
```

### 3. If spawning manual threads, copy context explicitly

```python
import contextvars
from concurrent.futures import ThreadPoolExecutor

ctx = contextvars.copy_context()
with ThreadPoolExecutor() as pool:
    future = pool.submit(ctx.run, some_blocking_function)  # ✅ context carried in
```

---

## What Your Traces Should Look Like

```
[SERVER] GET /items/{item_id}          <- FastAPI instrumentation
    └── [CLIENT] GET upstream-api/...  <- httpx/requests instrumentation
            └── [CLIENT] GET db-api/...  <- if chained calls
```

TraceLoop will also add LLM spans if you're calling OpenAI/Anthropic, which slot in as siblings or children of your HTTP spans depending on call order.

---

## Quick Diagnostic Checklist

If you're **not seeing outgoing spans**, check:

| # | Check |
|---|---|
| 1 | Are you using `httpx.AsyncClient` and have `HTTPXClientInstrumentor().instrument()` called at startup? |
| 2 | Are you using `requests` but only instrumented `httpx` (or vice versa)? |
| 3 | Is `Traceloop.init()` called **before** `FastAPIInstrumentor.instrument_app(app)`? |
| 4 | Are you creating raw threads without copying context? |
| 5 | Is the upstream service receiving `traceparent` headers? If yes, instrumentation is working but the exporter may be the issue. |
