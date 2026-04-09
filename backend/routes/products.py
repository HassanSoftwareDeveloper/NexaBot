# products.py
from fastapi import APIRouter, HTTPException, Query
from backend.models import ProductListResponse, ProductInfo
from backend.services.upsell_service import upsell_service
from typing import Optional

router = APIRouter()


@router.get("/list", response_model=ProductListResponse)
async def list_products(
    shop: Optional[str] = None,
    category: Optional[str] = None,
    in_stock_only: bool = False,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """List all products with optional filters and pagination."""
    try:
        products = list(upsell_service.products)

        if shop:
            products = [p for p in products if p.shop and shop.lower() in p.shop.lower()]
        if category:
            products = [p for p in products if p.category and category.lower() in p.category.lower()]
        if in_stock_only:
            products = [p for p in products if p.in_stock]
        if min_price is not None:
            products = [p for p in products if p.price and p.price >= min_price]
        if max_price is not None:
            products = [p for p in products if p.price and p.price <= max_price]

        total = len(products)
        products = products[offset: offset + limit]

        return ProductListResponse(products=products, total=total, shop=shop)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_products(
    q: str,
    limit: int = Query(10, ge=1, le=50),
    category: Optional[str] = None
):
    """Search products by name / description using semantic search."""
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    try:
        results = upsell_service.get_recommendations_by_query(q, top_k=limit * 2)

        if category:
            results = [p for p in results if p.category and category.lower() in p.category.lower()]

        results = results[:limit]

        return {
            "query": q,
            "results": [p.model_dump() for p in results],
            "total": len(results),
            "category_filter": category
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def list_categories():
    """Get all product categories with counts."""
    try:
        counts: dict = {}
        for p in upsell_service.products:
            cat = p.category or "Uncategorized"
            counts[cat] = counts.get(cat, 0) + 1

        categories = [
            {"name": cat, "count": cnt}
            for cat, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]
        return {"categories": categories, "total": len(categories)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shops")
async def list_shops():
    """Get all shops with product counts."""
    try:
        counts: dict = {}
        for p in upsell_service.products:
            shop = p.shop or "Unknown"
            counts[shop] = counts.get(shop, 0) + 1

        shops = [
            {"name": shop, "product_count": cnt}
            for shop, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]
        return {"shops": [s["name"] for s in shops], "details": shops, "total": len(shops)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/featured")
async def get_featured_products(limit: int = Query(10, ge=1, le=50)):
    """Return a random selection of in-stock products."""
    import random
    try:
        in_stock = [p for p in upsell_service.products if p.in_stock]
        featured = random.sample(in_stock, min(limit, len(in_stock))) if in_stock else []
        return {"products": [p.model_dump() for p in featured], "total": len(featured)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price-range")
async def get_price_range():
    """Get min/max price across all products."""
    try:
        prices = [p.price for p in upsell_service.products if p.price]
        if not prices:
            return {"min_price": 0, "max_price": 0, "currency": "PKR"}
        return {
            "min_price": min(prices),
            "max_price": max(prices),
            "currency": "PKR",
            "products_with_prices": len(prices)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dynamic route LAST to avoid swallowing static paths ──────────────────────
@router.get("/{product_name}")
async def get_product_details(product_name: str):
    """Get details for a specific product (fuzzy name match)."""
    try:
        from rapidfuzz import fuzz, process

        if not upsell_service.products:
            raise HTTPException(status_code=404, detail="No products available")

        product_names = [p.name for p in upsell_service.products]
        matches = process.extract(
            product_name, product_names,
            scorer=fuzz.partial_ratio, score_cutoff=60, limit=1
        )

        if not matches:
            raise HTTPException(status_code=404, detail=f"Product '{product_name}' not found")

        best_name = matches[0][0]
        product = next((p for p in upsell_service.products if p.name == best_name), None)

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        similar = upsell_service.get_similar_products(product.name, top_k=3)
        complementary = upsell_service.get_complementary_products(product.name)

        return {
            "product": product.model_dump(),
            "similar_products": [p.model_dump() for p in similar],
            "complementary_products": [p.model_dump() for p in complementary],
            "match_score": matches[0][1]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
