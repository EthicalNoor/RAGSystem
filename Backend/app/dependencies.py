from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.repositories.sql_repo import SQLRepository
from app.repositories.vector_repo import VectorRepository
from app.services.document_svc import DocumentService
from app.services.rag_service import RAGService
from app.services.chat_service import ChatService
from app.config import get_config, Config

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_sql_repo(db: Session = Depends(get_db)) -> SQLRepository:
    return SQLRepository(db)

def get_vector_repo(db: Session = Depends(get_db)) -> VectorRepository:
    return VectorRepository(db)

def get_document_service(
    sql_repo: SQLRepository = Depends(get_sql_repo),
    config: Config = Depends(get_config)
) -> DocumentService:
    return DocumentService(sql_repo, config)

def get_rag_service(
    doc_service: DocumentService = Depends(get_document_service),
    vector_repo: VectorRepository = Depends(get_vector_repo)
) -> RAGService:
    return RAGService(doc_service, vector_repo)

def get_chat_service(
    rag_service: RAGService = Depends(get_rag_service),
    sql_repo: SQLRepository = Depends(get_sql_repo),
    config: Config = Depends(get_config)
) -> ChatService:
    return ChatService(rag_service, sql_repo, config)