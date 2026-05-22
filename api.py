"""
FastAPI Server for Fashion Recommendations with Semantic Caching
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn

from cache_check import check_cache, save_to_cache, get_cache_stats, clear_cache
from recommender import main as get_recommendations
from logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__, "api.log")

# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Fashion Recommender API",
    description="AI-powered fashion recommendations with semantic caching",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request/Response Models ──────────────────────────────────────────────────

class RecommendationRequest(BaseModel):
    query: str
    use_cache: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "I have a black shirt, what should I buy for bottoms to wear on a wedding day?",
                "use_cache": True
            }
        }


class RecommendationResponse(BaseModel):
    recommended_items: list
    total_price: str
    stylist_note: str
    cache_hit: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "recommended_items": [
                    {
                        "name": "Formal Black Pants",
                        "brand": "The Souled Store",
                        "price": "₹1,499",
                        "product_url": "https://...",
                        "image_url": "https://...",
                        "why_this_works": "Perfect formal match for wedding"
                    }
                ],
                "total_price": "₹7,495",
                "stylist_note": "These pieces create an elegant wedding ensemble...",
                "cache_hit": False
            }
        }


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Fashion Recommender API",
        "version": "1.0.0"
    }


@app.post("/recommend", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest):
    """
    Get fashion recommendations for a query.
    Uses semantic caching to speed up similar queries.
    """
    try:
        cache_hit = False
        
        # Check cache if enabled
        if request.use_cache:
            cached_response = check_cache(request.query)
            if cached_response:
                cache_hit = True
                cached_response["cache_hit"] = True
                logger.info(f"Cache hit for query: '{request.query}'")
                return cached_response
        
        # Cache miss - get fresh recommendations
        logger.info(f"Getting fresh recommendations for: '{request.query}'")
        result = get_recommendations(request.query)
        
        # Add cache_hit flag
        result["cache_hit"] = False
        
        # Save to cache if enabled
        if request.use_cache:
            save_to_cache(request.query, result)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in recommend endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
def cache_stats():
    """Get cache statistics."""
    try:
        stats = get_cache_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache/clear")
def cache_clear():
    """Clear all cached queries."""
    try:
        clear_cache()
        return {
            "message": "Cache cleared successfully",
            "note": "If directory remains locked, it will be cleared on restart"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/reset")
def cache_reset():
    """Reset cache by deleting the collection (safer than clearing directory)."""
    try:
        global _cache_vectorstore
        from cache_check import _cache_vectorstore, CACHE_COLLECTION_NAME
        
        if _cache_vectorstore is not None:
            try:
                _cache_vectorstore._client.delete_collection(CACHE_COLLECTION_NAME)
                _cache_vectorstore = None
                return {
                    "message": "Cache collection deleted successfully",
                    "note": "New queries will create a fresh cache"
                }
            except Exception as e:
                return {
                    "message": "Could not delete collection",
                    "error": str(e)
                }
        else:
            return {
                "message": "Cache not initialized yet",
                "note": "Nothing to clear"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    """Detailed health check."""
    try:
        stats = get_cache_stats()
        return {
            "status": "healthy",
            "cache": {
                "enabled": True,
                "total_queries": stats["total_cached_queries"]
            }
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }


# ─── Run Server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("="*70)
    logger.info("FASHION RECOMMENDER API")
    logger.info("="*70)
    logger.info("Starting server...")
    logger.info("API Docs: http://localhost:8000/docs")
    logger.info("Health: http://localhost:8000/health")
    logger.info("="*70)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
