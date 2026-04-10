
import sys
import os

# Add paths for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "services")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime
import time

from backend.config import settings
from backend.routes import upload, query, products, orders

# Create FastAPI app
app = FastAPI(
    title="AI Shopping Assistant API",
    description="Intelligent document-driven product chatbot with vector search and AI responses",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware - Allow frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log request
    print(f"[LOG] {request.method} {request.url.path} - {response.status_code} - {duration:.2f}s")
    
    return response

# Include all routers
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(query.router, prefix="/api/query", tags=["Query"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])

# Root endpoint
@app.get("/", tags=["Home"])
async def root():
    """API root endpoint with system information"""
    return {
        "message": "AI Shopping Assistant API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "upload": "/api/upload",
            "query": "/api/query",
            "products": "/api/products",
            "orders": "/api/orders"
        }
    }

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring"""
    
    # Check if directories exist
    directories_ok = all([
        settings.upload_dir.exists(),
        settings.products_dir.exists(),
        settings.orders_dir.exists(),
        settings.index_dir.exists()
    ])
    
    # Check AI service
    from backend.services.llm_service import llm_service
    ai_service = llm_service.active_service
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "directories": "ok" if directories_ok else "error",
        "ai_service": ai_service,
        "groq_configured": bool(settings.groq_api_key),
        "version": "2.0.0"
    }

# System statistics endpoint
@app.get("/stats", tags=["Statistics"])
async def system_stats():
    """Get system statistics"""
    
    from backend.services.vector_store import vector_store
    from backend.services.upsell_service import upsell_service
    
    # Count files in directories
    upload_files = len(list(settings.upload_dir.glob("*"))) if settings.upload_dir.exists() else 0
    product_files = len(list(settings.products_dir.glob("*.json"))) if settings.products_dir.exists() else 0
    order_files = len(list(settings.orders_dir.glob("*.json"))) if settings.orders_dir.exists() else 0
    
    # Get vector store stats
    vector_stats = vector_store.get_stats()
    
    return {
        "files": {
            "uploads": upload_files,
            "products": product_files,
            "orders": order_files
        },
        "products": {
            "total": len(upsell_service.products),
            "in_stock": sum(1 for p in upsell_service.products if p.in_stock)
        },
        "vector_store": {
            "documents": vector_stats.get("total_documents", 0),
            "indexed": vector_stats.get("index_size", 0)
        },
        "timestamp": datetime.now().isoformat()
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all uncaught exceptions"""
    
    print(f"[ERROR] {str(exc)}")
    print(f"   Path: {request.url.path}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url.path),
            "timestamp": datetime.now().isoformat()
        }
    )

# HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )

    
    
    
# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("\n" + "="*70)
    print("AI Shopping Assistant - Backend Starting")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    print("\n" + "="*70)
    print("AI Shopping Assistant - Backend Shutting Down")
    print("="*70)
    print(f"Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

# Run server
if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level="info"
    )
