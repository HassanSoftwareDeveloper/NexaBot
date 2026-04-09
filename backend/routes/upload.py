#upload.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List, Optional
from pathlib import Path
from backend.config import settings
from backend.models import DocumentUploadResponse
from backend.services.document_processor import document_processor
from backend.services.vector_store import vector_store
from backend.services.upsell_service import upsell_service
import shutil

router = APIRouter()

@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    document_type: Optional[str] = Form(None)
):
    """
    Upload and process multiple documents
    Supports: PDF, DOCX, XLSX, TXT, JSON, CSV
    
    Args:
        files: List of files to upload
        document_type: Optional type hint - 'products', 'business_rules', or 'company_info'
    
    Returns:
        DocumentUploadResponse with success status and extracted products count
    """
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Allowed file extensions
    allowed_extensions = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv', '.txt', '.json']
    
    total_chunks = 0
    total_products = 0
    processed_files = []
    errors = []
    
    for file in files:
        try:
            # Validate file extension
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in allowed_extensions:
                errors.append(f"{file.filename}: Unsupported file type")
                continue
            
            # Validate file size (10MB limit)
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset to beginning
            
            if file_size > settings.max_upload_size:
                errors.append(f"{file.filename}: File too large (max 10MB)")
                continue
            
            # Save uploaded file
            file_path = settings.upload_dir / file.filename
            
            # Handle duplicate filenames
            if file_path.exists():
                base_name = file_path.stem
                counter = 1
                while file_path.exists():
                    file_path = settings.upload_dir / f"{base_name}_{counter}{file_ext}"
                    counter += 1
            
            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            print(f"\n📄 Processing: {file.filename}")
            print(f"   Size: {file_size / 1024:.1f} KB")
            
            # Process document — returns Dict with 'chunks', 'products', 'metadata'
            result = document_processor.process_document(file_path)
            chunks   = result.get('chunks', [])
            products = result.get('products', [])

            # Get or set document type
            if document_type:
                document_processor.document_types[file.filename] = document_type
                doc_type = document_type
            else:
                doc_type = document_processor.document_types.get(file.filename, 'products')
            
            # Add to vector store
            if chunks:
                vector_store.add_documents(chunks)
                total_chunks += len(chunks)
                print(f"✅ Added {len(chunks)} chunks to vector store")
            
            # Save products if extracted
            if products:
                base_name = Path(file.filename).stem
                document_processor.save_products_to_json(products, base_name)
                total_products += len(products)
                print(f"✅ Extracted {len(products)} products")
            
            processed_files.append({
                "filename": file.filename,
                "type": doc_type,
                "chunks": len(chunks),
                "products": len(products)
            })
        
        except Exception as e:
            error_msg = f"{file.filename}: {str(e)}"
            errors.append(error_msg)
            print(f"❌ Error processing {file.filename}: {e}")
            continue
    
    # Save vector store
    if total_chunks > 0:
        vector_store.save_index()
    
    # Reload products
    if total_products > 0:
        upsell_service.load_all_products()
        print(f"✅ Reloaded product catalog: {len(upsell_service.products)} total products")
    
    # Build response message
    if not processed_files:
        raise HTTPException(
            status_code=400,
            detail=f"No files processed successfully. Errors: {'; '.join(errors)}"
        )
    
    message = f"Successfully processed {len(processed_files)} file(s). "
    message += f"Extracted {total_chunks} text chunks"
    
    if total_products > 0:
        message += f" and {total_products} products."
    else:
        message += "."
    
    if errors:
        message += f" Warnings: {'; '.join(errors[:3])}"
    
    return DocumentUploadResponse(
        success=True,
        filename=", ".join([f['filename'] for f in processed_files]),
        message=message,
        products_extracted=total_products
    )

@router.post("/document", response_model=DocumentUploadResponse)
async def upload_single_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None)
):
    """
    Upload single document (for backward compatibility)
    Redirects to multi-file upload
    """
    return await upload_documents(files=[file], document_type=document_type)

