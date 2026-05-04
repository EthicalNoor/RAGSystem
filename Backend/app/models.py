from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

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

class DocumentModel(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    size_mb = Column(Float, nullable=False)
    status = Column(String, default="Pending") 
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Bidirectional relationships
    chunks = relationship("DocumentChunkModel", back_populates="document", cascade="all, delete-orphan")
    graph_edges = relationship("GraphEdgeModel", back_populates="document", cascade="all, delete-orphan")

class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # --- ADDED FOR CITATION MAPPING ---
    page_number = Column(Integer, nullable=True) 
    
    text_content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- RESTORED TO FIX SQLALCHEMY MAPPER ERROR ---
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
    query_text = Column(Text, nullable=False)
    response_snippet = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    source_count = Column(Integer, default=0)
    status = Column(String, default="Success")
    created_at = Column(DateTime(timezone=True), server_default=func.now())