"""
Fashion RAG Recommender - ReAct Agent with Tool Calling
Takes user queries and recommends fashion items using agentic LLM + Vector Search
"""

import os
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
import json
import re
from logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__, "recommender.log")

# Load environment variables
load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────
CHROMA_DB_DIR = "chroma_db"
COLLECTION_NAME = "fashion_items"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# LangSmith configuration
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "fashion-rag-recommender"

# ─── Initialize Components ────────────────────────────────────────────────────

_vectorstore = None
_llm = None

def get_vectorstore():
    """Load ChromaDB vector store (singleton)."""
    global _vectorstore
    if _vectorstore is None:
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        _vectorstore = Chroma(
            persist_directory=CHROMA_DB_DIR,
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME
        )
    
    return _vectorstore


def get_llm():
    """Initialize Groq LLM (singleton)."""
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            api_key=os.getenv("GROQ_API_KEY")
        )
    return _llm


# ─── Helper Functions ─────────────────────────────────────────────────────────

def extract_price_value(price_str):
    """Extract numeric value from price string."""
    if not price_str or price_str == 'N/A':
        return 0
    match = re.search(r'[\d,]+', str(price_str))
    if match:
        return int(match.group().replace(',', ''))
    return 0


# ─── Fashion Search Tool ──────────────────────────────────────────────────────

@tool
def search_fashion_items(search_term: str, min_price: int = 0, max_price: int = 10000, gender: str = "men") -> str:
    """
    Search for fashion items in the database with price and gender filtering.
    Automatically expands price range if no items found.
    
    Args:
        search_term: What to search for (e.g., "formal black pants", "casual joggers")
        min_price: Minimum price in rupees (default: 0) integer field not string
        max_price: Maximum price in rupees (default: 10000) integer field not string
        gender: Gender filter - "men" or "women" (default: "men")
        make sure you send min and max price as integers 
    Returns:
        JSON string with list of items found
    """
    logger.info(f"Tool called - search_term: '{search_term}', price: ₹{min_price:,}-₹{max_price:,}, gender: '{gender}'")
    
    vectorstore = get_vectorstore()
    
    # Normalize gender input
    gender = gender.lower().strip()
    if gender not in ["men", "women"]:
        gender = "men"  # Default to men if invalid
    
    # Try to find items within price range with retry logic
    attempts = 0
    max_attempts = 5
    current_min = min_price
    current_max = max_price
    results = []
    
    while attempts < max_attempts:
        logger.info(f"Attempt {attempts + 1}: Searching ₹{current_min:,} - ₹{current_max:,}, gender={gender}")
        
        # Get more results to filter by price and gender
        all_results = vectorstore.similarity_search(search_term, k=30)
        
        # Filter by price range and gender
        filtered_results = []
        for doc in all_results:
            price_str = doc.metadata.get('price', '0')
            price_value = extract_price_value(price_str)
            item_gender = doc.metadata.get('gender', '').lower().strip()
            
            # Check both price and gender match
            if current_min <= price_value <= current_max and item_gender == gender:
                filtered_results.append(doc)
        
        if len(filtered_results) >= 5:
            results = filtered_results[:5]
            logger.info(f"Found {len(results)} items")
            break
        elif len(filtered_results) > 0:
            results = filtered_results
            logger.info(f"Found {len(results)} items (less than 5)")
            break
        
        # Expand range by 500 on both sides
        current_min = max(0, current_min - 500)
        current_max = current_max + 500
        attempts += 1
        logger.warning(f"Found {len(filtered_results)} items, expanding range...")
    
    if not results:
        return json.dumps({
            "success": False,
            "message": f"No {gender}'s items found even after expanding price range",
            "items": []
        })
    
    # Format results
    items = []
    for doc in results:
        meta = doc.metadata
        items.append({
            "name": meta.get('name', 'N/A'),
            "brand": meta.get('brand', 'N/A'),
            "category": meta.get('category', 'N/A'),
            "gender": meta.get('gender', 'N/A'),
            "price": meta.get('price', 'N/A'),
            "price_value": extract_price_value(meta.get('price', '0')),
            "description": meta.get('description', 'N/A'),
            "product_url": meta.get('product_url', 'N/A'),
            "image_url": meta.get('image_url', 'N/A'),
        })
    
    return json.dumps({
        "success": True,
        "items": items,
        "price_range_used": f"₹{current_min:,} - ₹{current_max:,}",
        "gender": gender,
        "count": len(items)
    })


