import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_logger, get_config
from app.routers import chat, documents, logs
from app.database import engine, Base

logger = get_logger(__name__)
config = get_config()

# Initialize pgvector extension and create tables
try:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables and pgvector extension initialized.")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")

app = FastAPI(
    title="RAG Control Center API",
    description="Production-grade FastAPI backend with pgvector",
    version="1.0.0"
)

# Apply dynamic CORS settings from .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)} on {request.url}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred.", "path": str(request.url)}
    )

app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(logs.router, prefix="/api/v1/system", tags=["System & Logs"])

@app.get("/health", tags=["Health"])
async def health_check():
    logger.info("Health check endpoint pinged.")
    return {
        "status": "healthy", 
        "environment": config.environment,
        "database": "connected"
    }

if __name__ == "__main__":
    import uvicorn
    os.makedirs(config.upload_dir, exist_ok=True)
    
    # Automatically disable 'reload' if ENVIRONMENT is set to production
    is_development = config.environment.lower() == "development"
    
    uvicorn.run(
        "main:app", 
        host=config.host, 
        port=config.port, 
        reload=is_development
    )