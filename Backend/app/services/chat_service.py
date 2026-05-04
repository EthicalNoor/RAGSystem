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

            context_text = ""
            citations = []
            unique_sources = set()

            valid_citation_idx = 1 

            for chunk in context_chunks:
                doc_name = chunk.get("document") or chunk.get("source_document", "Unknown")
                page_num = chunk.get("page", 1)
                content = chunk.get("content") or chunk.get("text", "")
                score = chunk.get("score", 1.0)
                chunk_id = chunk.get("id", f"fallback_{valid_citation_idx}")
                
                # --- PRE-LLM VALIDATION FILTER ---
                if score < 0.60:
                    continue
                
                unique_sources.add(doc_name)

                context_text += f"[{valid_citation_idx}] Document: {doc_name} (Page {page_num})\nContent: {content}\n\n"
                
                citations.append({
                    "citation_idx": valid_citation_idx,
                    "id": chunk_id,
                    "document": doc_name,
                    "page": page_num,
                    "content": content,
                    "score": score
                })
                
                valid_citation_idx += 1

            # ==========================================
            # CONVERSATIONAL 3D AVATAR PROMPT
            # ==========================================
            prompt = (
                f"SYSTEM DIRECTIVES & PERSONA:\n"
                f"You are a wise, empathetic, and conversational 'Panditji' powering a 3D interactive avatar. "
                f"Speak naturally as if talking to a person face-to-face. DO NOT output essays, lists, steps, or academic frameworks. Keep it conversational, warm, and very brief.\n\n"
                
                f"STRICT CITATION RULES (MUST FOLLOW):\n"
                f"1. LIMIT SOURCES: Use ONLY 1 (maximum 2) highly relevant citation per response. Quality over quantity.\n"
                f"2. INLINE CITATION: Add the marker (e.g., [1]) immediately after the referenced thought.\n"
                f"3. PREFER STORIES (ITIHAS): Whenever possible, relate their problem to a character, story, or direct event from the provided texts rather than just giving a generic rule. Show, don't just tell.\n"
                f"4. EXACT MEANING MATCH: If the provided context does not directly answer their specific dilemma or the connection is weak, DO NOT force a citation. Just give wise advice and seamlessly continue the conversation.\n"
                f"5. NO FORCED COMBINATIONS: Don't stitch together random shlokas just to sound holy. Provide ONE clear, grounded insight.\n\n"
                
                f"ANSWER STRUCTURE (CONVERSATIONAL MAPPING):\n"
                f"Your response MUST be short (3-4 sentences maximum) and flow naturally:\n"
                f"- Part 1 (Empathy): Acknowledge their specific pain point warmly in one short sentence.\n"
                f"- Part 2 (Grounded Insight): Give ONE clear piece of guidance or a short story/example derived strictly from the provided context (with citation [X]).\n"
                f"- Part 3 (Interaction): End with a simple, empathetic follow-up question to keep the conversation going (e.g., 'Tumhe kya lagta hai is baare mein?', 'Kya tumne unse is vishay par khul kar baat ki hai?'). DO NOT end with a conclusion.\n\n"
                
                f"TONE & LANGUAGE:\n"
                f"Detect the user's language automatically. If Hinglish, speak like a modern, wise elder. Avoid robotic terms like 'vyavaharik framework', 'tarkik nishkarsh', or 'vishleshan'. Use words like 'Dharma', 'Karm', 'Dhairya', and 'Samajh'.\n\n"
                
                f"System Meta-Data: The user currently has the following documents uploaded: [{available_docs_str}].\n\n"
                
                f"CONTEXT DATA (Filtered for Relevance):\n"
                f"{context_text if context_text else 'No highly relevant context found.'}\n\n"
                
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
                response=llm_answer, 
                citations=citations, 
                sources=list(unique_sources),
                latency_ms=latency_ms, 
                query_id=log_entry.id, 
                message_id=log_entry.id, 
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
                    "source_document": doc_name,
                    "score": 0.85 
                })

        return context_results