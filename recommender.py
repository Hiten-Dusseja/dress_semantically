"""
Fashion RAG Recommender - Simple Query Pipeline
Takes user queries and recommends fashion items using LLM + Vector Search
"""

import os
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
import json
import re

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


# ─── Query Processing Chain ───────────────────────────────────────────────────

QUERY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a fashion expert. Analyze the user's query and generate ONE specific search term for the best recommendation.

**Case 1: User wants recommendations**
Example: "I have a black shirt, what should I pair with it for a wedding?"
→ Think about the BEST single item to recommend and output ONE search term like: "formal dress trousers black"

**Case 2: User is directly searching**
Example: "Show me black joggers"
→ Just refine the query: "black joggers"

Output ONLY ONE search term (not comma-separated, just one item), nothing else."""),
    ("user", "{query}")
])


def process_query(user_query: str, min_price: int = 0, max_price: int = 10000):
    """
    Process user query through LLM and search vector store with price filtering.
    
    Args:
        user_query: User's fashion query
        min_price: Minimum price filter (default: 0)
        max_price: Maximum price filter (default: 10000)
        
    Returns:
        List of recommended items with details
    """
    print(f"\n💬 User Query: {user_query}")
    print(f"💰 Price Range: ₹{min_price:,} - ₹{max_price:,}")
    
    # Step 1: LLM generates ONE search term for best recommendation
    llm = get_llm()
    chain = QUERY_PROMPT | llm | StrOutputParser()
    
    print("\n🤖 LLM processing query...")
    search_term = chain.invoke({"query": user_query})
    print(f"🔍 Search term: {search_term}")
    
    # Step 2: Search vector store with price filtering
    vectorstore = get_vectorstore()
    
    # Try to find items within price range
    attempts = 0
    max_attempts = 5
    current_min = min_price
    current_max = max_price
    results = []
    
    while attempts < max_attempts:
        print(f"\n🔎 Searching with range: ₹{current_min:,} - ₹{current_max:,}")
        
        # Get more results to filter by price
        all_results = vectorstore.similarity_search(search_term, k=20)
        
        # Filter by price range
        filtered_results = []
        for doc in all_results:
            price_str = doc.metadata.get('price', '0')
            price_value = extract_price_value(price_str)
            
            if current_min <= price_value <= current_max:
                filtered_results.append(doc)
        
        if len(filtered_results) >= 5:
            results = filtered_results[:5]
            break
        elif len(filtered_results) > 0:
            results = filtered_results
            break
        
        # Expand range by 500 on both sides
        current_min = max(0, current_min - 500)
        current_max = current_max + 500
        attempts += 1
        print(f"  ⚠ Found {len(filtered_results)} items, expanding range...")
    
    if not results:
        print("  ❌ No items found even after expanding range")
        return []
    
    print(f"  ✓ Found {len(results)} items in range ₹{current_min:,} - ₹{current_max:,}")
    
    # Step 3: Format results
    items = []
    print(f"\n📦 Items from database:")
    for i, doc in enumerate(results, 1):
        meta = doc.metadata
        item = {
            "name": meta.get('name', 'N/A'),
            "brand": meta.get('brand', 'N/A'),
            "category": meta.get('category', 'N/A'),
            "gender": meta.get('gender', 'N/A'),
            "price": meta.get('price', 'N/A'),
            "description": meta.get('description', 'N/A'),
            "product_url": meta.get('product_url', 'N/A'),
            "image_url": meta.get('image_url', 'N/A'),
        }
        items.append(item)
        
        # Print each item
        print(f"\n  [{i}] {item['name']}")
        print(f"      Brand: {item['brand']}")
        print(f"      Category: {item['category']} | Gender: {item['gender']}")
        print(f"      Price: {item['price']}")
        print(f"      Description: {item['description']}")
    
    return items


# ─── Stylist Justification ────────────────────────────────────────────────────

STYLIST_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a luxury fashion stylist. Evaluate the recommended items and create a sophisticated justification.

Analyze:
- Color coordination and harmony
- Style compatibility (formal/casual/occasion-appropriate)
- Fashion rules and principles
- Overall aesthetic cohesion

Return a JSON object with:
{{
  "recommended_items": [
    {{
      "name": "item name",
      "brand": "brand name",
      "price": "price",
      "why_this_works": "brief explanation"
    }}
  ],
  "total_price": "calculated total",
  "stylist_note": "A luxurious 2-3 sentence note explaining why these pieces work together as a cohesive outfit"
}}

Be elegant, concise, and authoritative."""),
    ("user", """User Query: {query}

Recommended Items:
{items}

Provide your expert styling justification.""")
])


