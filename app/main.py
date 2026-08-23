"""
Configuración de la aplicación FastAPI para os_open.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import hubs, metrics
from app.routers.executive_reports import router as executive_reports_router

app = FastAPI(
    title="OS Open API",
    description="API para dashboard de hubs y métricas",
    version="1.0.0",
)

# Configuración CORS para permitir frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(hubs.router, prefix="/api", tags=["hubs"])
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(executive_reports_router)


@app.get("/")
def root():
    return {"message": "OS Open API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
