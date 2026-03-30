"""Long-term memory module using ChromaDB for semantic search over conversation history."""

import os
import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime


# Persistent storage directory (Allow override via env for Render/Docker volumes)
CHROMA_DATA_PATH = os.getenv("CHROMA_DB_PATH", os.path.join(os.getcwd(), "chroma_db"))

embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)

collection = chroma_client.get_or_create_collection(
    name="coach_memory",
    embedding_function=embedding_func
)


class LongTermMemory:
    """Semantic memory layer — stores every message and retrieves relevant context."""

    @staticmethod
    def store(user_id: str, role: str, content: str):
        """Store a message into ChromaDB."""
        try:
            ts = datetime.now().isoformat()
            doc_id = f"{user_id}_{ts}_{role}"
            collection.add(
                documents=[content],
                metadatas=[{"user_id": str(user_id), "role": role, "timestamp": ts}],
                ids=[doc_id]
            )
        except Exception as e:
            print(f"   ⚠️ ChromaDB store error: {e}")

    @staticmethod
    def recall(user_id: str, query: str, limit: int = 5) -> str:
        """Retrieve semantically relevant past messages for a user."""
        try:
            results = collection.query(
                query_texts=[query],
                where={"user_id": str(user_id)},
                n_results=limit
            )
            if not results or not results["documents"][0]:
                return ""

            lines = []
            for i, doc in enumerate(results["documents"][0]):
                role = results["metadatas"][0][i].get("role", "unknown")
                lines.append(f"[{role}]: {doc}")
            return "\n".join(lines)
        except Exception as e:
            print(f"   ⚠️ ChromaDB recall error: {e}")
            return ""

    @staticmethod
    def clear(user_id: str):
        """Delete all stored memory for a user."""
        try:
            collection.delete(where={"user_id": str(user_id)})
        except Exception as e:
            print(f"   ⚠️ ChromaDB clear error: {e}")