# ─── ReAct Agent Setup ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a luxury fashion stylist AI agent. Help users find the perfect clothing items.

Your task:
1. Analyze the user's query to understand what they need
2. Extract or infer:
   - The type of clothing item to search for (be specific: "formal black pants", not just "pants")
   - Price range if mentioned (default: 0-10000 rupees)
   - Gender: "men" or "women" (default: "men" if not specified)
3. Use the search_fashion_items tool to find items (make sure you send min and max price as integers and gender as string)
4. Evaluate the results based on fashion rules:
   - Color coordination
   - Style compatibility (formal/casual/occasion)
   - Fashion principles
5. Return a final JSON response with:
   {{
     "recommended_items": [
       {{
         "name": "item name",
         "brand": "brand",
         "price": "price",
         "product_url": "url",
         "image_url": "url",
         "why_this_works": "brief elegant explanation"
       }}
     ],
     "total_price": "calculated total",
     "stylist_note": "A luxurious 2-3 sentence note explaining why these pieces work together"
   }}

Be elegant, concise, and authoritative in your styling advice."""


def create_fashion_agent():
    """Create the fashion agent with tool calling."""
    llm = get_llm()
    tools = [search_fashion_items]
    checkpointer = InMemorySaver()
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    
    return agent


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(user_query: str):
    """
    Main function to get fashion recommendations using agent.
    
    Args:
        user_query: User's fashion query (can include price preferences)
        
    Returns:
        JSON payload with justified recommendations
    """
    logger.info("="*70)
    logger.info("FASHION RECOMMENDER - Agentic Flow")
    logger.info("="*70)
    logger.info(f"User Query: {user_query}")
    
    # Create and run agent
    agent = create_fashion_agent()
    
    try:
        response = agent.invoke(
            {"messages": [{"role": "user", "content": user_query}]},
            config={"configurable": {"thread_id": "fashion-agent"}}
        )
        
        final_answer = response["messages"][-1].content
        
        # Try to parse JSON from final answer
        try:
            json_match = re.search(r'\{.*\}', final_answer, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(final_answer)
            
            # Ensure total_price is a string
            if "total_price" in result:
                if isinstance(result["total_price"], (int, float)):
                    result["total_price"] = f"₹ {result['total_price']:,}"
                elif not isinstance(result["total_price"], str):
                    result["total_price"] = str(result["total_price"])
            else:
                result["total_price"] = "₹ 0"
            
            # Ensure stylist_note exists
            if "stylist_note" not in result:
                result["stylist_note"] = "These pieces have been carefully curated for your style."
            
            # Ensure recommended_items exists
            if "recommended_items" not in result:
                result["recommended_items"] = []
            
            # Display results
            logger.info("="*70)
            logger.info("STYLIST RECOMMENDATIONS")
            logger.info("="*70)
            logger.info(f"Total Price: {result.get('total_price', 'N/A')}")
            logger.info(f"Stylist Note: {result.get('stylist_note', 'N/A')}")
            
            items = result.get('recommended_items', [])
            logger.info(f"Recommended Items: {len(items)}")
            for i, item in enumerate(items, 1):
                logger.info(f"[{i}] {item.get('name', 'N/A')} - {item.get('brand', 'N/A')} - {item.get('price', 'N/A')}")
            
            logger.info("="*70)
            
            return result
            
        except Exception as e:
            logger.error(f"Could not parse JSON: {e}")
            logger.debug(f"Raw response: {final_answer}")
            return {
                "recommended_items": [],
                "total_price": "₹ 0",
                "stylist_note": "Failed to parse response. Please try again.",
                "error": str(e),
                "raw": final_answer
            }
    
    except Exception as e:
        logger.error(f"Agent error: {e}")
        return {
            "recommended_items": [],
            "total_price": "₹ 0",
            "stylist_note": "An error occurred. Please try again.",
            "error": str(e)
        }


if __name__ == "__main__":
    # Example queries
    
    # Query with implicit price range
    query = "I  have blue polo I wanna buy bottoms for it but i have only 1500 rs"
    
    # Query with explicit price range
    # query = "Show me casual joggers under 2000 rupees"
    
    # Query with specific requirements
    # query = "I need formal pants between 1500 and 3000 rupees that go well with a white shirt"
    
    main(query)
