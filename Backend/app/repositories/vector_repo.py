import time
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import DocumentChunkModel
from app.config import get_logger
from app.repositories.sql_repo import SQLRepository
from app.security import decrypt_key

from google import genai
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = get_logger(__name__)


class VectorRepository:
    def __init__(self, db: Session):
        self.db = db
        self.sql_repo = SQLRepository(db)
        self.settings = self.sql_repo.get_settings()

        decrypted_gemini = decrypt_key(self.settings.gemini_api_key)
        decrypted_openai = decrypt_key(self.settings.openai_api_key)

        self.gemini_client = (
            genai.Client(api_key=decrypted_gemini) if decrypted_gemini else None
        )
        self.openai_client = (
            OpenAI(api_key=decrypted_openai) if decrypted_openai else None
        )

        del decrypted_gemini
        del decrypted_openai

    @retry(
        stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _generate_embedding_with_retry(self, text_input: str) -> List[float]:
        return self._generate_embedding(text_input)

    def _generate_embedding(self, text_input: str) -> List[float]:
        provider = self.settings.api_provider

        try:
            if provider == "gemini":
                if not self.gemini_client:
                    raise ValueError("Gemini API key is missing or invalid.")

                model = self.settings.embedding_model or "text-embedding-004"
                model = model.replace("models/", "")
                if "text-embedding-3" in model:
                    model = "text-embedding-004"

                try:
                    result = self.gemini_client.models.embed_content(
                        model=model, contents=text_input
                    )
                except Exception as e:
                    fallback_model = None
                    for m_info in self.gemini_client.models.list():
                        methods = getattr(
                            m_info,
                            "supported_actions",
                            getattr(m_info, "supported_generation_methods", []),
                        )
                        if methods and "embedContent" in methods:
                            fallback_model = m_info.name.replace("models/", "")
                            break

                    if fallback_model:
                        self.sql_repo.update_settings(
                            {"embedding_model": fallback_model}
                        )
                        result = self.gemini_client.models.embed_content(
                            model=fallback_model, contents=text_input
                        )
                    else:
                        raise ValueError(
                            "No supported embedding models found for this Gemini API key."
                        ) from e

                vec = result.embeddings[0].values

            elif provider == "openai":
                if not self.openai_client:
                    raise ValueError("OpenAI API key is missing or invalid.")

                model = self.settings.embedding_model
                if not model or "text-embedding-004" in model or "gemini" in model:
                    model = "text-embedding-3-small"

                response = self.openai_client.embeddings.create(
                    input=[text_input], model=model
                )
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
        logger.info(
            f"Inserting {len(chunks)} chunks into pgvector via {self.settings.api_provider} for doc {document_id}"
        )

        db_chunks = []
        batch_size = 50

        for i, chunk in enumerate(chunks):
            try:
                vector = self._generate_embedding_with_retry(chunk["text"])

                db_chunk = DocumentChunkModel(
                    document_id=document_id,
                    text_content=chunk["text"],
                    embedding=vector,
                )
                db_chunks.append(db_chunk)

                if len(db_chunks) >= batch_size:
                    self.db.add_all(db_chunks)
                    self.db.commit()
                    logger.info(
                        f"Successfully committed batch of {batch_size} chunks. ({i+1}/{len(chunks)})"
                    )
                    db_chunks = []

            except Exception as e:
                logger.error(
                    f"Critical failure on chunk {i+1} after multiple retries: {e}"
                )
                raise e

        if db_chunks:
            self.db.add_all(db_chunks)
            self.db.commit()
            logger.info(
                f"Successfully committed final batch of {len(db_chunks)} chunks."
            )

    def search(self, query: str, top_k: int = None) -> List[dict]:
        limit = top_k if top_k is not None else self.settings.top_k
        query_vector = self._generate_embedding_with_retry(query)

        # Calculate distance as a labeled column
        distance = DocumentChunkModel.embedding.cosine_distance(query_vector).label(
            "distance"
        )

        results = (
            self.db.query(DocumentChunkModel, distance)
            .order_by(distance)
            .limit(limit)
            .all()
        )

        citations = []
        for r, dist in results:
            citations.append(
                {
                    "id": r.id,  # Unique Chunk ID
                    "document": r.document.name if r.document else "Unknown",
                    "page": r.page_number or 1,
                    "content": r.text_content,
                    "score": round(
                        1.0 - float(dist), 4
                    ),  # Convert distance to similarity score
                }
            )
        return citations

    def ping(self) -> bool:
        try:
            self.db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_stats(self) -> dict:
        total_chunks = self.db.query(DocumentChunkModel).count()
        storage_used_mb = (total_chunks * 6.5) / 1024
        return {"total_embeddings": total_chunks, "storage_used_mb": storage_used_mb}
