from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from app.schemas import (
    QueryLogResponse, DashboardMetricsResponse, 
    VectorDBHealthResponse, SettingsPayload
)
from app.repositories.sql_repo import SQLRepository
from app.repositories.vector_repo import VectorRepository
from app.dependencies import get_sql_repo, get_vector_repo
from app.config import get_logger
from datetime import datetime

from google import genai
from openai import OpenAI
from app.security import MASK, decrypt_key # <-- IMPORT ADDED

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

@router.get("/graphdb/data")
async def get_graph_data(sql_repo: SQLRepository = Depends(get_sql_repo)):
    edges = sql_repo.get_all_graph_edges()
    
    nodes_set = set()
    links = []
    
    for edge in edges:
        nodes_set.add(edge.source_node)
        nodes_set.add(edge.target_node)
        links.append({
            "source": edge.source_node,
            "target": edge.target_node,
            "relation": edge.relation
        })
        
    return {
        "total_nodes": len(nodes_set),
        "total_edges": len(links),
        "nodes": [{"id": n} for n in nodes_set],
        "links": links
    }

@router.get("/settings", response_model=SettingsPayload)
async def get_system_settings(sql_repo: SQLRepository = Depends(get_sql_repo)):
    settings = sql_repo.get_settings()
    
    oai_display = MASK if settings.openai_api_key else ""
    gem_display = MASK if settings.gemini_api_key else ""
    
    return SettingsPayload(
        api_provider=settings.api_provider or "",
        embedding_model=settings.embedding_model or "",
        llm_model=settings.llm_model or "",
        chunk_size=settings.chunk_size or 1024,
        temperature=settings.temperature or 0.2,
        rag_type=settings.rag_type or "standard",
        database_url=settings.database_url or "",
        openai_api_key=oai_display,
        gemini_api_key=gem_display
    )

@router.put("/settings")
async def update_system_settings(payload: SettingsPayload, sql_repo: SQLRepository = Depends(get_sql_repo)):
    logger.info("Saving user settings directly to the database.")
    
    update_data = payload.dict(exclude_unset=True)
    mask = "••••••••••••••••••••••••••••••••"
    
    if update_data.get('openai_api_key') == mask or not update_data.get('openai_api_key'):
        update_data.pop('openai_api_key', None)
    if update_data.get('gemini_api_key') == mask or not update_data.get('gemini_api_key'):
        update_data.pop('gemini_api_key', None)
        
    sql_repo.update_settings(update_data)
    
    return {"status": "success", "message": "Settings securely saved to database."}

@router.get("/settings/models")
async def get_available_models(sql_repo: SQLRepository = Depends(get_sql_repo)):
    settings = sql_repo.get_settings()
    
    # --- FIX: DECRYPT KEYS BEFORE API CALLS ---
    decrypted_openai = decrypt_key(settings.openai_api_key)
    decrypted_gemini = decrypt_key(settings.gemini_api_key)
    
    models = {
        "openai": {"llm": [], "embedding": []},
        "gemini": {"llm": [], "embedding": []}
    }
    
    # Fetch OpenAI Models
    if decrypted_openai:
        try:
            client = OpenAI(api_key=decrypted_openai)
            openai_models = client.models.list()
            for m in openai_models.data:
                if "embed" in m.id:
                    models["openai"]["embedding"].append(m.id)
                elif "gpt" in m.id or "o1" in m.id or "o3" in m.id:
                    models["openai"]["llm"].append(m.id)
        except Exception as e:
            logger.warning(f"Could not fetch OpenAI models (Key might be invalid): {e}")

    # Fetch Gemini Models
    if decrypted_gemini:
        try:
            client = genai.Client(api_key=decrypted_gemini)
            gemini_models = client.models.list()
            for m_info in gemini_models:
                name = m_info.name.replace("models/", "")
                methods = getattr(m_info, 'supported_actions', getattr(m_info, 'supported_generation_methods', []))
                
                if not methods: 
                    continue
                    
                if "generateContent" in methods or "generateAnswer" in methods:
                    models["gemini"]["llm"].append(name)
                if "embedContent" in methods:
                    models["gemini"]["embedding"].append(name)
        except Exception as e:
            logger.warning(f"Could not fetch Gemini models (Key might be invalid): {e}")
            
    for provider in models:
        for m_type in models[provider]:
            models[provider][m_type].sort(reverse=True)
            
    return models