def extract_price_value(price_str):
    """Extract numeric value from price string."""
    if not price_str or price_str == 'N/A':
        return 0
    # Extract numbers from string like "₹ 1499" or "1499"
    match = re.search(r'[\d,]+', str(price_str))
    if match:
        return int(match.group().replace(',', ''))
    return 0


def justify_recommendations(user_query: str, items: list):
    """
    Get stylist justification for recommended items.
    
    Args:
        user_query: Original user query
        items: List of recommended items
        
    Returns:
        JSON payload with justified recommendations
    """
    if not items:
        return {
            "recommended_items": [],
            "total_price": "₹ 0",
            "stylist_note": "No items found matching your criteria."
        }
    
    print("\n✨ Generating stylist justification...")
    
    # Format items for LLM
    items_text = "\n\n".join([
        f"Item {i+1}:\n"
        f"- Name: {item['name']}\n"
        f"- Brand: {item['brand']}\n"
        f"- Category: {item['category']}\n"
        f"- Gender: {item['gender']}\n"
        f"- Price: {item['price']}\n"
        f"- Description: {item['description']}"
        for i, item in enumerate(items)
    ])
    
    # Get LLM justification
    llm = get_llm()
    chain = STYLIST_PROMPT | llm | StrOutputParser()
    
    response = chain.invoke({
        "query": user_query,
        "items": items_text
    })
    
    # Parse JSON response
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(response)
        
        # Calculate total price
        total = sum(extract_price_value(item.get('price')) for item in items)
        result['total_price'] = f"₹ {total:,}"
        
        # Add full item details
        for i, rec_item in enumerate(result.get('recommended_items', [])):
            if i < len(items):
                rec_item.update({
                    "product_url": items[i]['product_url'],
                    "image_url": items[i]['image_url'],
                    "description": items[i]['description'],
                    "category": items[i]['category'],
                    "gender": items[i]['gender']
                })
        
        return result
        
    except Exception as e:
        print(f"⚠ JSON parsing failed: {e}")
        # Fallback response
        total = sum(extract_price_value(item.get('price')) for item in items)
        return {
            "recommended_items": [
                {
                    "name": item['name'],
                    "brand": item['brand'],
                    "price": item['price'],
                    "product_url": item['product_url'],
                    "image_url": item['image_url'],
                    "why_this_works": "Carefully selected to match your style requirements."
                }
                for item in items
            ],
            "total_price": f"₹ {total:,}",
            "stylist_note": "These pieces have been curated to create a cohesive and stylish ensemble."
        }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(user_query: str, min_price: int = 0, max_price: int = 10000):
    """
    Main function to get fashion recommendations.
    
    Args:
        user_query: User's fashion query
        min_price: Minimum price filter (default: 0)
        max_price: Maximum price filter (default: 10000)
        
    Returns:
        JSON payload with justified recommendations
    """
    print("="*70)
    print("  FASHION RECOMMENDER")
    print("="*70)
    
    # Step 1: Get items from vector search with price filtering
    items = process_query(user_query, min_price, max_price)
    
    if not items:
        print("\n❌ No items found")
        return {
            "recommended_items": [],
            "total_price": "₹ 0",
            "stylist_note": "No items found matching your criteria."
        }
    
    # Step 2: Get stylist justification
    result = justify_recommendations(user_query, items)
    
    # Step 3: Display results
    print("\n" + "="*70)
    print("  STYLIST RECOMMENDATIONS")
    print("="*70)
    
    print(f"\n💰 Total Price: {result['total_price']}")
    print(f"\n✨ Stylist Note:\n{result['stylist_note']}")
    
    print(f"\n📦 Recommended Items ({len(result['recommended_items'])}):")
    for i, item in enumerate(result['recommended_items'], 1):
        print(f"\n[{i}] {item['name']}")
        print(f"    Brand: {item['brand']}")
        print(f"    Price: {item['price']}")
        print(f"    Why: {item.get('why_this_works', 'N/A')}")
        if 'product_url' in item:
            print(f"    URL: {item['product_url']}")
    
    print("\n" + "="*70)
    
    return result


if __name__ == "__main__":
    # Example queries
    query = "I want some blue comfy pants"
    # query = "Show me black joggers"
    
    # With default price range (0 - 10000)
    main(query, 0, 500)
    
    # With custom price range
    # main(query, min_price=1000, max_price=2000)
