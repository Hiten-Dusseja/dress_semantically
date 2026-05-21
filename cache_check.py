"""
Semantic Cache for Fashion Recommendations
Uses embeddings to check if similar queries have been cached
"""

import os
import json
from typing import Optional, Dict, Any
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# ─── Configuration ────────────────────────────────────────────────────────────
CACHE_DB_DIR = "cache_db"
CACHE_COLLECTION_NAME = "query_cache"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.85  # Queries above this similarity are considered cache hits

# ─── Initialize Cache Components ──────────────────────────────────────────────

_cache_vectorstore = None
_embeddings = None

def get_embeddings():
    """Get embeddings model (singleton)."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    return _embeddings


def get_cache_vectorstore():
    """Get or create cache vector store (singleton)."""
    global _cache_vectorstore
    if _cache_vectorstore is None:
        os.makedirs(CACHE_DB_DIR, exist_ok=True)
        
        embeddings = get_embeddings()
        
        _cache_vectorstore = Chroma(
            persist_directory=CACHE_DB_DIR,
            embedding_function=embeddings,
            collection_name=CACHE_COLLECTION_NAME
        )
    
    return _cache_vectorstore


# ─── Cache Operations ─────────────────────────────────────────────────────────

def check_cache(user_query: str) -> Optional[Dict[str, Any]]:
    """
    Check if a similar query exists in cache.
    
    Args:
        user_query: User's fashion query
        
    Returns:
        Cached response if found, None otherwise
    """
    print(f"\n🔍 Checking cache for: '{user_query}'")
    
    vectorstore = get_cache_vectorstore()
    
    # Search for similar queries
    results = vectorstore.similarity_search_with_score(user_query, k=1)
    
    if not results:
        print("  ❌ Cache miss - no similar queries found")
        return None
    
    doc, score = results[0]
    similarity = 1 - score  # Convert distance to similarity
    
    print(f"  📊 Most similar query: '{doc.page_content}'")
    print(f"  📊 Similarity score: {similarity:.3f} (threshold: {SIMILARITY_THRESHOLD})")
    
    if similarity >= SIMILARITY_THRESHOLD:
        print("  ✅ Cache hit!")
        # Return cached response from metadata
        cached_response = json.loads(doc.metadata.get('response', '{}'))
        return cached_response
    else:
        print("  ❌ Cache miss - similarity below threshold")
        return None


def save_to_cache(user_query: str, response: Dict[str, Any]) -> None:
    """
    Save query and response to cache.
    
    Args:
        user_query: User's fashion query
        response: The recommendation response to cache
    """
    print(f"\n💾 Saving to cache: '{user_query}'")
    
    vectorstore = get_cache_vectorstore()
    
    # Store query as document with response in metadata
    vectorstore.add_texts(
        texts=[user_query],
        metadatas=[{
            "response": json.dumps(response, ensure_ascii=False),
            "query": user_query
        }]
    )
    
    print("  ✅ Saved to cache")


def clear_cache() -> None:
    """Clear all cached queries."""
    global _cache_vectorstore
    
    # Close the connection first
    if _cache_vectorstore is not None:
        try:
            # Try to delete the collection
            _cache_vectorstore._client.delete_collection(CACHE_COLLECTION_NAME)
            print("✅ Collection deleted")
        except Exception as e:
            print(f"⚠ Could not delete collection: {e}")
        
        # Reset the global variable
        _cache_vectorstore = None
    
    # Try to remove the directory
    if os.path.exists(CACHE_DB_DIR):
        try:
            import shutil
            import time
            
            # Wait a bit for file handles to be released
            time.sleep(0.5)
            
            # Try to remove with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    shutil.rmtree(CACHE_DB_DIR)
                    print("✅ Cache directory cleared")
                    break
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        print(f"  Retry {attempt + 1}/{max_retries}...")
                        time.sleep(1)
                    else:
                        print(f"⚠ Could not delete cache directory: {e}")
                        print("  Cache collection was deleted but directory remains locked")
                        print("  It will be cleared on next restart")
        except Exception as e:
            print(f"⚠ Error clearing cache: {e}")
    else:
        print("⚠ Cache directory does not exist")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    vectorstore = get_cache_vectorstore()
    count = vectorstore._collection.count()
    
    return {
        "total_cached_queries": count,
        "cache_directory": CACHE_DB_DIR,
        "similarity_threshold": SIMILARITY_THRESHOLD
    }


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test cache operations
    print("="*70)
    print("  SEMANTIC CACHE TEST")
    print("="*70)
    
    # Test query
    test_query = "I have a black shirt, what should I wear for a wedding?"
    test_response = {
        "recommended_items": [{"name": "Test Item", "price": "₹1000"}],
        "total_price": "₹1000",
        "stylist_note": "Test note"
    }
    
    # Save to cache
    save_to_cache(test_query, test_response)
    
    # Check cache with exact query
    result = check_cache(test_query)
    print(f"\nExact query result: {result is not None}")
    
    # Check cache with similar query
    similar_query = "I have a black shirt, what bottoms for wedding?"
    result = check_cache(similar_query)
    print(f"\nSimilar query result: {result is not None}")
    
    # Check cache with different query
    different_query = "Show me blue joggers"
    result = check_cache(different_query)
    print(f"\nDifferent query result: {result is not None}")
    
    # Stats
    stats = get_cache_stats()
    print(f"\nCache stats: {stats}")