@router.get("/stats")
async def get_upload_stats():
    """Get detailed statistics about uploaded documents and products"""
    
    # Vector store stats
    stats = vector_store.get_stats()
    
    # File information
    uploaded_files = list(settings.upload_dir.glob("*"))
    stats['uploaded_files'] = len(uploaded_files)
    stats['files'] = []
    
    # Count by document type
    type_counts = {
        'products': 0,
        'business_rules': 0,
        'company_info': 0,
        'unknown': 0
    }
    
    for f in uploaded_files:
        doc_type = document_processor.document_types.get(f.name, 'unknown')
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        
        stats['files'].append({
            'name': f.name,
            'type': doc_type,
            'size_kb': round(f.stat().st_size / 1024, 2)
        })
    
    # Add type breakdown
    stats['product_docs'] = type_counts['products']
    stats['rules_docs'] = type_counts['business_rules']
    stats['business_docs'] = type_counts['company_info']
    
    # Product information
    stats['total_products'] = len(upsell_service.products)
    stats['in_stock_products'] = sum(1 for p in upsell_service.products if p.in_stock)
    
    # Products by category
    categories = {}
    for product in upsell_service.products:
        cat = product.category or 'Uncategorized'
        categories[cat] = categories.get(cat, 0) + 1
    stats['categories'] = categories
    
    return stats

@router.delete("/clear")
async def clear_all_data():
    """Clear all uploaded documents, products, and vector index"""
    try:
        # Clear vector store
        vector_store.clear_index()
        vector_store.save_index()
        print("✅ Cleared vector store")
        
        # Clear uploaded files
        file_count = 0
        for file in settings.upload_dir.glob("*"):
            file.unlink()
            file_count += 1
        print(f"✅ Deleted {file_count} uploaded files")
        
        # Clear product JSON files
        product_count = 0
        for file in settings.products_dir.glob("*.json"):
            file.unlink()
            product_count += 1
        print(f"✅ Deleted {product_count} product files")
        
        # Clear processor cache
        document_processor.products_cache = []
        document_processor.document_types = {}
        
        # Reload (empty) products
        upsell_service.load_all_products()
        print("✅ Reloaded empty product catalog")
        
        return {
            "success": True,
            "message": f"Cleared {file_count} documents and {product_count} product files",
            "deleted": {
                "documents": file_count,
                "products": product_count
            }
        }
    
    except Exception as e:
        print(f"❌ Error clearing data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing data: {str(e)}")

@router.get("/document-types")
async def get_document_types():
    """Get classification of all uploaded documents"""
    
    # Group by type
    by_type = {
        'products': [],
        'business_rules': [],
        'company_info': [],
        'unknown': []
    }
    
    for filename, doc_type in document_processor.document_types.items():
        by_type[doc_type].append(filename)
    
    return {
        "documents": document_processor.document_types,
        "by_type": by_type,
        "total": len(document_processor.document_types),
        "counts": {
            "products": len(by_type['products']),
            "business_rules": len(by_type['business_rules']),
            "company_info": len(by_type['company_info']),
            "unknown": len(by_type['unknown'])
        }
    }

@router.delete("/document/{filename}")
async def delete_document(filename: str):
    """Delete a specific document and its associated data"""
    try:
        # Find and delete the file
        file_path = settings.upload_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
        
        # Delete the file
        file_path.unlink()
        
        # Remove from document types
        if filename in document_processor.document_types:
            del document_processor.document_types[filename]
        
        # If it's a product file, delete associated JSON
        base_name = Path(filename).stem
        product_json = settings.products_dir / f"{base_name}.json"
        if product_json.exists():
            product_json.unlink()
            # Reload products
            upsell_service.load_all_products()
        
        print(f"✅ Deleted document: {filename}")
        
        return {
            "success": True,
            "message": f"Document '{filename}' deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f" Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")