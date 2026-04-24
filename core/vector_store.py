import os
import logging
from typing import Union
from langchain_community.vectorstores import Chroma, Qdrant
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config.settings import (
    GOOGLE_API_KEY,
    VECTOR_STORE_TYPE,
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    QDRANT_URL,
    QDRANT_API_KEY,
    EMBEDDING_MODEL
)

logger = logging.getLogger("vector_store")

def get_vector_store() -> Union[Chroma, Qdrant]:
    """
    Factory function to return the configured vector store instance.
    Defaults to Chroma for local dev and Qdrant for production if configured.
    """
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=GOOGLE_API_KEY)
    
    if VECTOR_STORE_TYPE.lower() == "qdrant" and QDRANT_URL:
        logger.info(f"Connecting to Qdrant Cloud at {QDRANT_URL}...")
        return Qdrant.from_existing_collection(
            embedding=embeddings,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            collection_name=CHROMA_COLLECTION_NAME, # Reusing collection name setting
        )
    
    # Default to Chroma
    is_production = os.getenv("RENDER") or os.getenv("VERCEL")
    
    if is_production:
        logger.info("🌊 Production Detected: Initializing IN-MEMORY High-Availability Store.")
        return Chroma(
            embedding_function=embeddings,
            collection_name=CHROMA_COLLECTION_NAME
        )
    else:
        logger.info(f"📁 Desktop Detected: Initializing DISK-PERSISTENT Store at {CHROMA_PERSIST_DIR}")
        return Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=embeddings,
            collection_name=CHROMA_COLLECTION_NAME,
        )
