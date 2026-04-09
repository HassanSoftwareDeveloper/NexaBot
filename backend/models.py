from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ProductInfo(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    colors: List[str] = []
    specs: Dict[str, Any] = {}
    shop: Optional[str] = Field(default="default_shop")
    delivery_areas: List[str] = []
    in_stock: bool = True


class DocumentUploadResponse(BaseModel):
    success: bool
    filename: str
    message: str
    products_extracted: int = 0


class QueryRequest(BaseModel):
    question: str
    shop: Optional[str] = None
    top_k: int = 5


class SourceReference(BaseModel):
    text: str
    document: str
    score: float
    page: Optional[int] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceReference] = []
    related_products: List[ProductInfo] = []
    confidence: float = 0.0


class OrderItem(BaseModel):
    product_name: str
    quantity: int = 1
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    product_category: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    specifications: Optional[str] = None


class CustomerInfo(BaseModel):
    full_name: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    whatsapp_number: Optional[str] = None


class PaymentDetails(BaseModel):
    method: str = "COD"
    transaction_id: Optional[str] = None


class OrderRequest(BaseModel):
    customer_info: CustomerInfo
    items: List[OrderItem]
    payment_details: PaymentDetails = PaymentDetails()
    delivery_instructions: Optional[str] = None
    preferred_delivery_date: Optional[str] = None
    preferred_delivery_time: Optional[str] = None
    how_did_you_hear: Optional[str] = None


class OrderResponse(BaseModel):
    success: bool
    order_id: Optional[str] = None
    message: str
    total_amount: Optional[float] = None
    estimated_delivery: Optional[str] = None


class ProductListResponse(BaseModel):
    products: List[ProductInfo]
    total: int
    shop: Optional[str] = None
