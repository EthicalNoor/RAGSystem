from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from app.models import DocumentModel, QueryLogModel, GraphEdgeModel, SystemSettingsModel
from app.config import get_logger

logger = get_logger(__name__)

class SQLRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_settings(self) -> SystemSettingsModel:
        settings = self.db.query(SystemSettingsModel).filter_by(id="default").first()
        if not settings:
            settings = SystemSettingsModel(
                id="default", api_provider="", embedding_model="", llm_model="",
                chunk_size=1024, temperature=0.2, rag_type="standard"
            )
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        return settings

    def update_settings(self, payload: dict) -> SystemSettingsModel:
        settings = self.get_settings()
        for key, value in payload.items():
            if hasattr(settings, key) and key != "id":
                setattr(settings, key, value)
        self.db.commit()
        self.db.refresh(settings)
        return settings

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
            query_text=query_text, response_snippet=response_snippet,
            latency_ms=latency_ms, source_count=source_count, status=status
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
            return True
        except Exception as e:
            self.db.rollback()
            raise e

    def upsert_graph_edges(self, document_id: str, triplets: List[Dict[str, str]]):
        db_edges = []
        for triplet in triplets:
            if "source" in triplet and "target" in triplet and "relation" in triplet:
                edge = GraphEdgeModel(
                    document_id=document_id,
                    source_node=str(triplet["source"]),
                    target_node=str(triplet["target"]),
                    relation=str(triplet["relation"])
                )
                db_edges.append(edge)
                
        if db_edges:
            self.db.add_all(db_edges)
            self.db.commit()

    def get_all_graph_edges(self) -> List[GraphEdgeModel]:
        return self.db.query(GraphEdgeModel).all()