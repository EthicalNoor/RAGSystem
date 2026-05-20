from typing import Generator
from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.database import SessionLocal
from app.repositories.sql_repo import SQLRepository
from app.repositories.vector_repo import VectorRepository
from app.services.document_svc import DocumentService
from app.services.rag_service import RAGService
from app.services.chat_service import ChatService
from app.config import get_config, Config

def get_current_user(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized - Missing Token")
    
    token = auth_header.split(" ")[1]
    
    # --- ALLOW ADMIN LOCAL BYPASS ---
    if token.startswith("admin-secret-token-"):
        return token.replace("admin-secret-token-", "")

    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request())
        return idinfo['sub'] 
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized - Invalid Token")

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