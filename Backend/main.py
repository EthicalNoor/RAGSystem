import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_logger, get_config
from app.routers import chat, documents, logs, auth, users
from migrate import run_migrations

logger = get_logger(__name__)
config = get_config()

os.makedirs(config.upload_dir, exist_ok=True)

# ==========================================
# DYNAMIC MIGRATION LOGIC
# ==========================================
DB_STATE_FILE = ".last_migrated_db"

def check_and_run_migrations():
    current_db_url = config.database_url
    if not current_db_url:
        logger.warning("No database_url found in environment/settings. Skipping migrations.")
        return

    last_db_url = None
    if os.path.exists(DB_STATE_FILE):
        with open(DB_STATE_FILE, "r") as f:
            last_db_url = f.read().strip()

    if current_db_url != last_db_url or True: 
        logger.info("Forcing migration to apply new database columns...")
        try:
            success = run_migrations(current_db_url)
            if success:
                with open(DB_STATE_FILE, "w") as f:
                    f.write(current_db_url)
        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
    else:
        logger.info("Database credentials unchanged. Skipping schema migrations.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    check_and_run_migrations()
    yield

# ==========================================
# FASTAPI APP INITIALIZATION
# ==========================================
app = FastAPI(
    title="RAG Control Center API",
    description="Production-grade FastAPI backend with pgvector",
    version="1.0.0",
    lifespan=lifespan 
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
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "environment": config.environment, "database": "connected"}

if __name__ == "__main__":
    import uvicorn
    is_development = config.environment.lower() == "development"
    uvicorn.run("main:app", host=config.host, port=config.port, reload=is_development)