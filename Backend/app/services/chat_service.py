import time
import json
import re
import networkx as nx
from typing import List

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

    async def process_query(self, query: str) -> ChatResponse:
        start_time = time.time()
        
        try:
            # Strictly fetch Database Settings
            settings = self.sql_repo.get_settings()
            gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
            openai_client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

            all_docs = self.sql_repo.get_all_documents()
            doc_names = [d.name for d in all_docs]
            available_docs_str = ", ".join(doc_names) if doc_names else "No documents uploaded."

            # 1. Check DB Settings to determine Retrieval Strategy
            if settings.rag_type == "graph":
                logger.info("Executing Knowledge Graph retrieval...")
                context_chunks = self._graph_search(query, settings, gemini_client, openai_client)
                
                # Fail-safe: If the graph yields no connections, fall back to vector search
                if not context_chunks:
                    logger.warning("Graph yielded no context, falling back to Vector similarity search.")
                    context_chunks = self.rag_svc.search_context(query)
            else:
                # Standard Vector Similarity Search
                context_chunks = self.rag_svc.search_context(query)

            # 2. Build Context Window
            sources = [chunk.get("source_document", "Unknown") for chunk in context_chunks]
            unique_sources = list(set(sources))

            context_text = "\n\n".join([f"Source: {c.get('source_document')}\nContent: {c.get('text')}" for c in context_chunks])
            
            prompt = (
                f"System Meta-Data: The user currently has the following documents uploaded in their knowledge base: [{available_docs_str}]. "
                f"If the user asks to list available documents or document names, use this list to answer.\n\n"
                f"Use the following knowledge base context to answer the user's question clearly.\n\n"
                f"Context:\n{context_text}\n\n"
                f"Question: {query}"
            )

            # 3. Call the Selected Provider for final Answer
            provider = settings.api_provider
            
            if provider == "gemini":
                if not gemini_client:
                    raise ValueError("Gemini API key is missing or invalid in Settings.")
                
                llm_model = settings.llm_model
                if not llm_model or "pro" in llm_model.lower() or "gpt" in llm_model.lower():
                    llm_model = "gemini-2.5-flash"
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

            # 4. Log telemetry
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
        """Uses NetworkX to build a graph from DB edges and traverse neighbors of queried entities."""
        
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

        edges = self.sql_repo.get_all_graph_edges()
        G = nx.MultiGraph() 
        
        for edge in edges:
            doc_name = edge.document.name if edge.document else "Unknown"
            G.add_edge(edge.source_node, edge.target_node, relation=edge.relation, doc=doc_name)

        context_results = []
        found_nodes = set()
        
        for entity in query_entities:
            for node in G.nodes():
                if entity.lower() in str(node).lower():
                    found_nodes.add(node)
                    
        for node in found_nodes:
            for neighbor in G.neighbors(node):
                edge_data_dict = G.get_edge_data(node, neighbor)
                
                for key, edge_data in edge_data_dict.items():
                    rel = edge_data.get('relation', 'connected to')
                    doc = edge_data.get('doc', 'Unknown')
                    
                    context_results.append({
                        "text": f"Knowledge Graph Record: {node} --[{rel}]--> {neighbor}",
                        "source_document": doc
                    })
                    
        unique_contexts = []
        seen = set()
        for c in context_results:
            if c['text'] not in seen:
                seen.add(c['text'])
                unique_contexts.append(c)

        return unique_contexts[:20]