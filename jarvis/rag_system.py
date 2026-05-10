# jarvis/rag_system.py - RAG System for Enhanced Memory & Knowledge

import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    import chromadb
    from chromadb.config import Settings
    HAS_RAG = True
except ImportError:
    logger.warning("[WARNING] RAG dependencies not installed. Install: chromadb, sentence-transformers")
    HAS_RAG = False


class HybridRAGSystem:
    """Lightweight local RAG fallback that works without external vector deps."""

    def __init__(self, memory_db):
        self.memory = memory_db

    def add_knowledge(self, title: str, content: str, session_id: str = "default", tags: Optional[List[str]] = None, source: str = "user"):
        fn = getattr(self.memory, "add_knowledge", None)
        if callable(fn):
            fn(title, content, session_id=session_id, tags=tags or [], source=source)

    def retrieve(self, query: str, session_id: str = "default", limit: int = 5) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        search_conversation = getattr(self.memory, "search_conversation", lambda *a, **k: [])
        search_knowledge = getattr(self.memory, "search_knowledge", lambda *a, **k: [])

        tokens = [tok for tok in query.lower().split() if tok]
        conv = search_conversation(query, session_id=session_id, limit=limit * 3)
        know = search_knowledge(query, session_id=session_id, limit=limit * 3)

        for token in tokens:
            conv.extend(search_conversation(token, session_id=session_id, limit=limit * 2))
            know.extend(search_knowledge(token, session_id=session_id, limit=limit * 2))

        for item in conv:
            items.append({
                "source": item.get("role", "conversation"),
                "content": item.get("content", ""),
                "score": self._score(query, item.get("content", "")),
            })
        for item in know:
            items.append({
                "source": item.get("title", "knowledge"),
                "content": item.get("content", ""),
                "score": self._score(query, f"{item.get('title', '')} {item.get('content', '')}"),
            })

        items.sort(key=lambda x: x["score"], reverse=True)
        return [item for item in items if item["score"] > 0][:limit]

    def search_knowledge(self, query: str, session_id: str = "default", limit: int = 5) -> List[Dict[str, Any]]:
        results = self.retrieve(query, session_id=session_id, limit=limit)
        return [
            {"title": item.get("source", "knowledge"), "content": item.get("content", "")}
            for item in results
        ]

    def _score(self, query: str, content: str) -> float:
        q_tokens = {tok for tok in query.lower().split() if tok}
        c_tokens = {tok for tok in content.lower().split() if tok}
        if not q_tokens or not c_tokens:
            return 0.0
        overlap = len(q_tokens & c_tokens)
        return overlap / float(len(q_tokens))

