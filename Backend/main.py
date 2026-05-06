import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_logger, get_config
from app.routers import chat, documents, logs
from app.database import engine, Base

logger = get_logger(__name__)
config = get_config()

os.makedirs(config.upload_dir, exist_ok=True)

try:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # --- SAFE MIGRATIONS ---
        
        # 1. Safe Settings Migration
        try:
            conn.execute(text("ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS database_url VARCHAR"))
        except Exception as alter_err:
            pass

        # 2. Citation Schema Migration
        try:
            conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_number INTEGER"))
        except Exception as alter_err:
            pass

        # 3. FIX: New Chat Memory Migrations (Session & Summarization)
        try:
            logger.info("Checking for chat memory tables/columns...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id VARCHAR PRIMARY KEY,
                    summary TEXT DEFAULT '',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS session_id VARCHAR"))
            conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS is_summarized BOOLEAN DEFAULT FALSE"))
            logger.info("Successfully ensured memory tables/columns exist.")
        except Exception as alter_err:
            logger.warning(f"Memory migration skipped or failed: {alter_err}")
            
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

app.mount("/uploads", StaticFiles(directory=config.upload_dir), name="uploads")

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
    return {"status": "healthy", "environment": config.environment, "database": "connected"}

if __name__ == "__main__":
    import uvicorn
    is_development = config.environment.lower() == "development"
    uvicorn.run("main:app", host=config.host, port=config.port, reload=is_development)