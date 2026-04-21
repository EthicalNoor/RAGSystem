from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import DocumentChunkModel
from app.config import get_logger, get_config

from google import genai
from openai import OpenAI

logger = get_logger(__name__)

class VectorRepository:
    def __init__(self, db: Session):
        self.db = db
        self.config = get_config()
        
        # Initialize clients conditionally based on available keys using new SDKs
        self.gemini_client = genai.Client(api_key=self.config.gemini_api_key) if self.config.gemini_api_key else None
        self.openai_client = OpenAI(api_key=self.config.openai_api_key) if self.config.openai_api_key else None

    def _generate_embedding(self, text_input: str) -> List[float]:
        provider = self.config.api_provider
        
        try:
            if provider == "gemini":
                if not self.gemini_client:
                    raise ValueError("Gemini API key is missing or invalid.")
                
                model = self.config.embedding_model or ""
                model = model.replace("models/", "")
                
                # Prevent sending OpenAI model names to Gemini
                if "text-embedding-3" in model:
                    model = "text-embedding-004"
                
                try:
                    result = self.gemini_client.models.embed_content(
                        model=model,
                        contents=text_input
                    )
                except Exception as e:
                    # FIX: Dynamic Discovery Fallback
                    # If the requested model throws a 404, dynamically find a supported one.
                    logger.warning(f"Embedding model '{model}' failed. Dynamically finding a supported Gemini embedding model...")
                    
                    fallback_model = None
                    try:
                        for m_info in self.gemini_client.models.list():
                            methods = getattr(m_info, 'supported_actions', getattr(m_info, 'supported_generation_methods', []))
                            if methods and "embedContent" in methods:
                                fallback_model = m_info.name.replace("models/", "")
                                break
                    except Exception as list_err:
                        logger.error(f"Failed to dynamically list models: {list_err}")

                    if fallback_model:
                        logger.info(f"Dynamically selected authorized embedding model: {fallback_model}")
                        result = self.gemini_client.models.embed_content(
                            model=fallback_model,
                            contents=text_input
                        )
                    else:
                        raise ValueError("No supported embedding models found for this Gemini API key.") from e
                    
                vec = result.embeddings[0].values
                
            elif provider == "openai":
                if not self.openai_client:
                    raise ValueError("OpenAI API key is missing or invalid.")
                
                model = self.config.embedding_model
                if not model or "text-embedding-004" in model or "gemini" in model:
                    model = "text-embedding-3-small"

                response = self.openai_client.embeddings.create(input=[text_input], model=model)
                vec = response.data[0].embedding
            else:
                raise ValueError(f"Unsupported API provider: {provider}")
                
        except Exception as e:
            logger.error(f"Embedding generation failed for provider {provider}: {e}")
            raise e

        # Database safety: Normalize dimension length to 1536 so pgvector doesn't crash
        dim = len(vec)
        if dim < 1536:
            vec.extend([0.0] * (1536 - dim))
        elif dim > 1536:
            vec = vec[:1536]
            
        return vec

    def upsert_chunks(self, document_id: str, chunks: List[Dict[str, Any]]):
        logger.info(f"Inserting {len(chunks)} chunks into pgvector via {self.config.api_provider} for doc {document_id}")
        
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

    def search(self, query: str, top_k: int = 3) -> List[dict]:
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