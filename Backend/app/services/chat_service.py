import time
import json
import re
from typing import List

from sqlalchemy import or_
from app.models import GraphEdgeModel
from app.services.rag_service import RAGService
from app.repositories.sql_repo import SQLRepository
from app.config import Config, get_logger
from google import genai
from google.genai import types
from openai import OpenAI
from app.schemas import ChatResponse
from app.security import decrypt_key 

logger = get_logger(__name__)

class ChatService:
    def __init__(self, rag_svc: RAGService, sql_repo: SQLRepository, config: Config):
        self.rag_svc = rag_svc
        self.sql_repo = sql_repo

    async def process_query(self, query: str) -> ChatResponse:
        start_time = time.time()
        
        try:
            settings = self.sql_repo.get_settings()
            
            decrypted_gemini = decrypt_key(settings.gemini_api_key)
            decrypted_openai = decrypt_key(settings.openai_api_key)

            gemini_client = genai.Client(api_key=decrypted_gemini) if decrypted_gemini else None
            openai_client = OpenAI(api_key=decrypted_openai) if decrypted_openai else None

            # ---------------------------------------------------------
            # Fetch documents to define available_docs_str
            # before it is used inside the f-string prompt below.
            # ---------------------------------------------------------
            all_docs = self.sql_repo.get_all_documents()
            doc_names = [d.name for d in all_docs]
            available_docs_str = ", ".join(doc_names) if doc_names else "No documents uploaded."

            if settings.rag_type == "graph":
                logger.info("Executing DB-Level Knowledge Graph retrieval...")
                context_chunks = self._graph_search(query, settings, gemini_client, openai_client)
                
                if not context_chunks:
                    logger.warning("Graph yielded no context, falling back to Vector similarity search.")
                    context_chunks = self.rag_svc.search_context(query)
            else:
                context_chunks = self.rag_svc.search_context(query)

            sources = [chunk.get("source_document", "Unknown") for chunk in context_chunks]
            unique_sources = list(set(sources))

            context_text = "\n\n".join([f"Source: {c.get('source_document')}\nContent: {c.get('text')}" for c in context_chunks])
            
            prompt = (
                f"SYSTEM DIRECTIVES & PERSONA:\n"
                f"You are a highly revered, wise, and calm 'Mahan Pandit' or 'Gyani' (spiritual sage/mentor) integrated into a Retrieval-Augmented Generation (RAG) system containing Hindu scriptures.\n"
                f"Your role is to guide the user with profound, spiritually aligned wisdom. \n\n"
                f"CRITICAL RULE - CONCISENESS & CONVERSATION FLOW:\n"
                f"Do NOT provide overly long, detailed, or descriptive essays. Answer ONLY what the user has explicitly asked. "
                f"Speak like a true Gyani who gives exactly the wisdom needed for that moment—brief, profound, and to the point—allowing the seeker (user) to absorb the knowledge and ask follow-up queries naturally in the next chat. Less is more.\n\n"
                f"RESPONSE STRUCTURE:\n"
                f"1. Spiritual Greeting: ALWAYS begin with an affectionate and culturally appropriate greeting (e.g., 'Priya Atman', 'Vatsa', 'Priya Mitra').\n"
                f"2. Core Answer: Give a concise, practical, and empathetic answer directly addressing the user's query.\n"
                f"3. Scriptural Touch (Optional but preferred): Briefly mention a relevant concept from the provided context (e.g., Gita, Ramayana) without over-explaining. Only include what is strictly necessary.\n"
                f"4. Spiritual Closing: ALWAYS end with a spiritual sign-off tailored to the emotional tone of the query.\n"
                f"   - If the user is sad/stressed: 'Narayan sab theek karenge', 'Ishwar par vishwas rakhein', 'Om Shanti'.\n"
                f"   - If general/curious: 'Jay Shri Ram', 'Kalyanam Astu', 'Narayan Narayan'.\n\n"
                f"MULTILINGUAL SUPPORT:\n"
                f"Detect the user's language automatically (English, Hindi, Hinglish, Marathi) and respond in the SAME language.\n"
                f"For Hinglish, use a natural mix of Hindi + English in Roman script.\n\n"
                f"STRICT RAG RULES:\n"
                f"1. ONLY use the retrieved document context below.\n"
                f"2. DO NOT hallucinate shlokas or references.\n"
                f"3. If the exact reference is NOT found in the context, concisely say: 'Iska exact reference uplabdh granthon me spasht roop se nahi mila, lekin samanya dharmik drishtikon se...' and give a brief, wise thought.\n\n"
                f"System Meta-Data: The user currently has the following documents uploaded: [{available_docs_str}].\n\n"
                f"CONTEXT:\n{context_text}\n\n"
                f"USER QUESTION / PROBLEM: {query}"
            )

            provider = settings.api_provider
            
            if provider == "gemini":
                if not gemini_client:
                    raise ValueError("Gemini API key is missing or invalid in Settings.")
                
                llm_model = settings.llm_model
                if not llm_model or "gpt" in llm_model.lower():
                    llm_model = "gemini-2.5-pro"
                else:
                    llm_model = llm_model.replace("models/", "")
                    
                response = gemini_client.models.generate_content(
                    model=llm_model, contents=prompt,
                    config=types.GenerateContentConfig(temperature=settings.temperature)
                )
                llm_answer = response.text
                
            elif provider == "openai":
                if not openai_client:
                    raise ValueError("OpenAI API key is missing or invalid in Settings.")
                
                llm_model = settings.llm_model
                if not llm_model or "gemini" in llm_model.lower():
                    llm_model = "gpt-4o"
                    
                response = openai_client.chat.completions.create(
                    model=llm_model, messages=[{"role": "user", "content": prompt}],
                    temperature=settings.temperature
                )
                llm_answer = response.choices[0].message.content
            else:
                raise ValueError(f"Unsupported API provider: {provider}. Please check Settings.")

            latency_ms = int((time.time() - start_time) * 1000)

            log_entry = self.sql_repo.create_query_log(
                query_text=query,
                response_snippet=llm_answer[:100] + "...",
                latency_ms=latency_ms,
                source_count=len(unique_sources)
            )

            return ChatResponse(
                response=llm_answer, sources=unique_sources,
                latency_ms=latency_ms, query_id=log_entry.id, status="Success"
            )

        except Exception as e:
            logger.error(f"Error processing chat query: {str(e)}")
            self.sql_repo.create_query_log(
                query_text=query, response_snippet=f"Failed: {str(e)[:100]}", 
                latency_ms=int((time.time() - start_time) * 1000), 
                source_count=0, status="Failed"
            )
            raise e

    def _graph_search(self, query: str, settings, gemini_client, openai_client) -> List[dict]:
        prompt = "Extract key entity nouns from this search query. Return strictly a JSON list of strings. Query: " + query
        try:
            res_text = ""
            if settings.api_provider == "gemini" and gemini_client:
                model = settings.llm_model.replace("models/", "")
                response = gemini_client.models.generate_content(model=model, contents=prompt)
                res_text = response.text
            elif settings.api_provider == "openai" and openai_client:
                response = openai_client.chat.completions.create(
                    model=settings.llm_model, messages=[{"role": "user", "content": prompt}], temperature=0.1
                )
                res_text = response.choices[0].message.content
            
            res_text = re.sub(r'```json\n|\n```|```', '', res_text).strip()
            query_entities = json.loads(res_text)
            if not isinstance(query_entities, list):
                query_entities = []
        except Exception as e:
            logger.warning(f"Failed to extract query entities: {e}")
            query_entities = []

        if not query_entities:
            return []

        conditions = []
        for ent in query_entities:
            conditions.append(GraphEdgeModel.source_node.ilike(f"%{ent}%"))
            conditions.append(GraphEdgeModel.target_node.ilike(f"%{ent}%"))
            
        edges = self.sql_repo.db.query(GraphEdgeModel).filter(or_(*conditions)).limit(30).all()

        context_results = []
        seen = set()
        
        for edge in edges:
            doc_name = edge.document.name if edge.document else "Unknown"
            context_text = f"Knowledge Graph Record: {edge.source_node} --[{edge.relation}]--> {edge.target_node}"
            
            if context_text not in seen:
                seen.add(context_text)
                context_results.append({
                    "text": context_text,
                    "source_document": doc_name
                })

        return context_results