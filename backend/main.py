from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from core.llm import generate_explanation
from core.repo_processor import build_code_context, prepare_repository

app = FastAPI(title="CodeLens AI — Local GitHub Repository Code Explainer", version="3.0.0")

class ExplainRequest(BaseModel):
    github_url: HttpUrl
    model: Optional[str] = Field(default=None, min_length=1)
    ollama_url: Optional[str] = None

class ExplainResponse(BaseModel):
    repository: str
    github_url: str
    explanation: dict
    files_analyzed: int
    total_candidate_files: int
    context_characters: int
    context_truncated: bool
    language_hints: list[str]
    manifest: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "codelens-ai", "version": "3.0.0"}

@app.post("/explain", response_model=ExplainResponse)
def explain_repository(request: ExplainRequest):
    try:
        data = prepare_repository(str(request.github_url))
        result = generate_explanation(
            data.name,
            build_code_context(data),
            model=request.model or os.getenv("OLLAMA_MODEL"),
            base_url=request.ollama_url or os.getenv("OLLAMA_BASE_URL"),
            manifest=data.manifest,
            documentation=data.documentation,
        )
        return ExplainResponse(
            repository=data.name,
            github_url=data.url,
            explanation=result,
            files_analyzed=len(data.files),
            total_candidate_files=data.total_candidate_files,
            context_characters=data.total_chars,
            context_truncated=data.truncated,
            language_hints=data.language_hints,
            manifest=data.manifest,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}") from exc
