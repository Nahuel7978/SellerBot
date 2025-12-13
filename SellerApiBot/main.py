# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from Controllers.controller import router as api_router
import logging
import os

logger = logging.getLogger("scapi")
scheduler = None
job_cleaner = None


# Eventos (startup/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código de inicialización
    logger.info("API arrancando: inicializando recursos...")
    try:
        logger.info("✅ Inicialización completada")
        
    except Exception as e:
        logger.error(f"❌ Error durante inicialización: {e}")
        raise
    
    yield
    # Código de limpieza
    logger.info("API apagándose: cerrando recursos...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Laburen Chatbot Service",
        version="0.1.0",
        description="API para vender productos vía LLM",
        lifespan=lifespan
    )

    # Middlewares: CORS ejemplo (ajustar CORS_ORIGINS en config)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Routers
    app.include_router(api_router, prefix="/SellerAPIBot/v1")

    return app

app = create_app()