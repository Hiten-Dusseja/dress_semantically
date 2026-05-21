# Flow Documentation

## Complete System Flow

This document describes the end-to-end flow of the Fashion RAG Recommender system, from data collection to user recommendations.

---

## Phase 1: Data Collection & Preparation

### Step 1: Web Scraping (`scraper.py`)

**Trigger**: Manual execution by developer

**Flow**:
```
1. Initialize Playwright browser (headless mode)
   ↓
2. For each target website (The Souled Store, Bewakoof):
   ├─ Navigate to category page (t-shirts, joggers, pants)
   ├─ Close popups/banners
   ├─ Slow scroll to trigger lazy-loading
   │  └─ Scroll 10-12 times with 1.5-3s delays
   ├─ Take screenshot for debugging
   ├─ Extract product cards using selector fallbacks
   │  └─ Try multiple selectors until one matches
   ├─ For each product card:
   │  ├─ Extract name (from title/alt/text)
   │  ├─ Extract price (from price elements)
   │  ├─ Extract description (from type/category)
   │  ├─ Extract product URL
   │  ├─ Extract image URL (from data-url or src)
   │  └─ Add metadata (brand, category, gender, timestamp)
   └─ Wait 8-15s before next page (rate limiting)
   ↓
3. Combine all scraped items
   ↓
4. Save to scraper_output/fashion_data.json
   ↓
5. Generate per-brand JSON files for inspection
```

**Output**: 
- `scraper_output/fashion_data.json` (all items)
- `scraper_output/souledstore.json`
- `scraper_output/bewakoof.json`
- Debug screenshots

---

### Step 2: Data Cleaning (`cleaner.py`)

**Trigger**: Manual execution after scraping

**Flow**:
```
1. Load fashion_data.json
   ↓
2. For each item:
   ├─ Validate required fields (name, brand, category, gender)
   ├─ Remove duplicates (by product_url)
   ├─ Normalize price format
   │  └─ Convert "₹ 1,499" to consistent format
   ├─ Clean text fields (trim whitespace, remove special chars)
   └─ Validate gender field (men/women)
   ↓
3. Remove invalid items
   ↓
4. Save cleaned data back to fashion_data.json
   ↓
5. Print statistics (total, removed, cleaned)
```

**Output**: Clean `fashion_data.json` ready for embedding

---

### Step 3: Embedding Generation (`embedding.py`)

**Trigger**: Manual execution after cleaning

**Flow**:
```
1. Initialize HuggingFace Embeddings
   ├─ Model: all-MiniLM-L6-v2
   ├─ Device: CPU
   └─ Normalize: True
   ↓
2. Initialize ChromaDB
   ├─ Create/connect to chroma_db/
   ├─ Delete existing collection (fresh start)
   └─ Create new collection: fashion_items
   ↓
3. Load fashion_data.json
   ↓
4. For each item:
   ├─ Create embedding text: "name - description"
   ├─ Prepare metadata (all fields except name/description)
   └─ Convert to LangChain Document
   ↓
5. Batch process (32 items at a time):
   ├─ Generate embeddings for batch
   ├─ Store in ChromaDB with metadata
   └─ Print progress
   ↓
6. Test with sample query ("black joggers")
   ↓
7. Print statistics (total embedded, collection count)
```

**Output**: 
- `chroma_db/` directory with vector embeddings
- Collection: `fashion_items` with ~900+ items

---

## Phase 2: Runtime Recommendation Flow

