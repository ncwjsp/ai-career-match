"""Private SageMaker container protocol, separate from the public application API."""

import os
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter

from app.contracts.models import ProcessedText
from app.nlp.cpu_embedding import CpuEmbeddingClient
from app.nlp.entities import EnglishPipeline
from app.nlp.errors import NlpError
from app.nlp.processor import SharedTextProcessor
from app.nlp.types import NlpAnalysis

ANALYSIS = TypeAdapter(NlpAnalysis)


def create_endpoint(encoder=None, pipeline=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.encoder = encoder or CpuEmbeddingClient(
            os.environ.get("MODEL_DIR", "/opt/ml/model")
        )
        app.state.pipeline = pipeline or EnglishPipeline()
        # Model health means weights and NLP actually load, not just HTTP listening.
        app.state.pipeline("Python engineering")
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/ping")
    def ping():
        return {"status": "ready"}

    @app.post("/invocations")
    async def invoke(request: Request):
        # Bound bytes before JSON parsing, including clients without Content-Length.
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > 4 * 1024 * 1024:
                return JSONResponse({"error": "INPUT_TOO_LARGE"}, status_code=413)
        import json

        from starlette.concurrency import run_in_threadpool

        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Expected an object.")
            if payload.get("task") == "nlp":
                source = ProcessedText.model_validate(payload["source"])
                ids = {(e.document_id, e.document_version) for e in source.evidence}
                if len(ids) != 1:
                    raise ValueError("Invalid source identity.")
                doc_id, version = next(iter(ids))
                processor = SharedTextProcessor(doc_id, version, pipeline=app.state.pipeline)
                result = await run_in_threadpool(processor.analyze, source, "en")
                return {"analysis": ANALYSIS.dump_python(result, mode="json")}
            inputs = payload["inputs"]
            if not isinstance(inputs, list) or not all(isinstance(t, str) for t in inputs):
                raise ValueError("Expected string inputs.")
            result = await run_in_threadpool(app.state.encoder.embed, inputs)
            return asdict(result)
        except NlpError as error:
            return JSONResponse({"error": error.code}, status_code=422)
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "INVALID_INPUT"}, status_code=422)

    return app


app = create_endpoint()
