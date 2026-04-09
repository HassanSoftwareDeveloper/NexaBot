#llm_service.py

import requests
import os
from typing import List, Dict, Optional, Any, Tuple
import json
import time
import logging
from datetime import datetime, timedelta
from functools import wraps
from backend.services.embedding_service import embedding_service


logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple rate limiter for free APIs"""
    def __init__(self):
        self.call_history = {}
        self.limits = {
            'groq': {'calls': 30, 'period': 60},  # 30/min
            'deepseek': {'calls': 60, 'period': 60},  # 60/min
            'openrouter': {'calls': 20, 'period': 60},  # 20/min
            'together': {'calls': 50, 'period': 60},  # 50/min
            'huggingface': {'calls': 30, 'period': 60}  # 30/min
        }
    
    def can_call(self, provider: str) -> bool:
        """Check if we can make a call to this provider"""
        if provider not in self.limits:
            return True
        
        now = datetime.now()
        if provider not in self.call_history:
            self.call_history[provider] = []
        
        # Remove old calls outside the time window
        limit_config = self.limits[provider]
        cutoff = now - timedelta(seconds=limit_config['period'])
        self.call_history[provider] = [
            t for t in self.call_history[provider] if t > cutoff
        ]
        
        # Check if under limit
        return len(self.call_history[provider]) < limit_config['calls']
    
    def record_call(self, provider: str):
        """Record a successful call"""
        if provider not in self.call_history:
            self.call_history[provider] = []
        self.call_history[provider].append(datetime.now())

rate_limiter = RateLimiter()

class LLMService:
    def __init__(self):
        """Initialize with ALL free API providers"""
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        # Load ALL available API keys
        self.api_keys = {
            'groq': os.getenv("GROQ_API_KEY", ""),
            'deepseek': os.getenv("DEEPSEEK_API_KEY", ""),
            'openrouter': os.getenv("OPENROUTER_API_KEY", ""),
            'together': os.getenv("TOGETHER_API_KEY", ""),
            'huggingface': os.getenv("HUGGINGFACE_API_KEY", ""),
            'openai': os.getenv("OPENAI_API_KEY", "")  # Backup if you have it
        }
        
        # API endpoints
        self.endpoints = {
            'groq': 'https://api.groq.com/openai/v1/chat/completions',
            'deepseek': 'https://api.deepseek.com/v1/chat/completions',
            'openrouter': 'https://openrouter.ai/api/v1/chat/completions',
            'together': 'https://api.together.xyz/v1/chat/completions',
            'huggingface': 'https://api-inference.huggingface.co/models',
            'openai': 'https://api.openai.com/v1/chat/completions'
        }
        
        # Model configurations for each provider
        self.models = {
            'groq': {
                'fast': 'llama-3.1-8b-instant',
                'standard': 'llama-3.3-70b-versatile',
                'complex': 'llama-3.1-70b-versatile'
            },
            'deepseek': {
                'fast': 'deepseek-chat',
                'standard': 'deepseek-chat',
                'complex': 'deepseek-chat'
            },
            'openrouter': {
                'fast': 'qwen/qwen-2.5-7b-instruct:free',
                'standard': 'google/gemini-2.0-flash-exp:free',
                'complex': 'qwen/qwen-2.5-72b-instruct:free'
            },
            'together': {
                'fast': 'meta-llama/Llama-3.2-3B-Instruct-Turbo',
                'standard': 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo',
                'complex': 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo'
            },
            'huggingface': {
                'fast': 'mistralai/Mistral-7B-Instruct-v0.2',
                'standard': 'HuggingFaceH4/zephyr-7b-beta',
                'complex': 'HuggingFaceH4/zephyr-7b-beta'
            }
        }
        
        # Determine available providers
        self.available_providers = self._get_available_providers()
        
        if not self.available_providers:
            logger.warning("⚠️ No API keys configured - using fallback mode")
            self.active_service = "fallback"
        else:
            self.active_service = self.available_providers[0]
            logger.info(f"✅ Active providers: {', '.join(self.available_providers)}")
        
        # Response configuration
        self.max_tokens = 2000
        self.temperature = 0.7
        self.max_retries = 3
        
        # Statistics
        self.request_count = 0
        self.error_count = 0
        self.provider_usage = {p: 0 for p in self.endpoints.keys()}
    
    def _get_available_providers(self) -> List[str]:
        """Get list of providers with valid API keys"""
        available = []
        
        for provider, key in self.api_keys.items():
            if key and len(key) > 10:  # Basic validation
                available.append(provider)
                logger.info(f"✅ {provider.upper()} API configured")
        
        # Sort by preference (fastest/most reliable first)
        priority = ['groq', 'deepseek', 'together', 'openrouter', 'huggingface', 'openai']
        available.sort(key=lambda x: priority.index(x) if x in priority else 999)
        
        return available
    
    def _should_use_fast_model(self, question: str) -> bool:
        """Determine if query can use fast model"""
        fast_indicators = [
            "price", "cost", "how much", "kitna", "available", "in stock",
            "color", "size", "delivery", "payment", "hello", "hi", "thanks"
        ]
        
        q_lower = question.lower()
        return len(question.split()) <= 10 and any(ind in q_lower for ind in fast_indicators)
    
    def _should_use_complex_model(self, question: str) -> bool:
        """Determine if query needs complex reasoning"""
        complex_indicators = [
            "compare", "comparison", "difference", "versus", "vs",
            "which is better", "recommend", "analyze", "explain why"
        ]
        
        q_lower = question.lower()
        return any(ind in q_lower for ind in complex_indicators) or len(question.split()) > 25
    
    def _select_model_tier(self, question: str) -> str:
        """Select model tier: fast, standard, or complex"""
        if self._should_use_complex_model(question):
            return 'complex'
        if self._should_use_fast_model(question):
            return 'fast'
        return 'standard'
    
    def generate_response(
        self, 
        question: str, 
        context: str = "", 
        products: Optional[List[Dict]] = None,
        conversation_history: str = ""
    ) -> str:
        """
        🤖 Generate response using ANY available free API
        Automatically tries providers until one succeeds
        """
        
        logger.info(f"🤖 Generating AI response for: '{question[:50]}...'")
        
        if not self.available_providers:
            logger.warning("No API providers available, using fallback")
            return self._intelligent_fallback(question, context, products)
        
        # Select model tier
        model_tier = self._select_model_tier(question)
        logger.info(f"🎯 Model tier: {model_tier}")
        
        # Build prompts
        system_prompt, user_prompt = self._build_universal_prompt(
            question, context, products, conversation_history
        )
        
        # Try each available provider with rate limiting
        last_error = None
        
        for provider in self.available_providers:
            # Check rate limits
            if not rate_limiter.can_call(provider):
                logger.warning(f"⏳ {provider} rate limited, trying next provider")
                continue
            
            try:
                logger.info(f"🔄 Trying {provider.upper()}...")
                
                # Call the provider
                response = self._call_provider(
                    provider=provider,
                    model_tier=model_tier,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )
                
                # Validate response
                if response and len(response.strip()) > 30:
                    rate_limiter.record_call(provider)
                    self.request_count += 1
                    self.provider_usage[provider] += 1
                    logger.info(f"✅ Success with {provider.upper()} ({len(response)} chars)")
                    return response
                else:
                    raise Exception("Response too short")
            
            except Exception as e:
                last_error = e
                logger.error(f"❌ {provider} failed: {e}")
                self.error_count += 1
                continue
        
        # All providers failed - use fallback
        logger.warning(f"⚠️ All providers failed. Last error: {last_error}")
        return self._intelligent_fallback(question, context, products)
    
    def _call_provider(
        self,
        provider: str,
        model_tier: str,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        """Call specific AI provider"""
        
        model = self.models[provider][model_tier]
        api_key = self.api_keys[provider]
        endpoint = self.endpoints[provider]
        
        # Special handling for different providers
        if provider == 'huggingface':
            return self._call_huggingface(model, system_prompt, user_prompt, api_key)
        elif provider == 'openrouter':
            return self._call_openrouter(model, system_prompt, user_prompt, api_key)
        else:
            # Standard OpenAI-compatible format
            return self._call_openai_compatible(
                endpoint, model, system_prompt, user_prompt, api_key, provider
            )
    
    def _call_openai_compatible(
        self,
        endpoint: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        api_key: str,
        provider: str
    ) -> str:
        """Call OpenAI-compatible APIs (Groq, DeepSeek, Together, OpenAI)"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        # DeepSeek needs specific parameters
        if provider == 'deepseek':
            data["max_tokens"] = 1500  # DeepSeek has lower limits
        
        response = requests.post(
            endpoint,
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        elif response.status_code == 429:
            raise Exception("Rate limit exceeded")
        elif response.status_code == 401:
            raise Exception("Invalid API key")
        else:
            raise Exception(f"API error {response.status_code}")
    
    def _call_openrouter(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        api_key: str
    ) -> str:
        """Call OpenRouter with free models"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:3000",  # Required by OpenRouter
            "X-Title": "Chatbot Service"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        response = requests.post(
            self.endpoints['openrouter'],
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            raise Exception(f"OpenRouter error {response.status_code}")
    
    def _call_huggingface(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        api_key: str
    ) -> str:
        """Call Hugging Face Inference API"""
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Combine prompts for HF format
        full_prompt = f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:"
        
        data = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": self.max_tokens,
                "temperature": self.temperature,
                "return_full_text": False
            }
        }
        
        endpoint = f"{self.endpoints['huggingface']}/{model}"
        
        response = requests.post(
            endpoint,
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0]["generated_text"].strip()
            return str(result)
        else:
            raise Exception(f"HuggingFace error {response.status_code}")
    
    def _build_universal_prompt(
        self, 
        question: str, 
        context: str, 
        products: Optional[List[Dict]],
        conversation_history: str
    ) -> Tuple[str, str]:
        """Build prompts (same as before)"""
        
        question_lower = question.lower()
        
        is_list_request = any(phrase in question_lower for phrase in [
            'list of', 'give me list', 'show me list', 'product names only',
            'name only', 'just names', 'only names', 'list all names'
        ])
        
        product_section = self._format_products(products, is_list_request)
        
        context = context[:5000] if context else ""
        conversation_history = conversation_history[-2000:] if conversation_history else ""
        
        if is_list_request:
            system_prompt = "You are a helpful assistant. Provide ONLY numbered product lists when asked."
            user_prompt = f"Question: {question}\n\n{product_section}\n\nProvide ONLY the list."
        else:
            system_prompt = """You are a helpful customer service assistant for an e-commerce business in Pakistan.

RULES:
1. Answer based ONLY on provided context and products
2. Be professional, friendly, conversational
3. Use markdown formatting: **bold**, bullets (•), emojis
4. All prices in Pakistani Rupees (Rs)
5. Keep responses clear and under 400 words
6. End with call-to-action"""

            user_prompt = ""
            
            if context:
                user_prompt += f"CONTEXT:\n{context}\n\n"
            
            if product_section:
                user_prompt += product_section
            
            if conversation_history:
                user_prompt += f"PREVIOUS CONVERSATION:\n{conversation_history}\n\n"
            
            user_prompt += f"CUSTOMER QUESTION:\n{question}\n\nProvide helpful response:"
        
        return system_prompt, user_prompt
    
    def _format_products(self, products: Optional[List[Dict]], is_list_request: bool) -> str:
        """Format products for prompt"""
        
        if not products or len(products) == 0:
            return ""
        
        if is_list_request:
            section = "\nPRODUCT NAMES:\n"
            for idx, p in enumerate(products, 1):
                section += f"{idx}. {p.get('name', 'Unknown')}\n"
            return section
        
        section = "\nAVAILABLE PRODUCTS:\n"
        
        for idx, p in enumerate(products[:10], 1):
            name = p.get('name', 'Unknown')
            price = p.get('price')
            desc = p.get('description', '')
            
            section += f"\n{idx}. {name}\n"
            
            if desc:
                section += f"   Description: {desc[:150]}\n"
            
            if price:
                section += f"   Price: Rs {price:,.0f}\n"
            
            colors = p.get('colors', [])
            if colors:
                section += f"   Colors: {', '.join(colors[:5])}\n"
            
            sizes = p.get('sizes', [])
            if sizes:
                section += f"   Sizes: {', '.join(sizes)}\n"
        
        return section
    
    def generate_fallback_response(
        self, 
        question: str, 
        conversation_history: str = "",
        products: Optional[List[Dict]] = None
    ) -> str:
        """Generate fallback when no documents found"""
        
        answer = "I'd be happy to help! 😊\n\n"
        
        if products and len(products) > 0:
            answer += "Here are some products that might interest you:\n\n"
            
            for idx, p in enumerate(products[:3], 1):
                name = p.get('name', 'Product')
                price = p.get('price')
                
                answer += f"**{idx}. {name}**\n"
                
                if price:
                    answer += f"   💰 Rs {price:,.0f}\n"
                
                answer += "\n"
        
        answer += "**HOW CAN I HELP?**\n\n"
        answer += "• Product information\n"
        answer += "• Pricing and availability\n"
        answer += "• Order placement\n"
        answer += "• Delivery details\n\n"
        answer += "Ask me anything! 😊"
        
        return answer
    
    def _intelligent_fallback(
        self, 
        question: str, 
        context: str, 
        products: Optional[List[Dict]]
    ) -> str:
        """High-quality fallback without AI"""
        
        logger.info("📝 Using intelligent fallback")
        
        response = ""
        
        if products and len(products) > 0:
            response += "**RELEVANT PRODUCTS:**\n\n"
            
            for idx, p in enumerate(products[:5], 1):
                name = p.get('name', 'Product')
                price = p.get('price')
                desc = p.get('description', '')
                
                response += f"**{idx}. {name}**\n"
                
                if desc:
                    response += f"   {desc[:150]}\n"
                
                if price:
                    response += f"   💰 Rs {price:,.0f}\n"
                
                response += "\n"
        
        if context and len(context) > 50:
            response += "**INFORMATION:**\n\n"
            sentences = [s.strip() for s in context.split('.') if len(s.strip()) > 30]
            for sentence in sentences[:3]:
                response += f"• {sentence}.\n"
            response += "\n"
        
        response += "**NEED HELP?**\n"
        response += "• Ask about specific products\n"
        response += "• Check 'Show all products'\n"
        response += "• Request pricing or availability\n\n"
        response += "I'm here to help! 😊"
        
        return response
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "available_providers": self.available_providers,
            "active_service": self.active_service,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "provider_usage": self.provider_usage,
            "success_rate": f"{(self.request_count / (self.request_count + self.error_count) * 100):.1f}%" if (self.request_count + self.error_count) > 0 else "N/A"
        }
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all providers"""
        health = {}
        
        for provider in self.available_providers:
            try:
                response = self._call_provider(
                    provider=provider,
                    model_tier='fast',
                    system_prompt="You are a test assistant.",
                    user_prompt="Say OK"
                )
                health[provider] = "OK" in response.upper()
            except Exception as e:
                logger.error(f"{provider} health check failed: {e}")
                health[provider] = False
        
        return health

# Global instance
llm_service = LLMService()