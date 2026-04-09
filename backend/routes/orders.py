"""
Order Routes
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime
from backend.models import OrderRequest, OrderResponse
from backend.services.order_service import order_service

router = APIRouter()


@router.post("/place", response_model=OrderResponse)
async def place_order(order_request: OrderRequest):
    """Place a new order."""
    try:
        result = order_service.place_order(order_request.model_dump())
        return OrderResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_order_statistics():
    """Get order statistics."""
    try:
        stats = order_service.get_order_statistics()
        return {"success": True, "statistics": stats, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_orders(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Export orders to Excel."""
    try:
        export_path = order_service.export_orders(start_date, end_date)
        return {"success": True, "file_path": str(export_path), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/status/{order_id}")
async def update_order_status(order_id: str, status: str):
    """Update order status."""
    valid = ["pending", "processing", "shipped", "delivered", "cancelled"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(valid)}")
    try:
        result = order_service.update_order_status(order_id, status)
        return {"success": True, "order_id": order_id, "new_status": status,
                "message": result.get("message"), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{order_id}")
async def get_order_details(order_id: str):
    """Get a specific order by ID."""
    import json
    from backend.config import settings

    json_file = settings.orders_dir / f"{order_id}.json"
    if not json_file.exists():
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            order_data = json.load(f)
        return {"success": True, "order": order_data, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
