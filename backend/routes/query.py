# query.py

from fastapi import APIRouter, HTTPException, Header
from backend.models import QueryRequest, QueryResponse
from backend.services.chatbot_service import chatbot_service
from backend.services.upsell_service import upsell_service
from typing import Optional
import uuid

router = APIRouter()

@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    x_session_id: Optional[str] = Header(None)
):
    """
    Ask a question and get an intelligent AI-powered answer
    
    Features:
    - Natural language understanding
    - Handles greetings, FAQ, product queries
    - Fuzzy product matching (handles typos)
    - Context-aware responses
    - Product recommendations
    
    Args:
        request: QueryRequest with question, shop filter, and top_k
        x_session_id: Optional session ID for conversation tracking
    
    Returns:
        QueryResponse with answer, sources, and related products
    """
    
    try:
        # Validate question
        if not request.question or len(request.question.strip()) < 2:
            raise HTTPException(
                status_code=400,
                detail="Question must be at least 2 characters long"
            )
        
        # Generate or use provided session ID
        session_id = x_session_id or str(uuid.uuid4())
        
        print(f"\n💬 Query from session {session_id[:8]}: {request.question}")
        
        # Get answer from chatbot service
        response = chatbot_service.answer_query(
            question=request.question,
            top_k=request.top_k,
            shop_filter=request.shop,
            session_id=session_id
        )
        
        print(f"✅ Response generated: {len(response.answer)} chars, {len(response.related_products)} products")
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing query: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@router.get("/suggestions/{product_name}")
async def get_suggestions(product_name: str, limit: int = 3):
    """
    Get product recommendations and upsells
    
    Returns:
    - Similar products (based on embeddings)
    - Complementary products (based on rules)
    
    Args:
        product_name: Name of the product to find suggestions for
        limit: Maximum number of suggestions (default: 3)
    
    Returns:
        Dictionary with similar_products and complementary_products lists
    """
    try:
        if not product_name or len(product_name.strip()) < 2:
            raise HTTPException(
                status_code=400,
                detail="Product name must be at least 2 characters"
            )
        
        # Get similar products
        similar = upsell_service.get_similar_products(product_name, top_k=limit)
        
        # Get complementary products
        complementary = upsell_service.get_complementary_products(product_name)
        
        print(f"💡 Suggestions for '{product_name}': {len(similar)} similar, {len(complementary)} complementary")
        
        return {
            "product_name": product_name,
            "similar_products": [p.model_dump() for p in similar],
            "complementary_products": [p.model_dump() for p in complementary],
            "total_suggestions": len(similar) + len(complementary)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting suggestions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting suggestions: {str(e)}"
        )

@router.get("/search/{query}")
async def search_products(query: str, limit: int = 10):
    """
    Search products by query string
    
    Uses fuzzy matching and semantic search
    
    Args:
        query: Search query
        limit: Maximum results (default: 10)
    
    Returns:
        List of matching products
    """
    try:
        if not query or len(query.strip()) < 2:
            raise HTTPException(
                status_code=400,
                detail="Search query must be at least 2 characters"
            )
        
        # Search using upsell service
        results = upsell_service.get_recommendations_by_query(query, top_k=limit)
        
        print(f"🔍 Search '{query}': Found {len(results)} products")
        
        return {
            "query": query,
            "results": [p.model_dump() for p in results],
            "total": len(results)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error searching products: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error searching: {str(e)}"
        )

@router.get("/categories")
async def get_categories():
    """
    Get all product categories
    
    Returns:
        List of unique categories with product counts
    """
    try:
        # Get all products
        products = upsell_service.products
        
        # Count by category
        categories = {}
        for product in products:
            cat = product.category or 'Uncategorized'
            if cat not in categories:
                categories[cat] = {
                    'name': cat,
                    'count': 0,
                    'products': []
                }
            categories[cat]['count'] += 1
            categories[cat]['products'].append(product.name)
        
        return {
            "categories": list(categories.values()),
            "total_categories": len(categories)
        }
    
    except Exception as e:
        print(f"❌ Error getting categories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting categories: {str(e)}"
        )

@router.post("/feedback")
async def submit_feedback(
    session_id: str,
    question: str,
    answer: str,
    rating: int,
    comment: Optional[str] = None
):
    """
    Submit feedback on chatbot response
    
    Args:
        session_id: Session identifier
        question: Original question
        answer: Generated answer
        rating: Rating 1-5
        comment: Optional feedback comment
    """
    try:
        if not 1 <= rating <= 5:
            raise HTTPException(
                status_code=400,
                detail="Rating must be between 1 and 5"
            )
        
        # Save feedback to file
        from datetime import datetime
        import json
        from pathlib import Path
        
        feedback_dir = Path.cwd() / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        feedback_file = feedback_dir / f"feedback_{session_id}.json"
        
        feedback_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer[:200],  # Truncate for storage
            "rating": rating,
            "comment": comment
        }
        
        with open(feedback_file, 'w') as f:
            json.dump(feedback_data, f, indent=2)
        
        print(f"📝 Feedback received: {rating}/5 stars")
        
        return {
            "success": True,
            "message": "Thank you for your feedback!"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error saving feedback: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error saving feedback: {str(e)}"
        )