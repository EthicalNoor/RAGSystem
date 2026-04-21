from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class DocumentModel(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    size_mb = Column(Float, nullable=False)
    status = Column(String, default="Pending") # Pending, Indexed, Failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Cascade delete chunks if document is removed
    chunks = relationship("DocumentChunkModel", back_populates="document", cascade="all, delete-orphan")

class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text_content = Column(Text, nullable=False)
    # Using 1536 dimensions as standard for OpenAI embeddings. 
    # Adjust if using a different embedding model size.
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("DocumentModel", back_populates="chunks")

class QueryLogModel(Base):
    __tablename__ = "query_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    query_text = Column(Text, nullable=False)
    response_snippet = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    source_count = Column(Integer, default=0)
    status = Column(String, default="Success")
    created_at = Column(DateTime(timezone=True), server_default=func.now())