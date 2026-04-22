import os
import logging
from typing import Union
from langchain_community.vectorstores import Chroma, Qdrant
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from config.settings import (
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
    embeddings = FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)
    
    if VECTOR_STORE_TYPE.lower() == "qdrant" and QDRANT_URL:
        logger.info(f"Connecting to Qdrant Cloud at {QDRANT_URL}...")
        return Qdrant.from_existing_collection(
            embedding=embeddings,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            collection_name=CHROMA_COLLECTION_NAME, # Reusing collection name setting
        )
    
    # Default to Chroma
    logger.info(f"Using local ChromaDB at {CHROMA_PERSIST_DIR}")
    return Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=embeddings,
        collection_name=CHROMA_COLLECTION_NAME,
    )