class RAGSystem:
    """Retrieval-Augmented Generation System for enhanced memory and context."""
    
    def __init__(self, persist_dir: str = "jarvis/data/chroma"):
        if not HAS_RAG:
            logger.warning("RAG system disabled - dependencies missing")
            self.enabled = False
            return
        
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedding model (lightweight)
        logger.info("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')  # 22M params, fast
        
        # Initialize Chroma client
        logger.info("Initializing vector database...")
        settings = Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=str(self.persist_dir),
            anonymized_telemetry=False
        )
        self.client = chromadb.Client(settings)
        
        # Create collections
        self.conversation_collection = self.client.get_or_create_collection(
            name="conversations",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.knowledge_collection = self.client.get_or_create_collection(
            name="knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.enabled = True
        logger.info("[OK] RAG System initialized")

    def add_to_memory(self, session_id: str, role: str, content: str):
        """Add conversation turn to vector memory."""
        if not self.enabled:
            return
        
        try:
            embedding = self.embedding_model.encode(content).tolist()
            doc_id = f"{session_id}_{role}_{datetime.now().isoformat()}"
            
            self.conversation_collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[{
                    "session_id": session_id,
                    "role": role,
                    "timestamp": datetime.now().isoformat()
                }]
            )
            logger.debug(f"Added to memory: {doc_id}")
        except Exception as e:
            logger.error(f"[ERROR] Error adding to memory: {e}")

    def add_knowledge(self, title: str, content: str, source: str = "user"):
        """Add knowledge/document to knowledge base."""
        if not self.enabled:
            return
        
        try:
            embedding = self.embedding_model.encode(content).tolist()
            doc_id = f"knowledge_{title}_{datetime.now().isoformat()}"
            
            self.knowledge_collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[{
                    "title": title,
                    "source": source,
                    "timestamp": datetime.now().isoformat()
                }]
            )
            logger.info(f"Added knowledge: {title}")
        except Exception as e:
            logger.error(f"[ERROR] Error adding knowledge: {e}")

    def retrieve_relevant_context(self, query: str, session_id: Optional[str] = None, 
                                 top_k: int = 5) -> List[Dict]:
        """Retrieve most relevant context for a query."""
        if not self.enabled:
            return []
        
        try:
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search both collections
            conversation_results = self.conversation_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where={"session_id": session_id} if session_id else None
            )
            
            knowledge_results = self.knowledge_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            
            # Combine results
            results: List[Dict] = []
            
            for i, doc in enumerate(conversation_results["documents"][0]):
                results.append({
                    "type": "conversation",
                    "content": doc,
                    "distance": conversation_results["distances"][0][i],
                    "metadata": conversation_results["metadatas"][0][i]
                })
            
            for i, doc in enumerate(knowledge_results["documents"][0]):
                results.append({
                    "type": "knowledge",
                    "content": doc,
                    "distance": knowledge_results["distances"][0][i],
                    "metadata": knowledge_results["metadatas"][0][i]
                })
            
            # Sort by relevance
            results.sort(key=lambda x: x["distance"])
            
            logger.debug(f"Retrieved {len(results)} relevant documents")
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"[ERROR] Error retrieving context: {e}")
            return []

    def build_augmented_context(self, query: str, session_id: Optional[str] = None) -> str:
        """Build augmented context string for LLM."""
        if not self.enabled:
            return ""
        
        retrieved = self.retrieve_relevant_context(query, session_id)
        
        if not retrieved:
            return ""
        
        context = "\n\n--- RELEVANT CONTEXT ---\n"
        for item in retrieved:
            if item["type"] == "conversation":
                context += f"[{item['metadata'].get('role', 'Unknown')}]: {item['content']}\n"
            else:
                context += f"[Knowledge: {item['metadata'].get('title', 'Unknown')}]\n{item['content']}\n"
        
        return context

    def cleanup(self):
        """Cleanup resources."""
        try:
            if self.enabled and hasattr(self, 'client'):
                self.client = None
            logger.info("RAG system cleaned up")
        except Exception as e:
            logger.error(f"Error cleanup: {e}")


class EntityMemory:
    """Tracks entities (people, places, things) mentioned by user."""
    
    def __init__(self):
        self.entities: Dict[str, Dict[str, Any]] = {}
        logger.info("Entity Memory initialized")
    
    def add_entity(self, name: str, entity_type: str, properties: Optional[Dict[str, Any]] = None):
        """Add or update an entity."""
        if name not in self.entities:
            self.entities[name] = {
                "type": entity_type,
                "properties": properties or {},
                "mentioned_count": 0,
                "last_mentioned": datetime.now().isoformat()
            }
        else:
            self.entities[name]["mentioned_count"] += 1
            self.entities[name]["last_mentioned"] = datetime.now().isoformat()
            if properties:
                self.entities[name]["properties"].update(properties)
    
    def get_entity(self, name: str) -> Optional[Dict]:
        """Get entity information."""
        return self.entities.get(name)
    
    def get_context_about_entities(self, names: List[str]) -> str:
        """Get context about mentioned entities."""
        context: str = ""
        for name in names:
            entity = self.get_entity(name)
            if entity:
                context += f"\n{name} ({entity['type']}): {entity['properties']}"
        return context
    
    def extract_entities_from_text(self, text: str) -> List[str]:
        """Basic entity extraction (can be enhanced with NER)."""
        # Simple: look for capitalized words
        words = text.split()
        potential_entities = [w.strip('.,!?') for w in words if w[0].isupper() and len(w) > 2]
        return potential_entities


class ConversationSummarizer:
    """Summarizes conversations to keep long-term memory manageable."""
    
    def __init__(self, llm):
        self.llm = llm
        logger.info("Conversation Summarizer initialized")
    
    def summarize_session(self, session_turns: List[Dict]) -> str:
        """Summarize a conversation session."""
        if not session_turns:
            return "Empty session"
        
        # Build conversation text
        conv_text = "\n".join([f"{t['role']}: {t['content']}" for t in session_turns])
        
        prompt = f"""Summarize this conversation in 2-3 sentences in Roman Urdu:

{conv_text}

Summary:"""
        
        try:
            summary = self.llm.generate(prompt)
            logger.debug(f"Session summarized: {len(summary)} chars")
            return summary
        except Exception as e:
            logger.error(f"Error summarizing: {e}")
            return "Summary generation failed"
