from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import DocumentModel, QueryLogModel
from app.config import get_logger

logger = get_logger(__name__)

class SQLRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_document(self, name: str, file_type: str, size_mb: float) -> DocumentModel:
        db_doc = DocumentModel(name=name, file_type=file_type, size_mb=size_mb)
        self.db.add(db_doc)
        self.db.commit()
        self.db.refresh(db_doc)
        return db_doc

    def get_document(self, doc_id: str) -> Optional[DocumentModel]:
        return self.db.query(DocumentModel).filter(DocumentModel.id == doc_id).first()

    def get_all_documents(self) -> List[DocumentModel]:
        return self.db.query(DocumentModel).order_by(DocumentModel.created_at.desc()).all()

    def update_document_status(self, doc_id: str, status: str):
        doc = self.get_document(doc_id)
        if doc:
            doc.status = status
            self.db.commit()

    def delete_document(self, doc_id: str) -> bool:
        doc = self.get_document(doc_id)
        if doc:
            self.db.delete(doc)
            self.db.commit()
            return True
        return False

    def create_query_log(self, query_text: str, response_snippet: str, latency_ms: int, source_count: int, status: str = "Success") -> QueryLogModel:
        log = QueryLogModel(
            query_text=query_text,
            response_snippet=response_snippet,
            latency_ms=latency_ms,
            source_count=source_count,
            status=status
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_query_logs(self, limit: int = 100) -> List[QueryLogModel]:
        return self.db.query(QueryLogModel).order_by(QueryLogModel.created_at.desc()).limit(limit).all()
    
    def delete_all_query_logs(self) -> bool:
        try:
            self.db.query(QueryLogModel).delete()
            self.db.commit()
            logger.info("Successfully deleted all query logs from the database.")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete query logs: {e}")
            raise e