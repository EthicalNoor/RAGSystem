from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import DocumentChunkModel, SystemSettingsModel
from app.config import get_logger

from google import genai
from openai import OpenAI

logger = get_logger(__name__)

class VectorRepository:
    def __init__(self, db: Session):
        self.db = db

    def _get_settings(self) -> SystemSettingsModel:
        settings = self.db.query(SystemSettingsModel).filter_by(id="default").first()
        if not settings:
            raise ValueError("System settings not found in database. Please check settings.")
        return settings

    def _generate_embedding(self, text_input: str) -> List[float]:
        settings = self._get_settings()
        provider = settings.api_provider
        
        try:
            if provider == "gemini":
                if not settings.gemini_api_key:
                    raise ValueError("Gemini API key is missing in Database settings.")
                
                gemini_client = genai.Client(api_key=settings.gemini_api_key)
                model = settings.embedding_model or ""
                model = model.replace("models/", "")
                
                if "text-embedding-3" in model:
                    model = "text-embedding-004"
                
                try:
                    result = gemini_client.models.embed_content(
                        model=model,
                        contents=text_input
                    )
                except Exception as e:
                    logger.warning(f"Embedding model '{model}' failed. Dynamically finding a supported Gemini embedding model...")
                    
                    fallback_model = None
                    try:
                        for m_info in gemini_client.models.list():
                            methods = getattr(m_info, 'supported_actions', getattr(m_info, 'supported_generation_methods', []))
                            if methods and "embedContent" in methods:
                                fallback_model = m_info.name.replace("models/", "")
                                break
                    except Exception as list_err:
                        logger.error(f"Failed to dynamically list models: {list_err}")

                    if fallback_model:
                        logger.info(f"Dynamically selected embedding model: {fallback_model}. Saving to database.")
                        
                        settings.embedding_model = fallback_model
                        self.db.commit()
                        
                        result = gemini_client.models.embed_content(
                            model=fallback_model,
                            contents=text_input
                        )
                    else:
                        raise ValueError("No supported embedding models found for this Gemini API key.") from e
                    
                vec = result.embeddings[0].values
                
            elif provider == "openai":
                if not settings.openai_api_key:
                    raise ValueError("OpenAI API key is missing in Database settings.")
                
                openai_client = OpenAI(api_key=settings.openai_api_key)
                model = settings.embedding_model
                if not model or "text-embedding-004" in model or "gemini" in model:
                    model = "text-embedding-3-small"

                response = openai_client.embeddings.create(input=[text_input], model=model)
                vec = response.data[0].embedding
            else:
                raise ValueError(f"Unsupported API provider: {provider}")
                
        except Exception as e:
            logger.error(f"Embedding generation failed for provider {provider}: {e}")
            raise e

        dim = len(vec)
        if dim < 1536:
            vec.extend([0.0] * (1536 - dim))
        elif dim > 1536:
            vec = vec[:1536]
            
        return vec

    def upsert_chunks(self, document_id: str, chunks: List[Dict[str, Any]]):
        logger.info(f"Inserting {len(chunks)} chunks into pgvector for doc {document_id}")
        
        db_chunks = []
        for chunk in chunks:
            vector = self._generate_embedding(chunk["text"])
            
            db_chunk = DocumentChunkModel(
                document_id=document_id,
                text_content=chunk["text"],
                embedding=vector
            )
            db_chunks.append(db_chunk)
            
        self.db.add_all(db_chunks)
        self.db.commit()

    def search(self, query: str, top_k: int = 10) -> List[dict]:
        logger.info(f"Executing pgvector search for query: {query}")
        
        query_vector = self._generate_embedding(query)
        
        results = (
            self.db.query(DocumentChunkModel)
            .order_by(DocumentChunkModel.embedding.cosine_distance(query_vector))
            .limit(top_k)
            .all()
        )
        
        return [
            {
                "text": r.text_content, 
                "source_document": r.document.name if r.document else "Unknown"
            } for r in results
        ]

    def ping(self) -> bool:
        try:
            self.db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_stats(self) -> dict:
        total_chunks = self.db.query(DocumentChunkModel).count()
        storage_used_mb = (total_chunks * 6.5) / 1024 
        return {
            "total_embeddings": total_chunks,
            "storage_used_mb": storage_used_mb
        }