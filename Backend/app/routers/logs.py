from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.schemas import (
    QueryLogResponse, DashboardMetricsResponse, 
    VectorDBHealthResponse, SettingsPayload
)
from app.repositories.sql_repo import SQLRepository
from app.repositories.vector_repo import VectorRepository
from app.dependencies import get_sql_repo, get_vector_repo
from app.config import get_config, Config, get_logger
from datetime import datetime

logger = get_logger(__name__)
router = APIRouter()

@router.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    sql_repo: SQLRepository = Depends(get_sql_repo),
    vector_repo: VectorRepository = Depends(get_vector_repo)
):
    doc_count = len(sql_repo.get_all_documents())
    log_count = len(sql_repo.get_query_logs())
    vdb_stats = vector_repo.get_stats()
    
    return DashboardMetricsResponse(
        total_documents=doc_count,
        total_chunks=vdb_stats.get("total_embeddings", 0),
        storage_used_mb=vdb_stats.get("storage_used_mb", 0.0),
        total_queries=log_count,
        recent_activity=[{"action": "System Boot", "time": "Just now"}]
    )

@router.get("/logs/queries", response_model=List[QueryLogResponse])
async def get_query_logs(sql_repo: SQLRepository = Depends(get_sql_repo)):
    return sql_repo.get_query_logs(limit=50)

@router.delete("/logs/queries")
async def clear_query_logs(sql_repo: SQLRepository = Depends(get_sql_repo)):
    try:
        success = sql_repo.delete_all_query_logs()
        if success:
            return {"status": "success", "message": "All query logs deleted"}
        raise HTTPException(status_code=500, detail="Failed to delete logs")
    except Exception as e:
        logger.error(f"Error clearing logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while clearing logs")

@router.get("/vectordb/health", response_model=VectorDBHealthResponse)
async def get_vectordb_health(vector_repo: VectorRepository = Depends(get_vector_repo)):
    stats = vector_repo.get_stats()
    return VectorDBHealthResponse(
        status="Healthy" if vector_repo.ping() else "Offline",
        total_embeddings=stats.get("total_embeddings", 0),
        storage_used_mb=stats.get("storage_used_mb", 0.0),
        last_updated=datetime.now()
    )

@router.get("/settings", response_model=SettingsPayload)
async def get_system_settings(config: Config = Depends(get_config)):
    return SettingsPayload(
        api_provider=config.api_provider,
        embedding_model=config.embedding_model,
        llm_model=config.llm_model,
        chunk_size=config.chunk_size,
        temperature=config.temperature
    )

@router.put("/settings")
async def update_system_settings(payload: SettingsPayload, config: Config = Depends(get_config)):
    logger.info(f"Settings update requested. Switching to provider: {payload.api_provider}")
    
    # In-memory config update (In production, persist this to a DB or env file)
    config.api_provider = payload.api_provider
    config.embedding_model = payload.embedding_model
    config.llm_model = payload.llm_model
    config.chunk_size = payload.chunk_size
    config.temperature = payload.temperature
    
    return {"status": "success", "message": "Settings updated"}