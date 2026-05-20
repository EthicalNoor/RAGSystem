from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    role: str
    model_config = ConfigDict(from_attributes=True)

class DocumentResponse(BaseModel):
    id: str
    name: str
    type: str
    size: str
    status: str
    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(DocumentResponse):
    chunk_count: int
    graph_edge_count: int

class ChatSessionResponse(BaseModel):
    id: str
    summary: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class Citation(BaseModel):
    citation_idx: int
    id: str
    document: str
    page: int
    content: str
    score: float

class ChatResponse(BaseModel):
    response: str
    sources: List[str]
    citations: List[Citation] = []  
    message_id: str                 
    latency_ms: int
    query_id: str
    status: str

class QueryLogResponse(BaseModel):
    id: str
    query_text: str
    response_snippet: str
    latency_ms: int
    source_count: int
    status: str
    created_at: datetime
    feedback_score: Optional[int] = None
    feedback_text: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class FeedbackRequest(BaseModel):
    score: int
    text: Optional[str] = None

class DashboardMetricsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    storage_used_mb: float
    total_queries: int
    recent_activity: List[dict]

class VectorDBHealthResponse(BaseModel):
    status: str
    total_embeddings: int
    storage_used_mb: float
    last_updated: datetime

class SettingsPayload(BaseModel):
    api_provider: str
    embedding_model: str
    llm_model: str
    chunk_size: int
    temperature: float
    rag_type: str
    database_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None