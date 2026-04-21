import time
from app.services.rag_service import RAGService
from app.repositories.sql_repo import SQLRepository
from app.config import Config, get_logger

from google import genai
from google.genai import types
from openai import OpenAI
from app.schemas import ChatResponse

logger = get_logger(__name__)

class ChatService:
    def __init__(self, rag_svc: RAGService, sql_repo: SQLRepository, config: Config):
        self.rag_svc = rag_svc
        self.sql_repo = sql_repo
        self.config = config
        
        # Initialize clients conditionally based on available keys using new SDKs
        self.gemini_client = genai.Client(api_key=self.config.gemini_api_key) if self.config.gemini_api_key else None
        self.openai_client = OpenAI(api_key=self.config.openai_api_key) if self.config.openai_api_key else None

    async def process_query(self, query: str) -> ChatResponse:
        start_time = time.time()
        
        try:
            # 1. Retrieve Context from VectorDB
            context_chunks = self.rag_svc.search_context(query)
            sources = [chunk.get("source_document", "Unknown") for chunk in context_chunks]
            unique_sources = list(set(sources))

            # 2. Build the System Prompt
            context_text = "\n\n".join([f"Source: {c.get('source_document')}\nContent: {c.get('text')}" for c in context_chunks])
            prompt = f"Use the following knowledge base context to answer the user's question clearly.\n\nContext:\n{context_text}\n\nQuestion: {query}"

            # 3. Call the Selected Provider
            provider = self.config.api_provider
            
            if provider == "gemini":
                if not self.gemini_client:
                    raise ValueError("Gemini API key is missing or invalid.")
                
                # Directly use the confirmed working model, avoiding failed model loops
                llm_model = self.config.llm_model
                if not llm_model or "pro" in llm_model.lower() or "gpt" in llm_model.lower():
                    llm_model = "gemini-2.5-flash"
                else:
                    llm_model = llm_model.replace("models/", "")

                logger.info(f"Generating LLM response using {provider} ({llm_model})")
                
                response = self.gemini_client.models.generate_content(
                    model=llm_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.config.temperature,
                    )
                )
                llm_answer = response.text
                
            elif provider == "openai":
                if not self.openai_client:
                    raise ValueError("OpenAI API key is missing or invalid.")
                
                llm_model = self.config.llm_model
                if not llm_model or "gemini" in llm_model.lower():
                    llm_model = "gpt-4o"

                logger.info(f"Generating LLM response using {provider} ({llm_model})")
                
                response = self.openai_client.chat.completions.create(
                    model=llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config.temperature
                )
                llm_answer = response.choices[0].message.content
            else:
                raise ValueError(f"Unsupported API provider: {provider}")

            latency_ms = int((time.time() - start_time) * 1000)

            # 4. Log the query result
            log_entry = self.sql_repo.create_query_log(
                query_text=query,
                response_snippet=llm_answer[:100] + "...",
                latency_ms=latency_ms,
                source_count=len(unique_sources)
            )

            return ChatResponse(
                response=llm_answer,
                sources=unique_sources,
                latency_ms=latency_ms,
                query_id=log_entry.id,
                status="Success"
            )

        except Exception as e:
            logger.error(f"Error processing chat query: {str(e)}")
            self.sql_repo.create_query_log(
                query_text=query, response_snippet=f"Failed: {str(e)[:100]}", 
                latency_ms=int((time.time() - start_time) * 1000), 
                source_count=0, status="Failed"
            )
            raise e