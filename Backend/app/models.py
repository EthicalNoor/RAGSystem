from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())
class UserModel(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True) # Google 'sub' id or Admin ID
    email = Column(String, unique=True)
    name = Column(String)
    picture = Column(String, nullable=True)
    role = Column(String, default="user") # <-- NEW: Role Tracking
    password = Column(String, nullable=True) # <-- NEW: For Admin Auth
    created_at = Column(DateTime(timezone=True), server_default=func.now())
class SystemSettingsModel(Base):
    __tablename__ = "system_settings"

    id = Column(String, primary_key=True, default="default")
    api_provider = Column(String, default="")
    embedding_model = Column(String, default="")
    llm_model = Column(String, default="")
    chunk_size = Column(Integer, default=1024)
    temperature = Column(Float, default=0.2)
    rag_type = Column(String, default="standard")
    openai_api_key = Column(String, nullable=True)
    gemini_api_key = Column(String, nullable=True)
    database_url = Column(String, nullable=True)

# --- NEW: Chat Session Model for Memory Summaries ---
class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True) # Uses session_id from frontend
    summary = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True) # <-- NEW

class DocumentModel(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    size_mb = Column(Float, nullable=False)
    status = Column(String, default="Pending") 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    chunks = relationship("DocumentChunkModel", back_populates="document", cascade="all, delete-orphan")
    graph_edges = relationship("GraphEdgeModel", back_populates="document", cascade="all, delete-orphan")

class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=True) 
    text_content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    document = relationship("DocumentModel", back_populates="chunks")

class GraphEdgeModel(Base):
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    source_node = Column(String, nullable=False)
    target_node = Column(String, nullable=False)
    relation = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("DocumentModel", back_populates="graph_edges")

class QueryLogModel(Base):
    __tablename__ = "query_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    
    # --- ADDED FOR MEMORY TRACKING ---
    session_id = Column(String, nullable=True) 
    is_summarized = Column(Boolean, default=False)
    
    query_text = Column(Text, nullable=False)
    response_snippet = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    source_count = Column(Integer, default=0)
    status = Column(String, default="Success")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    feedback_score = Column(Integer, nullable=True) # e.g., 1 for thumbs up, -1 for down
    feedback_text = Column(String, nullable=True)