"""
Fashion RAG Pipeline - Embedding Generator (LangChain)
Reads scraped fashion data and stores embeddings in ChromaDB using LangChain
"""

import json
import os
from pathlib import Path
from typing import List, Dict

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# ─── Configuration ────────────────────────────────────────────────────────────
SCRAPER_OUTPUT_DIR = "scraper_output"
CHROMA_DB_DIR = "chroma_db"
COLLECTION_NAME = "fashion_items"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, lightweight, good for semantic search

# ─── Read Scraped Data ────────────────────────────────────────────────────────
def load_fashion_data():
    """Load fashion data from fashion_data.json."""
    json_file = Path(SCRAPER_OUTPUT_DIR) / "fashion_data.json"
    
    print(f"\n📂 Reading: {json_file}")
    
    if not json_file.exists():
        print(f"  ✗ File not found: {json_file}")
        return []
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if isinstance(data, list):
            print(f"  ✓ Loaded {len(data)} items")
            return data
        else:
            print(f"  ⚠ File is not a list")
            return []
    except Exception as e:
        print(f"  ✗ Error reading {json_file}: {e}")
        return []


# ─── Convert to LangChain Documents ───────────────────────────────────────────
def create_documents(items: List[Dict]) -> List[Document]:
    """
    Convert fashion items to LangChain Document objects.
    page_content = name + description (for embedding)
    metadata = all other fields
    """
    documents = []
    
    for item in items:
        # Skip items without name
        if not item.get("name"):
            continue
        
        # Create page_content from name + description
        name = item.get("name", "") or ""
        description = item.get("description", "") or ""
        
        name = name.strip() if isinstance(name, str) else ""
        description = description.strip() if isinstance(description, str) else ""
        
        if description:
            page_content = f"{name} - {description}"
        else:
            page_content = name
        
        # Prepare metadata (all other fields)
        metadata = {
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "price": item.get("price", 0) if isinstance(item.get("price"), int) else item.get("price", ""),
            "category": item.get("category", ""),
            "gender": item.get("gender", ""),
            "brand": item.get("brand", ""),
            "product_url": item.get("product_url", ""),
            "image_url": item.get("image_url", ""),
            "scraped_at": item.get("scraped_at", ""),
        }
        
        # Clean up None values (ChromaDB requires strings/ints/floats/bools)
        metadata = {k: (v if v is not None else ("" if isinstance(v, str) else 0)) for k, v in metadata.items()}
        
        # Create Document
        doc = Document(
            page_content=page_content,
            metadata=metadata
        )
        documents.append(doc)
    
    return documents


# ─── Main Pipeline ────────────────────────────────────────────────────────────
def main():
    print("="*70)
    print("  FASHION RAG - EMBEDDING PIPELINE (LangChain)")
    print("="*70)
    
    # Step 1: Load fashion data
    print("\n[1/4] Loading fashion data...")
    items = load_fashion_data()
    
    if not items:
        print("\n✗ No items found! Run the scraper first.")
        return
    
    print(f"\n  Total items loaded: {len(items)}")
    
    # Step 2: Convert to LangChain Documents
    print("\n[2/4] Converting to LangChain Documents...")
    documents = create_documents(items)
    print(f"  ✓ Created {len(documents)} documents")
    
    # Step 3: Initialize embedding model
    print(f"\n[3/4] Loading embedding model: {EMBEDDING_MODEL}...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    print(f"  ✓ Model loaded")
    
    # Step 4: Create ChromaDB vector store
    print(f"\n[4/4] Creating ChromaDB vector store...")
    
    # Delete existing collection if it exists
    if os.path.exists(CHROMA_DB_DIR):
        print(f"  ⚠ Deleting existing ChromaDB at {CHROMA_DB_DIR}")
        import shutil
        shutil.rmtree(CHROMA_DB_DIR)
    
    # Create new vector store with embeddings
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_DB_DIR,
        collection_name=COLLECTION_NAME
    )
    
    print(f"  ✓ Vector store created with {len(documents)} documents")
    
    # Summary
    print("\n" + "="*70)
    print(f"  ✅ COMPLETE!")
    print(f"  Total items embedded: {len(documents)}")
    print(f"  ChromaDB location: {CHROMA_DB_DIR}")
    print(f"  Collection name: {COLLECTION_NAME}")
    
    # Test query
    print("\n  🔍 Testing with sample query...")
    results = vectorstore.similarity_search("black joggers", k=3)
    
    print("\n  Sample results for 'black joggers':")
    for i, doc in enumerate(results):
        metadata = doc.metadata
        print(f"    {i+1}. {metadata['name']} ({metadata['brand']}) - {metadata['category']}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
