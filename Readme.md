# Fashion RAG Recommender 👔

AI-powered fashion recommendation system using RAG (Retrieval Augmented Generation) with semantic caching.

## Features

- 🤖 **Agentic LLM** - Intelligent agent that understands fashion queries
- 🔍 **Semantic Search** - Vector-based similarity search using ChromaDB
- 💰 **Price Filtering** - Automatic price range expansion if no results found
- 👔 **Gender Filtering** - Separate recommendations for men and women
- ⚡ **Semantic Caching** - Fast responses for similar queries
- 🎨 **Stylist Justification** - AI explains why items work together
- 🚀 **FastAPI** - RESTful API with automatic documentation

## Architecture

```
User Query → Semantic Cache Check → Agent (LLM) → Tool (Vector Search) → Stylist Justification → JSON Response
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright

Playwright is required for web scraping:

```bash
playwright install
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_groq_api_key_here
LANGCHAIN_API_KEY=your_langsmith_api_key_here  # Optional for tracing
```

### 4. Run the Scraper

Scrape fashion items from websites (The Souled Store, Bewakoof):

```bash
python scraper.py
```

This will create `scraper_output/fashion_data.json` with scraped items.

### 5. Run the Cleaner

Clean and normalize the scraped data:

```bash
python cleaner.py
```

This processes the data and prepares it for embedding generation.

### 6. Generate Embeddings

Create vector embeddings and store in ChromaDB:

```bash
python embedding.py
```

This will:
- Read `scraper_output/fashion_data.json`
- Generate embeddings for name + description
- Store in `chroma_db/` directory

### 7. Start the API Server

```bash
python api.py
```

The server will start at `http://localhost:8000`

### 8. Access API Documentation

Visit the interactive API docs:

```
http://localhost:8000/docs
```

## API Endpoints

### POST `/recommend`

Get fashion recommendations for a query.

**Request:**
```json
{
  "query": "I have a black shirt, what should I buy for bottoms to wear on a wedding day?",
  "use_cache": true
}
```

**Response:**
```json
{
  "recommended_items": [
    {
      "name": "Formal Black Pants",
      "brand": "The Souled Store",
      "price": "₹ 1,499",
      "product_url": "https://...",
      "image_url": "https://...",
      "why_this_works": "Perfect formal match for wedding occasions"
    }
  ],
  "total_price": "₹ 7,495",
  "stylist_note": "These pieces create an elegant wedding ensemble...",
  "cache_hit": false
}
```

### GET `/cache/stats`

Get cache statistics.

### POST `/cache/reset`

Reset the semantic cache (safer than clear).

### DELETE `/cache/clear`

Clear all cached queries.

### GET `/health`

Health check endpoint.

## Query Examples

### Basic Recommendation
```
"I have a black shirt, what should I buy for bottoms to wear on a wedding day?"
```

### With Price Range
```
"Show me casual joggers under 2000 rupees"
```

### With Gender
```
"I need formal pants for women between 1500 and 3000 rupees"
```

### Direct Search
```
"Show me black joggers"
```

## Project Structure

```
.
├── scraper.py            # Web scraper for fashion items
├── cleaner.py            # Data cleaning and normalization
├── embedding.py          # Embedding generation pipeline
├── recommender.py        # Agentic recommendation engine
├── cache_check.py        # Semantic caching system
├── api.py                # FastAPI server
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables
├── .gitignore            # Git ignore rules
├── scraper_output/       # Scraped data directory
│   └── fashion_data.json
├── chroma_db/            # Vector database (created after embedding.py)
└── cache_db/             # Semantic cache (created after first API call)
```

## Technologies Used

- **LangChain** - Agent framework and tool calling
- **Groq** - Fast LLM inference (Llama 3.3 70B)
- **ChromaDB** - Vector database for embeddings
- **Sentence Transformers** - Embedding model (all-MiniLM-L6-v2)
- **FastAPI** - REST API framework
- **Playwright** - Web scraping
- **LangSmith** - LLM tracing and monitoring (optional)

## How It Works

1. **User sends query** to `/recommend` endpoint
2. **Semantic cache check** - Searches for similar past queries (similarity > 0.85)
3. **If cache miss:**
   - Agent analyzes query and extracts: clothing type, price range, gender
   - Agent calls `search_fashion_items` tool with parameters
   - Tool searches ChromaDB with filters (price + gender)
   - Tool auto-expands price range ±500 if no results (up to 5 attempts)
   - Agent evaluates results using fashion rules
   - Agent returns structured JSON with justification
4. **Response cached** for future similar queries
5. **User receives** recommendations with stylist notes

## Semantic Caching

The system uses semantic similarity to cache responses:
- Queries with similarity > 0.85 are considered cache hits
- Saves LLM calls and reduces latency
- Example: "black shirt for wedding" ≈ "black shirt wedding bottoms"

## Development

### Run in Development Mode

```bash
# With auto-reload
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### Test Recommender Directly

```bash
python recommender.py
```

### Test Cache System

```bash
python cache_check.py
```

## Troubleshooting

### Cache Lock Error on Windows

If you get "file is being used by another process" when clearing cache, use:
```
POST /cache/reset
```
instead of `DELETE /cache/clear`

### No Items Found

- Check if embeddings were generated: `ls chroma_db/` (or `dir chroma_db` on Windows)
- Verify scraped data exists: `ls scraper_output/fashion_data.json`
- Try broader price range or different gender

### LLM Errors

- Verify `GROQ_API_KEY` is set in `.env`
- Check Groq API rate limits
- Try reducing query complexity

### Scraper Issues

- Ensure Playwright is installed: `playwright install`
- Check internet connection
- Sites may have changed their structure - update selectors in `scraper.py`

## License

MIT

## Contributing

Pull requests welcome! Please ensure:
- Code follows existing style
- Add tests for new features
- Update README for new functionality
