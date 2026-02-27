
# Uvicorn & FastAPI

## Uvicorn

Uvicorn is an **ASGI (Asynchronous Server Gateway Interface)** web server implementation for Python. Think of it as the runtime that sits between the network and your application code — it handles raw TCP connections, HTTP parsing, and hands off requests to your ASGI app.

It's built on top of `uvloop` (a fast event loop replacement for asyncio) and `httptools`, making it one of the fastest Python web servers available. The ASGI spec is the async successor to WSGI (which powered older frameworks like Flask/Django).

When you run:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Uvicorn starts an event loop, binds to the port, and feeds incoming HTTP requests into your FastAPI app.

---

## FastAPI

FastAPI is an **ASGI web framework** that runs on top of Uvicorn (or any ASGI server). It's built on two libraries: **Starlette** (the ASGI toolkit/routing layer) and **Pydantic** (data validation/serialization).

Key characteristics:

- Fully async-native, though it also supports sync route handlers
- Auto-generates OpenAPI/Swagger docs from your type hints
- Uses Python type annotations for request/response validation via Pydantic

```python
from fastapi import FastAPI

app = FastAPI()  # This is the ASGI application object Uvicorn receives
```

---

## FastAPI Routes

Routes map HTTP methods + paths to handler functions, very similar to Spring's `@GetMapping`, `@PostMapping`, etc.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

# GET with path parameter
@app.get("/items/{item_id}")
async def get_item(item_id: int):
    return {"item_id": item_id}

# GET with query parameters
@app.get("/items/")
async def list_items(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}

# POST with request body (Pydantic model)
@app.post("/items/")
async def create_item(item: Item):
    return item

# PUT
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    return {"item_id": item_id, **item.dict()}

# DELETE
@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    return {"deleted": item_id}
```

FastAPI automatically infers where parameters come from based on their name and type: if it matches a path segment it's a path param, if it's a Pydantic model it's the request body, otherwise it's a query param.

You can also use **APIRouter** to organize routes across files — equivalent to Spring's `@RestController` per domain:

```python
# routers/items.py
from fastapi import APIRouter
router = APIRouter(prefix="/items", tags=["items"])

@router.get("/{item_id}")
async def get_item(item_id: int): ...

# main.py
app.include_router(router)
```

---

## Are Routes Run in Separate Threads?

This is where it differs significantly from Spring Boot's traditional thread-per-request model.

### `async def` handlers — No threads

They run on the **single asyncio event loop thread**. Uvicorn uses a single-threaded event loop (like Node.js). Concurrency is achieved via cooperative multitasking — when a handler hits an `await`, it yields control back to the event loop to process another request.

```python
@app.get("/data")
async def get_data():
    result = await some_async_db_call()  # yields to event loop here
    return result
```

### `sync def` handlers — Yes, a thread pool

FastAPI is smart enough to detect regular (non-async) route handlers and automatically runs them in a **thread pool executor** so they don't block the event loop.

```python
@app.get("/blocking")
def blocking_route():
    time.sleep(2)  # FastAPI runs this in a threadpool automatically
    return {"done": True}
```

### The Practical Rule

| Handler Type | Execution Model | Use When |
|---|---|---|
| `async def` | Single event loop thread | I/O-bound: DB calls, HTTP requests, file reads |
| `sync def` | Thread pool executor | CPU-bound or legacy blocking code |

> ⚠️ **Never** call blocking code (like `time.sleep` or `requests.get`) inside an `async def` handler — it will block the **entire event loop**.

For a Spring Boot developer, the mental model shift is from **"one thread per request"** to **"one event loop + await points for concurrency"**.
