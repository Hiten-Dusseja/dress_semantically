# Architecture Documentation

## System Overview

The Fashion RAG Recommender is built as a multi-stage pipeline combining web scraping, vector embeddings, semantic caching, and agentic LLM reasoning to provide intelligent fashion recommendations.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA COLLECTION LAYER                        │
├─────────────────────────────────────────────────────────────────────┤
│  Playwright Scraper  →  Raw JSON  →  Data Cleaner  →  Clean JSON   │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         EMBEDDING LAYER                              │
├─────────────────────────────────────────────────────────────────────┤
│  Sentence Transformers  →  Vector Embeddings  →  ChromaDB Storage   │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │   FastAPI    │───▶│ Semantic     │───▶│  Recommender │         │
│  │   Server     │    │  Cache       │    │   Agent      │         │
│  └──────────────┘    └──────────────┘    └──────────────┘         │
│         │                   │                     │                  │
│         │                   │                     ↓                  │
│         │                   │            ┌──────────────┐           │
│         │                   │            │ Vector Store │           │
│         │                   │            │   Search     │           │
│         │                   │            └──────────────┘           │
│         │                   │                     │                  │
│         │                   └─────────────────────┘                  │
│         │                                                            │
│         └────────────────▶  JSON Response                           │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Data Collection Layer

#### Scraper (`scraper.py`)
- **Technology**: Playwright (headless browser automation)
- **Purpose**: Extract fashion items from e-commerce websites
- **Target Sites**: The Souled Store, Bewakoof
- **Features**:
  - Lazy-load handling with incremental scrolling
  - Anti-bot detection (user-agent rotation, stealth mode)
  - Popup dismissal
  - Multiple selector fallbacks
  - Screenshot debugging
- **Output**: `scraper_output/fashion_data.json`

#### Cleaner (`cleaner.py`)
- **Purpose**: Normalize and validate scraped data
- **Operations**:
  - Remove duplicates
  - Validate required fields
  - Normalize price formats
  - Clean text data
- **Output**: Cleaned `fashion_data.json`

### 2. Embedding Layer

#### Embedding Generator (`embedding.py`)
- **Technology**: LangChain + Sentence Transformers
- **Model**: `all-MiniLM-L6-v2` (384-dimensional embeddings)
- **Process**:
  1. Load fashion items from JSON
  2. Combine `name + description` as embedding text
  3. Generate vector embeddings
  4. Store in ChromaDB with metadata
- **Storage**: ChromaDB persistent storage at `chroma_db/`
- **Metadata Stored**:
  - name, brand, category, gender
  - price, description
  - product_url, image_url
  - scraped_at timestamp

### 3. Application Layer

#### API Server (`api.py`)
- **Technology**: FastAPI
- **Features**:
  - RESTful endpoints
  - Automatic OpenAPI documentation
  - CORS middleware
  - Request/response validation with Pydantic
- **Endpoints**:
  - `POST /recommend` - Get recommendations
  - `GET /cache/stats` - Cache statistics
  - `POST /cache/reset` - Reset cache
  - `DELETE /cache/clear` - Clear cache
  - `GET /health` - Health check

#### Semantic Cache (`cache_check.py`)
- **Technology**: ChromaDB with embeddings
- **Purpose**: Cache similar queries to reduce LLM calls
- **Mechanism**:
  - Stores query embeddings with response metadata
  - Similarity search with threshold (0.85)
  - Returns cached response if similar query found
- **Storage**: Separate ChromaDB at `cache_db/`
- **Benefits**:
  - Reduced latency (no LLM call needed)
  - Cost savings (fewer API calls)
  - Consistent responses for similar queries

#### Recommender Agent (`recommender.py`)
- **Technology**: LangChain Agents + Groq LLM
- **Model**: Llama 3.3 70B Versatile
- **Architecture**: Agentic with tool calling
- **Components**:

##### Agent System
- **Type**: LangChain `create_agent` (modern v1 API)
- **Capabilities**:
  - Natural language understanding
  - Tool selection and invocation
  - Multi-step reasoning
  - Structured output generation

##### Tool: `search_fashion_items`
- **Purpose**: Search vector database with filters
- **Parameters**:
  - `search_term`: Semantic search query
  - `min_price`: Minimum price filter (default: 0)
  - `max_price`: Maximum price filter (default: 10000)
  - `gender`: Gender filter ("men" or "women", default: "men")
- **Logic**:
  1. Semantic search in ChromaDB
  2. Filter by price range and gender
  3. Auto-expand price range ±500 if insufficient results
  4. Return top 5 items
- **Retry Mechanism**: Up to 5 attempts with expanding price range

##### Agent Workflow
1. **Query Analysis**: Extract clothing type, price range, gender
2. **Tool Invocation**: Call `search_fashion_items` with parameters
3. **Fashion Evaluation**: Apply fashion rules (color, style, occasion)
4. **Response Generation**: Create structured JSON with justifications

## Data Flow

