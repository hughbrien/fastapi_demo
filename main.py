import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from traceloop.sdk import Traceloop
from opentelemetry import trace


from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from routers import auth, rag, chat

# Initialize TraceLoop observability
Traceloop.init(
    app_name="fastapi-demo",
    api_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
    disable_batch=False,
)
app = FastAPI(title="FastAPI Demo Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("application-start-span") as span:
    span.set_attribute("app.name", "fastapi-demo")
    span.set_attribute("app.version", "1.0.0")
    span.set_attribute("environment", "development")
    span.set_attribute("region", "florida_west")
    span.set_attribute("team", "dynatrace-se-team")
    span.end()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