### User Request Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER SENDS REQUEST                            │
│  POST /recommend                                                 │
│  {                                                               │
│    "query": "I have a black shirt, what for wedding?",         │
│    "use_cache": true                                            │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI RECEIVES REQUEST                      │
│  - Validate request with Pydantic                               │
│  - Extract query and use_cache flag                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────────────┐
                    │  use_cache?   │
                    └───────┬───────┘
                            │
                ┌───────────┴───────────┐
                │                       │
               Yes                     No
                │                       │
                ↓                       │
┌─────────────────────────────────┐   │
│   SEMANTIC CACHE CHECK           │   │
│   (cache_check.py)               │   │
├─────────────────────────────────┤   │
│ 1. Generate query embedding      │   │
│ 2. Search cache_db ChromaDB      │   │
│ 3. Find most similar query       │   │
│ 4. Calculate similarity score    │   │
│    (1 - distance)                │   │
│ 5. Check threshold (>= 0.85)     │   │
└─────────────┬───────────────────┘   │
              │                       │
      ┌───────┴────────┐              │
      │  Cache Hit?    │              │
      └───┬────────┬───┘              │
          │        │                  │
         Yes       No                 │
          │        │                  │
          │        └──────────────────┘
          │                           │
          │                           ↓
          │        ┌─────────────────────────────────────────────┐
          │        │   RECOMMENDER AGENT (recommender.py)        │
          │        ├─────────────────────────────────────────────┤
          │        │ STEP 1: Agent Initialization                │
          │        │  - Load Groq LLM (Llama 3.3 70B)           │
          │        │  - Load search_fashion_items tool          │
          │        │  - Create agent with system prompt         │
          │        └─────────────────┬───────────────────────────┘
          │                          ↓
          │        ┌─────────────────────────────────────────────┐
          │        │ STEP 2: Query Analysis                      │
          │        │  Agent thinks:                              │
          │        │  - What clothing item? (e.g., "pants")     │
          │        │  - Price range? (extract or default)       │
          │        │  - Gender? (extract or default "men")      │
          │        └─────────────────┬───────────────────────────┘
          │                          ↓
          │        ┌─────────────────────────────────────────────┐
          │        │ STEP 3: Tool Invocation                     │
          │        │  Agent calls: search_fashion_items(         │
          │        │    search_term="formal black pants",       │
          │        │    min_price=0,                            │
          │        │    max_price=10000,                        │
          │        │    gender="men"                            │
          │        │  )                                          │
          │        └─────────────────┬───────────────────────────┘
          │                          ↓
          │        ┌─────────────────────────────────────────────┐
          │        │ STEP 4: Vector Search (Tool Execution)      │
          │        ├─────────────────────────────────────────────┤
          │        │ Attempt 1:                                  │
          │        │  1. Semantic search in ChromaDB            │
          │        │     - Query: "formal black pants"          │
          │        │     - Get top 30 results                   │
          │        │  2. Filter by price (0-10000)              │
          │        │  3. Filter by gender ("men")               │
          │        │  4. Check if >= 5 items found              │
          │        │                                             │
          │        │ If < 5 items:                               │
          │        │  Attempt 2:                                 │
          │        │   - Expand range: -500 to +500             │
          │        │   - Retry search                            │
          │        │                                             │
          │        │ Repeat up to 5 attempts                     │
          │        │                                             │
          │        │ Return: JSON with top 5 items               │
          │        └─────────────────┬───────────────────────────┘
          │                          ↓
          │        ┌─────────────────────────────────────────────┐
          │        │ STEP 5: Fashion Evaluation                  │
          │        │  Agent analyzes returned items:             │
          │        │  - Color coordination                       │
          │        │  - Style compatibility                      │
          │        │  - Occasion appropriateness                 │
          │        │  - Fashion principles                       │
          │        └─────────────────┬───────────────────────────┘
          │                          ↓
          │        ┌─────────────────────────────────────────────┐
          │        │ STEP 6: Response Generation                 │
          │        │  Agent creates JSON:                        │
          │        │  {                                          │
          │        │    "recommended_items": [                   │
          │        │      {                                      │
          │        │        "name": "...",                       │
          │        │        "brand": "...",                      │
          │        │        "price": "...",                      │
          │        │        "why_this_works": "..."             │
          │        │      }                                      │
          │        │    ],                                       │
          │        │    "total_price": "₹ X,XXX",              │
          │        │    "stylist_note": "..."                   │
          │        │  }                                          │
          │        └─────────────────┬───────────────────────────┘
          │                          ↓
          │        ┌─────────────────────────────────────────────┐
          │        │ STEP 7: Response Validation                 │
          │        │  - Parse JSON from LLM response            │
          │        │  - Ensure total_price is string            │
          │        │  - Ensure all required fields exist        │
          │        │  - Add cache_hit: false flag               │
          │        └─────────────────┬───────────────────────────┘
          │                          ↓
          │        ┌─────────────────────────────────────────────┐
          │        │ STEP 8: Save to Cache                       │
          │        │  - Generate query embedding                 │
          │        │  - Store in cache_db ChromaDB              │
          │        │  - Metadata: {query, response}             │
          │        └─────────────────┬───────────────────────────┘
          │                          │
          └──────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                    RETURN RESPONSE TO USER                       │
│  {                                                               │
│    "recommended_items": [...],                                  │
│    "total_price": "₹ 7,495",                                   │
│    "stylist_note": "These pieces create...",                   │
│    "cache_hit": true/false                                     │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Flows

### Semantic Cache Flow

```
Query: "I have a black shirt, what for wedding?"

1. Generate Embedding
   ├─ Use same model as fashion items (all-MiniLM-L6-v2)
   ├─ Normalize embedding
   └─ Result: 384-dim vector

2. Search Cache DB
   ├─ Similarity search in cache_db ChromaDB
   ├─ Find most similar cached query
   └─ Return: (document, distance_score)

3. Calculate Similarity
   ├─ similarity = 1 - distance
   └─ Example: 1 - 0.12 = 0.88

4. Check Threshold
   ├─ If similarity >= 0.85: CACHE HIT
   └─ If similarity < 0.85: CACHE MISS

5. Return Result
   ├─ Cache Hit: Return cached response JSON
   └─ Cache Miss: Return None (proceed to agent)
```

### Agent Tool Calling Flow

```
Agent receives: "I have a black shirt, what for wedding?"

1. Agent Reasoning (Internal)
   Thought: "User needs formal bottoms for wedding"
   Thought: "Should search for formal pants"
   Thought: "No price mentioned, use default"
   Thought: "No gender mentioned, default to men"

2. Agent Decision
   Action: search_fashion_items
   Action Input: {
     "search_term": "formal black pants wedding",
     "min_price": 0,
     "max_price": 10000,
     "gender": "men"
   }

3. Tool Execution
   [Tool runs vector search with filters]
   
4. Tool Response
   Observation: {
     "success": true,
     "items": [...5 items...],
     "price_range_used": "₹0 - ₹10,000",
     "gender": "men",
     "count": 5
   }

5. Agent Reasoning (Post-Tool)
   Thought: "I have 5 formal pants options"
   Thought: "Need to evaluate fashion compatibility"
   Thought: "Black shirt + black/grey/navy pants work well"
   Thought: "Wedding requires formal style"

6. Agent Final Answer
   Final Answer: {
     "recommended_items": [...],
     "total_price": "₹7,495",
     "stylist_note": "These formal pants..."
   }
```

### Vector Search with Retry Flow

```
Tool Call: search_fashion_items(
  search_term="formal pants",
  min_price=1500,
  max_price=2000,
  gender="men"
)

Attempt 1: Range ₹1,500 - ₹2,000
├─ Semantic search: Get 30 results
├─ Filter by price: 2 items (< 5 needed)
└─ Result: INSUFFICIENT

Attempt 2: Range ₹1,000 - ₹2,500
├─ Semantic search: Get 30 results
├─ Filter by price: 4 items (< 5 needed)
└─ Result: INSUFFICIENT

Attempt 3: Range ₹500 - ₹3,000
├─ Semantic search: Get 30 results
├─ Filter by price: 7 items (>= 5 needed)
└─ Result: SUCCESS

Return: Top 5 items from 7 found
```

---

## Error Handling Flows

### Cache Error Flow
```
Cache Check Fails
   ↓
Log Warning
   ↓
Proceed to Agent (treat as cache miss)
   ↓
Continue normal flow
```

### Agent Error Flow
```
Agent Execution Fails
   ↓
Catch Exception
   ↓
Return Error Response:
{
  "recommended_items": [],
  "total_price": "₹ 0",
  "stylist_note": "An error occurred...",
  "error": "error message"
}
```

### Tool Error Flow
```
Vector Search Fails
   ↓
Return Tool Error:
{
  "success": false,
  "message": "No items found...",
  "items": []
}
   ↓
Agent Receives Error
   ↓
Agent Returns Graceful Response
```

---

## Performance Optimization Flows

### Cache Hit Path (Fast)
```
Request → Cache Check → Cache Hit → Return
Time: ~100-200ms
```

### Cache Miss Path (Slow)
```
Request → Cache Check → Cache Miss → Agent → Tool → Vector Search → Agent Response → Cache Save → Return
Time: ~2-5 seconds (depends on LLM)
```

### Subsequent Similar Request (Fast)
```
Request → Cache Check → Cache Hit (from previous) → Return
Time: ~100-200ms
```

---

## Data Transformation Flow

### Scraping → Storage
```
HTML Element
   ↓ (scraper.py)
Python Dict
   ↓ (cleaner.py)
Validated Dict
   ↓ (embedding.py)
LangChain Document
   ↓
ChromaDB Entry
   ├─ Document: "name - description"
   ├─ Embedding: [0.123, -0.456, ...]
   └─ Metadata: {name, brand, price, ...}
```

### Query → Response
```
User Text Query
   ↓ (api.py)
Pydantic Model
   ↓ (cache_check.py)
Query Embedding
   ↓ (recommender.py)
Agent Input
   ↓ (tool)
Vector Search
   ↓ (agent)
Fashion Evaluation
   ↓ (agent)
JSON Response
   ↓ (api.py)
HTTP Response
```

---

## Monitoring Points

Key points to monitor in production:

1. **Cache Hit Rate**: % of requests served from cache
2. **Agent Latency**: Time for agent to respond
3. **Tool Success Rate**: % of successful vector searches
4. **Price Expansion**: How often price range needs expansion
5. **Error Rate**: % of failed requests
6. **Response Quality**: User feedback on recommendations
