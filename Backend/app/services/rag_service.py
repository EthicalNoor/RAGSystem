import json
import re
from typing import List
from fastapi import UploadFile
from google import genai
from openai import OpenAI
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
        settings = self.doc_service.sql_repo.get_settings()
        chunk_size = settings.chunk_size or 1024
        
        for doc_id in document_ids:
            try:
                chunks = self.doc_service.parse_and_chunk(doc_id, chunk_size=chunk_size)
                
                # Always create Vector Embeddings (Fallback mechanism)
                self.vector_repo.upsert_chunks(doc_id, chunks)

                # If Graph RAG is active, extract relationships via LLM
                if settings.rag_type == "graph":
                    logger.info(f"Graph RAG enabled. Extracting knowledge triplets for doc {doc_id}")
                    self._extract_and_save_graph(doc_id, chunks, settings)
                
                self.doc_service.sql_repo.update_document_status(doc_id, "Indexed")
                logger.info(f"Successfully processed and indexed document {doc_id}")
            except Exception as e:
                logger.error(f"Failed to process document {doc_id}: {str(e)}")
                self.doc_service.sql_repo.update_document_status(doc_id, "Failed")

    def search_context(self, query: str) -> List[dict]:
        logger.info(f"Searching pgvector store for context.")
        return self.vector_repo.search(query, top_k=10)

    def delete_document(self, document_id: str) -> bool:
        success = self.doc_service.sql_repo.delete_document(document_id)
        if success:
            logger.info(f"Document {document_id} and its vector chunks deleted.")
        return success

    def _extract_and_save_graph(self, document_id: str, chunks: List[dict], settings):
        """Uses LLM to extract Source->Relation->Target triplets from text."""
        provider = settings.api_provider
        all_triplets = []

        gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
        openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

        for chunk in chunks:
            prompt = (
                "Extract knowledge graph triplets from the following text. "
                "Identify key entities (people, places, concepts) and how they relate. "
                "Return strictly a valid JSON array of objects with keys: 'source', 'relation', 'target'. "
                "Do not use markdown blocks or include any other text.\n\n"
                f"Text:\n{chunk['text'][:2000]}" # Truncated for token safety
            )
            
            try:
                res_text = ""
                if provider == "gemini" and gemini_client:
                    model = settings.llm_model.replace("models/", "")
                    response = gemini_client.models.generate_content(model=model, contents=prompt)
                    res_text = response.text
                elif provider == "openai" and openai_client:
                    response = openai_client.chat.completions.create(
                        model=settings.llm_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1
                    )
                    res_text = response.choices[0].message.content
                
                # Clean markdown formatting in case the LLM ignores the 'strictly JSON' rule
                res_text = re.sub(r'```json\n|\n```|```', '', res_text).strip()
                triplets = json.loads(res_text)
                
                if isinstance(triplets, list):
                    all_triplets.extend(triplets)
                    
            except Exception as e:
                logger.warning(f"Failed to extract triplets for a chunk (LLM hallucinated JSON?): {e}")

        if all_triplets:
            self.doc_service.sql_repo.upsert_graph_edges(document_id, all_triplets)
            logger.info(f"Successfully saved {len(all_triplets)} graph edges for doc {document_id}")