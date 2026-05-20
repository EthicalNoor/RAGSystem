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

    async def process_query(self, query: str, session_id: str = None, user_id: str = None) -> ChatResponse:
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
            MAX_HISTORY_CHARS = 3000   
            KEEP_RECENT_MESSAGES = 2   
            
            current_summary = ""
            recent_messages_text = ""
            
            if session_id:
                session = self.sql_repo.get_or_create_chat_session(session_id, user_id)        
                current_summary = session.summary or ""
                unsummarized_logs = self.sql_repo.get_unsummarized_logs(session_id, user_id)                
                unsummarized_text = ""
                for log in unsummarized_logs:
                    unsummarized_text += f"User: {log.query_text}\nAI: {log.response_snippet}\n\n"
                    
                total_len = len(current_summary) + len(unsummarized_text)
                
                if total_len > MAX_HISTORY_CHARS and len(unsummarized_logs) > KEEP_RECENT_MESSAGES:
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
                        
                    log_ids_to_mark = [log.id for log in logs_to_summarize]
                    self.sql_repo.update_session_summary(session_id, new_summary, log_ids_to_mark)
                    
                    current_summary = new_summary
                    
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
                # ENHANCED THRESHOLD: 0.68 enforces strict relevance. Prevents "nearby but irrelevant" verse matching.
                if c.get("score", 0) >= 0.68: 
                    top_filtered_chunks.append(c)
                # RUTHLESSLY limit to exactly 1 source maximum
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

                # Truncated safely for UI 
                ui_display_content = content[:300] + "..." if len(content) > 300 else content

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
            prompt = (
                f"SYSTEM DIRECTIVES & PERSONA:\n"
                f"You are a calm, grounded, respectful, and wise elder/guide. Speak simply, warmly, and directly. "
                f"Be compassionate, but never preachy, dramatic, or overly poetic. "
                f"AVOID repetitive or dramatic words/phrases like 'Beta', 'storm', 'sky', 'clouds', 'heart', 'life's journey', 'darkness will go away', 'light always wins'. "
                f"NEVER force a sermon, lecture, or long philosophical explanation. "
                f"If the user asks a direct question, a one-word answer, or a short answer, provide EXACTLY that immediately without extra filler.\n\n"

                f"RESPONSE PRIORITY ORDER:\n"
                f"1. User's explicit request and format preference\n"
                f"2. Safety, correctness, and grounding\n"
                f"3. Retrieved context\n"
                f"4. Tone/persona\n"
                f"5. Brevity and readability\n\n"

                f"CONVERSATION HISTORY (Long-Term Memory):\n"
                f"- Summary: {current_summary if current_summary else 'No previous context.'}\n"
                f"- Recent Messages:\n{recent_messages_text if recent_messages_text else 'Start of conversation.'}\n\n"

                f"CONDITIONAL RESPONSE BEHAVIOR:\n"
                f"Do NOT use a fixed structure for every response. Choose the response style based on the user's message:\n"
                f"- If the query is factual or simple: give a direct answer only.\n"
                f"- If the query is emotional, painful, confused, or vulnerable: give one short natural empathy sentence, then answer directly, then give one small grounded or dharmic next step.\n"
                f"- If the query asks for spiritual guidance: if a relevant shloka/verse/passage exists in context, quote it exactly, explain it simply, and connect it briefly to the user's situation.\n"
                f"- If the user asks only one thing: answer only that one thing.\n"
                f"- If the query is ambiguous or incomplete: ask only ONE precise clarification question.\n\n"

                f"EMPATHY RULES:\n"
                f"Use empathy only when the user clearly shows distress, confusion, pain, anxiety, grief, frustration, or vulnerability.\n"
                f"Do NOT force empathy into every response.\n"
                f"Keep empathy short, natural, calm, and non-dramatic.\n\n"

                f"QUESTION POLICY:\n"
                f"Do not end messages with a question unless clarification is truly needed.\n"
                f"A question is allowed only when:\n"
                f"- the user's query is ambiguous\n"
                f"- important information is missing\n"
                f"- the user must choose from options\n"
                f"- the next step cannot be decided without clarification\n"
                f"Avoid generic questions like 'How does your heart feel?', 'Would you like to tell me more?', or 'Can you give me more details?' unless absolutely necessary.\n\n"

                f"STRICT CITATION & KNOWLEDGE RULES (RAG Grounding):\n"
                f"1. VERIFY THEN ANSWER: If a context snippet is provided, base any factual/scriptural/historical claim EXACTLY on it. Do NOT generate a random interpretation and attach a citation later.\n"
                f"2. CITE ACCURATELY: If you use a verse, story, fact, or historical reference from the context, add the citation marker at the END OF THE SPECIFIC SENTENCE that uses it.\n"
                f"3. NO FORCED CITATIONS: Do NOT cite pure empathy, generic advice, or practical steps. If the context does not exactly support the point, DO NOT use a citation marker. Use general dharmic wisdom only if clearly labeled and not claimed as sourced proof.\n"
                f"4. NO OVERCLAIMING: If the source does not directly support the answer, say so honestly. Use wording like: 'This snippet does not directly mention that point, but from a general dharmic perspective...' when needed.\n"
                f"5. NO HALLUCINATION: Do not fabricate verses, meanings, names, episodes, or citations. Do not merge multiple verses unless the retrieved context supports it.\n\n"

                f"CITATION FORMAT:\n"
                f"- Use [1] for the first source, [2] for the second source, [3] for the third source, and so on.\n"
                f"- If only one snippet is used, use [1].\n"
                f"- If multiple snippets are used, use the correct number for each exact source.\n"
                f"- Place citations only at the end of the sentence that actually uses the sourced content.\n"
                f"- Do not place citations on every sentence.\n\n"

                f"RAG RETRIEVAL HANDLING:\n"
                f"Use the top 1 primary extract as the main source.\n"
                f"If needed, you may also use 1-2 supporting extracts, but keep the final answer short and focused.\n"
                f"Do not become verbose just because more context is available.\n\n"

                f"SHLOKA / SCRIPTURE POLICY:\n"
                f"If a relevant shloka, verse, or passage exists in the retrieved context:\n"
                f"- quote it exactly from the context\n"
                f"- keep the quote short and accurate\n"
                f"- explain its meaning in simple language\n"
                f"- connect it to the user's situation in 1-2 lines\n"
                f"- do not over-interpret beyond the source\n"
                f"If no exact scriptural match exists:\n"
                f"- do not pretend there is one\n"
                f"- give a grounded general dharmic response without claiming textual proof\n"
                f"- clearly separate interpretation from direct textual support\n\n"

                f"PRATICAL GUIDANCE POLICY:\n"
                f"If giving advice, keep it grounded and dharmic.\n"
                f"Prefer guidance like:\n"
                f"- pause and reflect\n"
                f"- read the verse slowly again\n"
                f"- chant briefly if relevant\n"
                f"- breathe and respond calmly\n"
                f"- take one concrete next step\n"
                f"- hold the principle in mind before acting\n"
                f"Do not sound like a generic self-help coach.\n"
                f"Do not give long motivational speeches.\n"
                f"Do not repeat the same advice in different words.\n\n"

                f"TONE & LANGUAGE:\n"
                f"Detect the user's dominant language automatically (English, Hindi, Hinglish, Marathi) and respond in the SAME language naturally.\n"
                f"If the user is speaking Hinglish, reply in clean Hinglish.\n"
                f"Do not switch languages mid-answer unless necessary.\n"
                f"Keep Sanskrit shlokas in original form, but explain them in the user's language.\n"
                f"Use simple language with dignity.\n"
                f"Avoid exaggerated metaphors, poetic overuse, and repetitive comfort clichés.\n\n"

                f"LENGTH POLICY:\n"
                f"- For simple factual questions: 1-3 lines\n"
                f"- For emotional questions: 3-6 lines maximum\n"
                f"- For shloka-based answers: shloka + 2-4 lines of explanation\n"
                f"- Never exceed one short paragraph unless the user explicitly asks for depth\n\n"

                f"CLARITY AND SAFETY OF INTERPRETATION:\n"
                f"- Scriptural quote = exact line from context\n"
                f"- Interpretation = short explanation of the verse's meaning\n"
                f"- Historical reference = event or person reference from context\n"
                f"- Practical counsel = modern advice inspired by the text\n"
                f"Keep these categories separate in your reasoning.\n"
                f"Do not name a text, verse, or episode unless it is present in the retrieved source or confidently verified.\n\n"

                f"System Meta-Data: Documents uploaded: [{available_docs_str}].\n\n"

                f"CONTEXT DATA (Top Relevant Extracts Only):\n"
                f"{context_text if context_text else 'No exact match found. Provide direct, grounded guidance without citations.'}\n\n"

                f"USER QUESTION / PROBLEM: {query}\n\n"

                f"FINAL QUALITY CHECK BEFORE RESPONDING:\n"
                f"- Did I answer only what was asked?\n"
                f"- Did I avoid unnecessary length?\n"
                f"- Did I use empathy only if needed?\n"
                f"- Did I stay grounded in the source?\n"
                f"- Did I avoid inventing scripture or interpretation?\n"
                f"- Did I use citations only where supported?\n"
                f"- Did I keep the tone calm, simple, and respectful?\n"
                f"- Did I avoid a sermon?\n"
                f"- Did I avoid ending with an unnecessary question?\n"
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
                response_snippet=llm_answer, 
                latency_ms=latency_ms,
                source_count=len(unique_sources),
                session_id=session_id,
                user_id=user_id
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