from typing import List
from fastapi import UploadFile
from app.services.document_svc import DocumentService
from app.repositories.vector_repo import VectorRepository
from app.config import get_logger

logger = get_logger(__name__)

class RAGService:
    def __init__(self, doc_service: DocumentService, vector_repo: VectorRepository):
        self.doc_service = doc_service
        self.vector_repo = vector_repo

    async def handle_uploads(self, files: List[UploadFile]):
        saved_docs = []
        for file in files:
            doc = await self.doc_service.save_upload(file)
            saved_docs.append(doc)
        return saved_docs

    def process_documents(self, document_ids: List[str]):
        chunk_size = self.doc_service.config.chunk_size
        
        for doc_id in document_ids:
            try:
                chunks = self.doc_service.parse_and_chunk(doc_id, chunk_size=chunk_size)
                self.vector_repo.upsert_chunks(doc_id, chunks)
                
                self.doc_service.sql_repo.update_document_status(doc_id, "Indexed")
                logger.info(f"Successfully processed and indexed document {doc_id}")
            except Exception as e:
                logger.error(f"Failed to process document {doc_id}: {str(e)}")
                self.doc_service.sql_repo.update_document_status(doc_id, "Failed")

    def search_context(self, query: str) -> List[dict]:
        logger.info(f"Searching pgvector store for context.")
        return self.vector_repo.search(query, top_k=3)

    def delete_document(self, document_id: str) -> bool:
        # Cascade logic in PostgreSQL handles deleting chunks automatically
        success = self.doc_service.sql_repo.delete_document(document_id)
        if success:
            logger.info(f"Document {document_id} and its vector chunks deleted.")
        return success