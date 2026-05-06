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

    async def process_query(self, query: str, session_id: str = None) -> ChatResponse:
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

            # ==========================================
            # 1. CONVERSATION MEMORY & RECURSIVE SUMMARIZATION
            # ==========================================
            # Explanation: How Chat History is Stored
            # All messages are saved in QueryLogModel with a shared session_id.
            # A separate ChatSessionModel stores the rolling summary.
            
            MAX_HISTORY_CHARS = 3000   # Token limit threshold
            KEEP_RECENT_MESSAGES = 2   # Keep last N turns unsummarized for exact context
            
            current_summary = ""
            recent_messages_text = ""
            
            if session_id:
                session = self.sql_repo.get_or_create_chat_session(session_id)
                current_summary = session.summary or ""
                unsummarized_logs = self.sql_repo.get_unsummarized_logs(session_id)
                
                unsummarized_text = ""
                for log in unsummarized_logs:
                    unsummarized_text += f"User: {log.query_text}\nAI: {log.response_snippet}\n\n"
                    
                total_len = len(current_summary) + len(unsummarized_text)
                
                # Explanation: How Summarization is Triggered
                # Triggered only when the uncompressed history breaches the MAX_HISTORY_CHARS limit.
                if total_len > MAX_HISTORY_CHARS and len(unsummarized_logs) > KEEP_RECENT_MESSAGES:
                    
                    # Explanation: How Recursive Summarization Works
                    # We take the existing summary, append the older raw messages, and ask the LLM
                    # to generate a single compressed block. The very recent messages are spared.
                    logs_to_summarize = unsummarized_logs[:-KEEP_RECENT_MESSAGES]
                    logs_to_keep = unsummarized_logs[-KEEP_RECENT_MESSAGES:]
                    
                    text_to_summarize = ""
                    for log in logs_to_summarize:
                        text_to_summarize += f"User: {log.query_text}\nAI: {log.response_snippet}\n\n"
                        
                    summarize_prompt = (
                        "You are an AI tasked with maintaining a rolling memory for a conversation. "
                        "Combine the EXISTING SUMMARY with the NEW MESSAGES into a concise, updated summary. "
                        "Preserve important facts, user emotions, decisions, and context. Do NOT lose key information.\n\n"
                        f"EXISTING SUMMARY:\n{current_summary if current_summary else 'None'}\n\n"
                        f"NEW MESSAGES TO SUMMARIZE:\n{text_to_summarize}\n\n"
                        "NEW UPDATED SUMMARY:"
                    )
                    
                    # Trigger LLM for summarization
                    if settings.api_provider == "gemini":
                        summ_resp = gemini_client.models.generate_content(
                            model=settings.llm_model.replace("models/", "") if "gemini" in settings.llm_model else "gemini-2.5-pro", 
                            contents=summarize_prompt, config=types.GenerateContentConfig(temperature=0.3)
                        )
                        new_summary = summ_resp.text
                    else:
                        summ_resp = openai_client.chat.completions.create(
                            model=settings.llm_model if "gpt" in settings.llm_model else "gpt-4o", 
                            messages=[{"role": "user", "content": summarize_prompt}], temperature=0.3
                        )
                        new_summary = summ_resp.choices[0].message.content
                        
                    # Save new summary and mark processed logs as summarized
                    log_ids_to_mark = [log.id for log in logs_to_summarize]
                    self.sql_repo.update_session_summary(session_id, new_summary, log_ids_to_mark)
                    
                    current_summary = new_summary
                    
                    # Rebuild recent messages context block with what we spared
                    for log in logs_to_keep:
                        recent_messages_text += f"User: {log.query_text}\nAI: {log.response_snippet}\n\n"
                else:
                    recent_messages_text = unsummarized_text


            # ==========================================
            # 2. RAG RETRIEVAL (Vector / Graph Search)
            # ==========================================
            if settings.rag_type == "graph":
                logger.info("Executing DB-Level Knowledge Graph retrieval...")
                context_chunks = self._graph_search(query, settings, gemini_client, openai_client)
                
                if not context_chunks:
                    logger.warning("Graph yielded no context, falling back to Vector similarity search.")
                    context_chunks = self.rag_svc.search_context(query)
            else:
                context_chunks = self.rag_svc.search_context(query)

            # ---------------------------------------------------------
            # STRICT FILTERING & SORTING (The "Top 1" Absolute Rule)
            # ---------------------------------------------------------
            context_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            top_filtered_chunks = []
            for c in context_chunks:
                # SWEET SPOT: 0.65 allows abstract philosophical matches, but still blocks complete garbage.
                if c.get("score", 0) >= 0.65: 
                    top_filtered_chunks.append(c)
                # RUTHLESSLY limit to exactly 1 source maximum to prevent citation overload
                if len(top_filtered_chunks) >= 1:
                    break

            context_text = ""
            citations = []
            unique_sources = set()
            valid_citation_idx = 1 

            for chunk in top_filtered_chunks:
                doc_name = chunk.get("document") or chunk.get("source_document", "Unknown")
                page_num = chunk.get("page", 1)
                content = chunk.get("content") or chunk.get("text", "")
                score = chunk.get("score", 1.0)
                chunk_id = chunk.get("id", f"fallback_{valid_citation_idx}")
                
                unique_sources.add(doc_name)

                # Truncate content for the UI drastically so it's a small anchor, not a book page
                ui_display_content = content[:200] + "..." if len(content) > 200 else content

                # Format text for LLM injection
                context_text += f"[{valid_citation_idx}] Document: {doc_name} (Page {page_num})\nContent: {content}\n\n"
                
                citations.append({
                    "citation_idx": valid_citation_idx,
                    "id": chunk_id,
                    "document": doc_name,
                    "page": page_num,
                    "content": ui_display_content,
                    "score": score
                })
                
                valid_citation_idx += 1

            # ==========================================
            # 3. PROMPT CONSTRUCTION (Context + Memory)
            # ==========================================
            # Explanation: How Prompt is Constructed
            # We explicitly inject the rolling summary and recent raw messages so the AI remembers context.
            prompt = (
                f"SYSTEM DIRECTIVES & PERSONA:\n"
                f"You are a wise, empathetic, and highly conversational 'Panditji' powering a 3D interactive voice avatar. "
                f"Speak naturally, emotionally, and briefly, as if talking to a person face-to-face. "
                f"NEVER use lists, steps, academic frameworks, or formal analysis. Be a warm guide.\n\n"
                
                f"CONVERSATION HISTORY (Long-Term Memory):\n"
                f"- Summary of Past Discussion: {current_summary if current_summary else 'No previous context.'}\n"
                f"- Recent Messages:\n{recent_messages_text if recent_messages_text else 'This is the start of the conversation.'}\n\n"
                
                f"STRICT CITATION & KNOWLEDGE RULES:\n"
                f"1. ONE ANCHOR CITATION ONLY: If the provided context contains a highly relevant story, character (Itihas), or exact principle, use it and add the [1] marker at the end of that sentence.\n"
                f"2. DO NOT FORCE CITATIONS: If the context is generic or a weak match, DO NOT cite it. Rely on your base wisdom instead. Say 'Citation not found' internally by just not placing any [X] marker.\n"
                f"3. SHORT & DIRECT: Deliver ONE core insight. Do not explain multiple viewpoints.\n\n"
                
                f"CONVERSATIONAL STRUCTURE (CRITICAL):\n"
                f"Your response MUST be maximum 3 to 4 sentences in total.\n"
                f"- Part 1: Emotional Validation (Acknowledge their pain/dilemma warmly in one sentence).\n"
                f"- Part 2: Core Insight (One brief piece of guidance or a short relevant story from the context, marked with [1] if used).\n"
                f"- Part 3: Interactive Hook (End with a short, empathetic question to invite them to speak again, e.g., 'Tumhara man is baare mein kya kehta hai?').\n\n"
                
                f"TONE & LANGUAGE:\n"
                f"Detect the user's language automatically (English, Hindi, Hinglish, Marathi) and respond in the SAME language seamlessly.\n\n"
                
                f"System Meta-Data: Documents uploaded: [{available_docs_str}].\n\n"
                
                f"CONTEXT DATA (Top 1 Most Relevant Extract Only):\n"
                f"{context_text if context_text else 'No exact match found. Provide un-cited general wisdom.'}\n\n"
                
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

            # --- SAVING RESPONSE FOR NEXT TURN ---
            # Save the FULL llm_answer so it can be summarized efficiently in the next loop.
            log_entry = self.sql_repo.create_query_log(
                query_text=query,
                response_snippet=llm_answer, 
                latency_ms=latency_ms,
                source_count=len(unique_sources),
                session_id=session_id
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