### Request Flow
```
User Query
    ↓
FastAPI Endpoint
    ↓
Semantic Cache Check (ChromaDB similarity search)
    ↓
Cache Hit? ──Yes──▶ Return Cached Response
    │
    No
    ↓
Recommender Agent (Groq LLM)
    ↓
Agent Analyzes Query
    ↓
Agent Calls search_fashion_items Tool
    ↓
Tool Searches ChromaDB (with filters)
    ↓
Tool Returns Items
    ↓
Agent Evaluates & Justifies
    ↓
Agent Returns Structured JSON
    ↓
Save to Cache
    ↓
Return Response to User
```

### Data Storage

#### ChromaDB (Fashion Items)
```
Collection: fashion_items
├── Documents: "name - description" (embedded text)
├── Embeddings: 384-dim vectors
└── Metadata:
    ├── name: string
    ├── brand: string
    ├── category: string (tops/bottoms)
    ├── gender: string (men/women)
    ├── price: string (₹ format)
    ├── description: string
    ├── product_url: string
    ├── image_url: string
    └── scraped_at: timestamp
```

#### ChromaDB (Cache)
```
Collection: query_cache
├── Documents: user queries (embedded)
├── Embeddings: 384-dim vectors
└── Metadata:
    ├── query: original query string
    └── response: JSON string (full recommendation)
```

## Technology Stack

### Core Technologies
- **Python 3.8+**: Primary language
- **LangChain**: Agent framework, tool calling, embeddings
- **Groq**: Fast LLM inference (Llama 3.3 70B)
- **ChromaDB**: Vector database for embeddings
- **FastAPI**: REST API framework
- **Playwright**: Web scraping

### ML/AI Components
- **Sentence Transformers**: Embedding generation
  - Model: `all-MiniLM-L6-v2`
  - Dimension: 384
  - Normalized embeddings
- **Groq LLM**: Agentic reasoning
  - Model: `llama-3.3-70b-versatile`
  - Temperature: 0.7
  - Tool calling enabled

### Supporting Libraries
- **Pydantic**: Data validation
- **Uvicorn**: ASGI server
- **python-dotenv**: Environment management
- **LangSmith**: LLM tracing (optional)

## Design Patterns

### 1. Singleton Pattern
- Embedding models and vector stores initialized once
- Reduces memory usage and initialization time
- Used in: `recommender.py`, `cache_check.py`

### 2. Tool Pattern (LangChain)
- Agent uses tools to interact with external systems
- Decouples reasoning from execution
- Enables retry logic and error handling

### 3. Semantic Caching Pattern
- Cache based on semantic similarity, not exact match
- Improves cache hit rate
- Reduces redundant LLM calls

### 4. Retry with Backoff
- Price range expansion in tool
- Graceful degradation
- Ensures results even with strict filters

### 5. Repository Pattern
- ChromaDB abstracts vector storage
- Easy to swap storage backends
- Consistent interface for queries

## Scalability Considerations

### Current Architecture
- **Single-instance**: Runs on one server
- **In-memory state**: Singleton patterns
- **Local storage**: ChromaDB on disk

### Scaling Strategies

#### Horizontal Scaling
- **Stateless API**: FastAPI can run multiple instances
- **Shared Storage**: Move ChromaDB to distributed vector DB (Pinecone, Weaviate)
- **Load Balancer**: Distribute requests across instances

#### Performance Optimization
- **Batch Processing**: Embed multiple queries at once
- **Connection Pooling**: Reuse LLM connections
- **Async Operations**: Use async/await for I/O
- **Caching Layer**: Redis for hot cache

#### Data Scaling
- **Partitioning**: Split by brand/category/gender
- **Indexing**: Optimize ChromaDB indices
- **Compression**: Reduce embedding dimensions (PCA)

## Security Considerations

### API Security
- **CORS**: Configured for cross-origin requests
- **Rate Limiting**: Should be added for production
- **API Keys**: Environment variables for secrets
- **Input Validation**: Pydantic models

### Data Security
- **No PII**: Fashion data only, no user data
- **Secure Storage**: Local file system (should use encrypted storage in prod)
- **API Key Management**: `.env` file (should use secrets manager in prod)

### LLM Security
- **Prompt Injection**: System prompts are fixed
- **Output Validation**: JSON parsing with error handling
- **Rate Limiting**: Groq API has built-in limits

## Monitoring & Observability

### Current Implementation
- **Console Logging**: Print statements for debugging
- **LangSmith**: Optional LLM tracing
- **Error Handling**: Try-catch blocks with fallbacks

### Production Recommendations
- **Structured Logging**: Use logging library
- **Metrics**: Prometheus for API metrics
- **Tracing**: OpenTelemetry for distributed tracing
- **Alerting**: Monitor cache hit rate, LLM latency, error rates

## Future Enhancements

### Planned Features
1. **User Profiles**: Personalized recommendations
2. **Outfit Builder**: Multi-item combinations
3. **Image Search**: Visual similarity search
4. **Trend Analysis**: Popular items tracking
5. **A/B Testing**: Compare recommendation strategies

### Technical Improvements
1. **Async API**: FastAPI async endpoints
2. **Distributed Cache**: Redis cluster
3. **Vector DB Migration**: Pinecone/Weaviate
4. **Model Fine-tuning**: Custom fashion embeddings
5. **Multi-modal**: Text + image embeddings
