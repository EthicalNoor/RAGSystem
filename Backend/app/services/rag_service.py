import json
import os
import re
from typing import List
from fastapi import UploadFile
from google import genai
from openai import OpenAI
from app.services.document_svc import DocumentService
from app.repositories.vector_repo import VectorRepository
from app.config import get_logger
from app.security import decrypt_key
from tenacity import retry, stop_after_attempt, wait_exponential # <-- IMPORT ADDED

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
                self.vector_repo.upsert_chunks(doc_id, chunks)

                if settings.rag_type == "graph":
                    logger.info(f"Graph RAG enabled. Extracting knowledge triplets for doc {doc_id}")
                    self._extract_and_save_graph(doc_id, chunks, settings)
                
                self.doc_service.sql_repo.update_document_status(doc_id, "Indexed")
                logger.info(f"Successfully processed and indexed document {doc_id}")
            except Exception as e:
                logger.error(f"Failed to process document {doc_id}: {str(e)}")
                self.doc_service.sql_repo.update_document_status(doc_id, "Failed")

    def search_context(self, query: str) -> List[dict]:
        return self.vector_repo.search(query, top_k=10)

    def delete_document(self, document_id: str) -> bool:
        # 1. Get document to find the filename
        doc = self.doc_service.sql_repo.get_document(document_id)
        if not doc:
            return False
            
        # 2. Delete the physical file from the disk to prevent storage leaks
        file_path = os.path.join(self.doc_service.upload_dir, doc.name)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted physical file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not delete physical file {file_path}: {e}")

        # 3. Delete from Database (Cascades chunks and edges)
        success = self.doc_service.sql_repo.delete_document(document_id)
        if success:
            logger.info(f"Document {document_id} and its vector chunks deleted from DB.")
        return success




    # --- FIXED: Added Retry Logic to LLM Extraction Call ---
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _extract_triplets_with_retry(self, prompt: str, settings, gemini_client, openai_client) -> str:
        provider = settings.api_provider
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
        return res_text

    def _extract_and_save_graph(self, document_id: str, chunks: List[dict], settings):
        all_triplets = []
        decrypted_gemini = decrypt_key(settings.gemini_api_key)
        decrypted_openai = decrypt_key(settings.openai_api_key)

        gemini_client = genai.Client(api_key=decrypted_gemini) if decrypted_gemini else None
        openai_client = OpenAI(api_key=decrypted_openai) if decrypted_openai else None

        for chunk in chunks:
            prompt = (
                "Extract knowledge graph triplets from the following text. "
                "Identify key entities (people, places, concepts) and how they relate. "
                "Return strictly a valid JSON array of objects with keys: 'source', 'relation', 'target'. "
                "Do not use markdown blocks or include any other text.\n\n"
                f"Text:\n{chunk['text'][:2000]}" 
            )
            
            try:
                res_text = self._extract_triplets_with_retry(prompt, settings, gemini_client, openai_client)
                res_text = re.sub(r'```json\n|\n```|```', '', res_text).strip()
                triplets = json.loads(res_text)
                
                if isinstance(triplets, list):
                    all_triplets.extend(triplets)
                    
            except Exception as e:
                logger.warning(f"Failed to extract triplets for a chunk after retries: {e}")

        if all_triplets:
            self.doc_service.sql_repo.upsert_graph_edges(document_id, all_triplets)
            logger.info(f"Successfully saved {len(all_triplets)} graph edges for doc {document_id}")