from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    # ---------------- Backend Settings ----------------
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    
    # ---------------- Directory Settings ----------------
    upload_dir: Path = Path("./data/uploads")
    index_dir: Path = Path("./data/indexes")
    products_dir: Path = Path("./data/products")
    orders_dir: Path = Path("./data/orders")
    
    # ---------------- Upload Limits ----------------
    max_upload_size: int = 10 * 1024 * 1024  # 10MB in bytes
    allowed_file_types: list = [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt", ".json"]

    # ---------------- Model / AI Settings ----------------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "google/flan-t5-base"
    max_tokens: int = 512
    temperature: float = 0.7  # Changed from 0.9 to 0.7 for more consistent responses

    # ---------------- Vector Store Settings ----------------
    faiss_index_type: str = "Flat"
    top_k_results: int = 5
    similarity_threshold: float = 0.3  # Minimum similarity score
    chunk_size: int = 500  # Words per chunk
    chunk_overlap: int = 50  # Overlap between chunks

    # ---------------- API Keys from .env ----------------
    groq_api_key: str = ""
    together_api_key: str = ""
    huggingface_api_key: str = ""
    
    # ---------------- Order Settings ----------------
    order_id_prefix: str = "ORD"
    estimated_delivery_days: int = 5
    free_shipping_threshold: float = 5000.0  # PKR
    
    # ---------------- Business Settings ----------------
    business_name: str = "AI Shopping Assistant"
    support_email: str = "support@aistore.com"
    support_phone: str = "0300-1234567"
    cities_served: list = ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad"]
    
    # ---------------- Session Settings ----------------
    session_timeout: int = 3600  # 1 hour in seconds
    max_chat_history: int = 50  # Maximum messages to keep in chat history

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Ensure all data directories exist
        for directory in [self.upload_dir, self.index_dir, self.products_dir, self.orders_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            print(f" Directory ready: {directory}")
        
        # Validate API keys
        self._validate_api_keys()
    
    def _validate_api_keys(self):
        """Validate that at least one AI API key is configured"""
        has_api_key = False
        
        if self.groq_api_key and len(self.groq_api_key) > 20:
            print(" Groq API key configured")
            has_api_key = True
        
        if self.together_api_key:
            print(" Together AI API key configured")
            has_api_key = True
        
        if self.huggingface_api_key:
            print(" HuggingFace API key configured")
            has_api_key = True
        
        if not has_api_key:
            print(" WARNING: No AI API keys configured! System will use fallback responses.")
            print("   Add GROQ_API_KEY to .env file for best performance.")
    
    def get_file_extension_allowed(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        ext = Path(filename).suffix.lower()
        return ext in self.allowed_file_types
    
    def get_order_id(self) -> str:
        """Generate unique order ID"""
        import uuid
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"{self.order_id_prefix}-{timestamp}-{unique_id}"

# Create global settings instance
settings = Settings()

# Print startup banner
print("\n" + "="*60)
print("🤖 AI Shopping Assistant - Backend Configuration")
print("="*60)
print(f"📁 Upload Directory: {settings.upload_dir}")
print(f"📁 Products Directory: {settings.products_dir}")
print(f"📁 Orders Directory: {settings.orders_dir}")
print(f"🧠 Embedding Model: {settings.embedding_model}")
print(f"🌐 Server: {settings.backend_host}:{settings.backend_port}")
print("="*60 + "\n")