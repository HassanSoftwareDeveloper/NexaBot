

"""
ENHANCED UPSELL SERVICE - Smart Product Recommendations
- Better product matching and recommendations
- Works with any product type
- Smart similarity detection
- Category-based recommendations
"""

from typing import List, Dict, Optional
from backend.models import ProductInfo
from backend.services.embedding_service import embedding_service
import numpy as np
import json
from pathlib import Path
from backend.config import settings
import logging


logger = logging.getLogger(__name__)

class UpsellService:
    def __init__(self):
        self.products = []
        self.product_embeddings = None
        self.categories = {}
        self.load_all_products()
    
    def load_all_products(self):
        """Load all products from JSON files with validation"""
        self.products = []
        
        if not settings.products_dir.exists():
            logger.warning(f"Products directory not found: {settings.products_dir}")
            return
        
        json_files = list(settings.products_dir.glob("*.json"))
        
        if not json_files:
            logger.warning("No product JSON files found")
            return
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    products_data = json.load(f)
                    
                    # Handle both list and single product formats
                    if isinstance(products_data, list):
                        for p in products_data:
                            self._add_product(p)
                    elif isinstance(products_data, dict):
                        self._add_product(products_data)
                        
            except Exception as e:
                logger.error(f"Error loading {json_file.name}: {e}")
                continue
        
        if self.products:
            self._generate_product_embeddings()
            self._organize_by_category()
        
        logger.info(f" Loaded {len(self.products)} products from {len(json_files)} files")
    
    def _add_product(self, product_data: Dict):
        """Add a product with validation"""
        try:
            # Skip non-product entries
            if not product_data.get('name'):
                return
            
            # Filter out non-product documents
            name_lower = product_data.get('name', '').lower()
            skip_terms = ['business rules', 'executive', 'company overview', 
                         'policy', 'terms and conditions', 'about us']
            
            if any(term in name_lower for term in skip_terms):
                return
            
            # Create ProductInfo object
            product = ProductInfo(**product_data)
            self.products.append(product)
            
        except Exception as e:
            logger.error(f"Error adding product {product_data.get('name', 'Unknown')}: {e}")
    
    def _organize_by_category(self):
        """Organize products by category for faster access"""
        self.categories = {}
        
        for product in self.products:
            category = product.category or "General"
            
            if category not in self.categories:
                self.categories[category] = []
            
            self.categories[category].append(product)
        
        logger.info(f" Organized into {len(self.categories)} categories")
    
    def _generate_product_embeddings(self):
        """Generate embeddings for intelligent product matching"""
        try:
            # Create rich text representation of each product
            product_texts = []
            self.embedding_metadata = [] 
            
            for i, product in enumerate(self.products):
                # Combine all relevant information
                text_parts = [product.name]
                
                if product.description:
                    text_parts.append(product.description)
                
                if product.category:
                    text_parts.append(product.category)
                
                if product.colors:
                    text_parts.append(' '.join(product.colors))
                
                if hasattr(product, 'tags') and product.tags:
                    text_parts.append(' '.join(product.tags))
                
                # Create combined text
                product_text = ' '.join(text_parts)
                product_texts.append(product_text)
                
            # Save metadata for this embedding
                self.embedding_metadata.append({
                "name": product.name,
                "category": product.category,
                "index": i
            })
            
            
            # Generate embeddings
            logger.info(f" Generating embeddings for {len(product_texts)} products...")
            self.product_embeddings = embedding_service.encode_texts(product_texts)
            logger.info(" Product embeddings generated successfully")
            
        except Exception as e:
            logger.error(f" Error generating embeddings: {e}")
            self.product_embeddings = None
    
    def get_similar_products(self, product_name: str, top_k: int = 3) -> List[ProductInfo]:
        """
        Get similar products based on product name
        Uses semantic similarity with embeddings
        """
        
        if not self.products or self.product_embeddings is None:
            logger.warning("No products or embeddings available")
            return []
        
        # Find the reference product
        reference_product = None
        reference_idx = None
        
        product_name_lower = product_name.lower()
        
        for idx, product in enumerate(self.products):
            if product_name_lower in product.name.lower():
                reference_product = product
                reference_idx = idx
                break
        
        if reference_idx is None:
            # If exact product not found, use query-based recommendations
            logger.info(f"Product '{product_name}' not found, using query-based search")
            return self.get_recommendations_by_query(product_name, top_k)
        
        try:
            # Get reference embedding
            reference_embedding = self.product_embeddings[reference_idx:reference_idx+1]
            
            # Calculate similarities using cosine similarity
            similarities = np.dot(self.product_embeddings, reference_embedding.T).flatten()
            
            # Get top-k similar (excluding the reference itself)
            similar_indices = np.argsort(similarities)[::-1]
            
            # Filter out the reference product and get top_k
            similar_indices = [idx for idx in similar_indices if idx != reference_idx][:top_k]
            
            similar_products = [self.products[idx] for idx in similar_indices]
            
            logger.info(f"Found {len(similar_products)} similar products to '{product_name}'")
            return similar_products
            
        except Exception as e:
            logger.error(f"Error finding similar products: {e}")
            return []
    
    def get_recommendations_by_query(self, query: str, top_k: int = 3) -> List[ProductInfo]:
        """
        Get product recommendations based on a text query
        Very useful for natural language searches
        """
        
        if not self.products or self.product_embeddings is None:
            logger.warning("No products or embeddings available")
            return []
        
        try:
            # Generate query embedding
            query_embedding = embedding_service.encode_query(query)
            
            # Calculate similarities
            query_norm = np.linalg.norm(query_embedding)
            similarities = (self.product_embeddings @ query_embedding.T).flatten()
            similarities /= query_norm

            # Get top-k
            
            top_indices=similarities.argsort()[::-1][:top_k]
            recommended_products = [self.products[idx] for idx in top_indices]
            
            logger.info(f"Found {len(recommended_products)} products matching query: '{query}'")
            return recommended_products
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []
    
    def get_category_recommendations(self, category: str, top_k: int = 5) -> List[ProductInfo]:
        """Get products from a specific category"""
        
        # Try exact match first
        if category in self.categories:
            products = self.categories[category]
            return products[:top_k]
        
        # Try fuzzy match
        category_lower = category.lower()
        
        for cat_name, products in self.categories.items():
            if category_lower in cat_name.lower() or cat_name.lower() in category_lower:
                return products[:top_k]
        
        logger.info(f"Category '{category}' not found")
        return []
    
    def get_shop_products(self, shop: str, top_k: int = 10) -> List[ProductInfo]:
        """Get products from a specific shop (if shop field exists)"""
        
        shop_lower = shop.lower()
        
        shop_products = [
            p for p in self.products 
            if hasattr(p, 'shop') and p.shop and shop_lower in p.shop.lower()
        ]
        
        return shop_products[:top_k]
    
    def get_complementary_products(self, product_name: str, top_k: int = 3) -> List[ProductInfo]:
        """
        Get complementary products using smart rules
        Works for various product types
        """
        
        product_name_lower = product_name.lower()
        recommendations = []
        
        # Find the product first
        current_product = None
        for p in self.products:
            if product_name_lower in p.name.lower():
                current_product = p
                break
        
        if current_product and current_product.category:
            # Get products from same category but different type
            category_products = self.get_category_recommendations(current_product.category, 10)
            
            # Filter out the current product
            category_products = [p for p in category_products if p.name != current_product.name]
            
            if category_products:
                recommendations.extend(category_products[:top_k])
        
        # If not enough recommendations, use similarity
        if len(recommendations) < top_k:
            similar = self.get_similar_products(product_name, top_k - len(recommendations))
            recommendations.extend(similar)
        
        return recommendations[:top_k]
    
    def get_products_by_price_range(self, min_price: float, max_price: float, 
                                   top_k: int = 10) -> List[ProductInfo]:
        """Get products within a price range"""
        
        filtered_products = [
            p for p in self.products
            if p.price and min_price <= p.price <= max_price
        ]
        
        # Sort by price
        filtered_products.sort(key=lambda p: p.price)
        
        return filtered_products[:top_k]
    
    def get_all_categories(self) -> List[str]:
        """Get list of all categories"""
        return list(self.categories.keys())
    
    def get_product_by_name(self, name: str) -> Optional[ProductInfo]:
        """Get exact product by name (case-insensitive)"""
        
        name_lower = name.lower()
        
        for product in self.products:
            if product.name.lower() == name_lower:
                return product
        
        # Try partial match
        for product in self.products:
            if name_lower in product.name.lower():
                return product
        
        return None
    
    def search_products(self, search_term: str, top_k: int = 10) -> List[ProductInfo]:
        """
        Search products by name, description, category
        More flexible than exact matching
        """
        
        search_lower = search_term.lower()
        results = []
        
        for product in self.products:
            # Check name
            if search_lower in product.name.lower():
                results.append((product, 3))  # High priority
                continue
            
            # Check description
            if product.description and search_lower in product.description.lower():
                results.append((product, 2))  # Medium priority
                continue
            
            # Check category
            if product.category and search_lower in product.category.lower():
                results.append((product, 1))  # Low priority
                continue
        
        # Sort by priority and return
        results.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in results[:top_k]]
    
    def get_statistics(self) -> Dict:
        """Get statistics about products"""
        
        stats = {
            'total_products': len(self.products),
            'total_categories': len(self.categories),
            'categories': {},
            'has_embeddings': self.product_embeddings is not None,
            'price_range': {
                'min': None,
                'max': None,
                'average': None
            }
        }
        
        # Category counts
        for category, products in self.categories.items():
            stats['categories'][category] = len(products)
        
        # Price statistics
        prices = [p.price for p in self.products if p.price and p.price > 0]
        
        if prices:
            stats['price_range']['min'] = min(prices)
            stats['price_range']['max'] = max(prices)
            stats['price_range']['average'] = sum(prices) / len(prices)
        
        return stats

# Global instance
upsell_service = UpsellService()