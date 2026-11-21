"""FastAPI application for Dear Tomorrow / Me² AI."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.questionnaire import router as questionnaire_router
from app.api.call import router as call_router

app = FastAPI(title="Dear Tomorrow API")
origins = [url.strip() for url in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if url.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(auth_router)
app.include_router(questionnaire_router)
app.include_router(call_router)

@app.get("/health")
def health():
    return {"status": "ok"}
