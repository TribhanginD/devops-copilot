import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import os
from devops_copilot.utils.logger import logger

class MemorySystem:
    """Persistent memory using ChromaDB."""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name="agent_memory")
        logger.info(f"Memory system initialized at {persist_directory}")

    def add_memories(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """Adds documents to the vector store."""
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Added {len(documents)} memories to vector store.")

    def search_memories(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Searches for relevant memories."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

class SessionManager:
    """Handles ephemeral session state."""
    
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self._sessions:
            self._sessions[session_id] = {"history": [], "context": {}}
        return self._sessions[session_id]

    def update_session(self, session_id: str, key: str, value: Any):
        session = self.get_session(session_id)
        session[key] = value

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
