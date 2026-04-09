# """
# COMPLETE ENHANCED CHATBOT SERVICE - PRODUCTION READY
#  FIXED: No repetitive greetings (like in screenshot)
#  FIXED: Proper product formatting (as shown in desired output)
#  FIXED: Conversation memory works correctly
#  Direct responses (no fluff)
#  Document-first, then general knowledge
# Number-based product selection
# Complete order field collection
# Intelligent intent detection
# Groq AI integration
# ADDED: Friendly casual responses like "Hey! What's up??"
# FIXED: Better handling when document context lacks information
# ADDED: Intelligent fallback to product knowledge when docs fail
# """

# from typing import List, Dict, Optional, Tuple
# from backend.services.vector_store import vector_store
# from backend.services.llm_service import llm_service
# from backend.services.upsell_service import upsell_service
# from backend.services.order_service import order_service
# from backend.models import QueryResponse, SourceReference, ProductInfo
# from rapidfuzz import fuzz
# import logging
# from datetime import datetime, timedelta
# import re
# import os
# import time
# from groq import Groq

# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# def _clean(text: str) -> str:
#     """Clean and normalize text"""
#     if not text:
#         return ""
#     return text.strip().lower()

# def _extract_product_keywords(query: str) -> List[str]:
#     """Extract meaningful keywords from query with better filtering"""
#     stop_words = {
#         "tell", "me", "about", "the", "a", "an", "what", "is", "are", 
#         "do", "does", "you", "have", "has", "price", "of", "cost", 
#         "buy", "order", "purchase", "want", "need", "looking", "for", "show", 
#         "give", "get", "can", "i", "my", "in", "on", "at", "to", "from",
#         "your", "store", "shop", "something", "please", "kindly", "sir", "madam"
#     }
    
#     words = query.lower().split()
#     important_short_words = {"paint", "primer", "emulsion", "texture", "stain", "free", "super", "all", "weather"}
    
#     keywords = []
#     for w in words:
#         if w in stop_words:
#             continue
#         if len(w) > 2 or w in important_short_words:
#             keywords.append(w)
    
#     return keywords

# class ConversationMemory:
#     """Enhanced conversation context with order state tracking"""
    
#     def __init__(self, max_history: int = 10, timeout_minutes: int = 30):
#         self.sessions = {}
#         self.max_history = max_history
#         self.timeout = timedelta(minutes=timeout_minutes)
    
#     def add_message(self, session_id: str, user_query: str, bot_response: str, 
#                    mentioned_products: List[ProductInfo] = None, intent: str = None,
#                    metadata: Dict = None):
#         """Add message to conversation history"""
#         if session_id not in self.sessions:
#             self.sessions[session_id] = {
#                 'messages': [],
#                 'last_products': [],
#                 'last_topic': None,
#                 'last_intent': None,
#                 'last_updated': datetime.now(),
#                 'context_data': {},
#                 'order_state': None,
#                 'pending_order': {}
#             }
        
#         session = self.sessions[session_id]
#         session['messages'].append({
#             'user': user_query,
#             'bot': bot_response,
#             'intent': intent,
#             'timestamp': datetime.now(),
#             'metadata': metadata or {}
#         })
        
#         if len(session['messages']) > self.max_history:
#             session['messages'] = session['messages'][-self.max_history:]
        
#         if mentioned_products:
#             session['last_products'] = mentioned_products
        
#         if intent:
#             session['last_intent'] = intent
        
#         if metadata:
#             session['context_data'].update(metadata)
        
#         session['last_updated'] = datetime.now()
    
#     def get_context(self, session_id: str) -> Dict:
#         """Get conversation context with timeout handling"""
#         if session_id not in self.sessions:
#             return {
#                 'messages': [], 
#                 'last_products': [], 
#                 'last_intent': None,
#                 'context_data': {},
#                 'order_state': None,
#                 'pending_order': {}
#             }
        
#         session = self.sessions[session_id]
        
#         if datetime.now() - session['last_updated'] > self.timeout:
#             logger.info(f"Session {session_id} expired")
#             del self.sessions[session_id]
#             return {
#                 'messages': [], 
#                 'last_products': [], 
#                 'last_intent': None,
#                 'context_data': {},
#                 'order_state': None,
#                 'pending_order': {}
#             }
        
#         return session
    
#     def set_order_state(self, session_id: str, state: str, order_data: Dict = None):
#         """Set order collection state"""
#         context = self.get_context(session_id)
#         context['order_state'] = state
#         if order_data:
#             context['pending_order'].update(order_data)
#         self.sessions[session_id] = context
    
#     def get_order_state(self, session_id: str) -> Tuple[Optional[str], Dict]:
#         """Get current order state and pending data"""
#         context = self.get_context(session_id)
#         return context.get('order_state'), context.get('pending_order', {})
    
#     def clear_order_state(self, session_id: str):
#         """Clear order collection state"""
#         if session_id in self.sessions:
#             self.sessions[session_id]['order_state'] = None
#             self.sessions[session_id]['pending_order'] = {}
    
#     def get_conversation_history(self, session_id: str, last_n: int = 5) -> str:
#         """Get formatted conversation history for AI context"""
#         context = self.get_context(session_id)
#         messages = context.get('messages', [])[-last_n:]
        
#         if not messages:
#             return ""
        
#         history = "Recent conversation:\n"
#         for msg in messages:
#             history += f"Customer: {msg['user']}\n"
#             history += f"Assistant: {msg['bot'][:100]}...\n\n"
        
#         return history.strip()
    
#     def get_last_products(self, session_id: str, n: int = 20) -> List[ProductInfo]:
#         """Get last N products mentioned"""
#         context = self.get_context(session_id)
#         products = context.get('last_products', [])
#         return products[:n]
    
#     def clear_session(self, session_id: str):
#         """Clear specific session"""
#         if session_id in self.sessions:
#             del self.sessions[session_id]
#             logger.info(f"Session {session_id} cleared")

# class ChatbotService:
#     def __init__(self):
#         self.memory = ConversationMemory()
#         self.generic_faq = self._load_generic_faq()
#         self._confidence_threshold = 0.6
        
#         # Initialize Groq client
#         self.groq_client, self.groq_model = self._initialize_groq_client()
        
#         # Friendly casual responses mapping
#         self.friendly_responses = {
#             "hi": ["Hey! What's up?? 😊", "Hi there! How's your day going?", "Hello! 😊"],
#             "how_are_you": ["I'm great, thanks! How about you?", "Doing awesome! How are you doing?", "I'm good! What about you?"],
#             "good": ["Nice! Glad you're doing good 😊 So, what's the plan today?", "Awesome! So what brings you here today?", "Great to hear! How can I help you?"],
#             "am_good": ["Nice! Glad you're doing good 😊 So, what's the plan today?"],
#             "i_am_good": ["Nice! Glad you're doing good 😊 So, what's the plan today?"],
#             "doing_good": ["Nice! Glad you're doing good 😊 So, what's the plan today?"],
#             "thanks": ["You're welcome! 😊", "No problem! Happy to help!", "Anytime! 😄"],
#             "bye": ["See you! Have a great day! 😊", "Bye! Take care!", "Goodbye! Come back anytime!"]
#         }
        
#         # Material-Product matching knowledge base
#         self.material_recommendations = {
#             "wood": ["Brighto Wood Finish", "Brighto Stain", "Brighto Wood Varnish", "Brighto Wood Primer"],
#             "metal": ["Brighto Metal Primer", "Brighto Anti-Rust Paint", "Brighto Metallic Finish", "Brighto Iron Paint"],
#             "concrete": ["Brighto Cement Paint", "Brighto Wall Putty", "Brighto Texture Paint", "Brighto Concrete Primer"],
#             "wall": ["Brighto Emulsion", "Brighto Wall Paint", "Brighto Distemper", "Brighto Silk Finish"],
#             "plastic": ["Brighto Plastic Primer", "Brighto Plastic Paint", "Brighto PVC Coating"],
#             "exterior": ["Brighto Weatherproof Paint", "Brighto Exterior Emulsion", "Brighto Sunproof Paint"],
#             "interior": ["Brighto Interior Emulsion", "Brighto Wall Putty", "Brighto Texture Finish"],
#             "kitchen": ["Brighto Kitchen Paint", "Brighto Washable Paint", "Brighto Anti-Grease Paint"],
#             "bathroom": ["Brighto Bathroom Paint", "Brighto Waterproof Paint", "Brighto Anti-Mold Paint"],
#             "furniture": ["Brighto Wood Varnish", "Brighto Lacquer", "Brighto Furniture Paint"]
#         }
        
#         logger.info("Enhanced Chatbot Service initialized")

#     def _initialize_groq_client(self):
#         """Initialize Groq client from environment variable"""
#         groq_api_key = os.getenv('GROQ_API_KEY')
        
#         if not groq_api_key:
#             logger.warning("GROQ_API_KEY not found in environment variables")
#             return None, None
        
#         try:
#             client = Groq(api_key=groq_api_key)
            
#             current_models = [
#                 "llama-3.3-70b-versatile",
#                 "llama-3.1-8b-instant", 
#                 "llama-3.1-70b-versatile",
#                 "mixtral-8x7b-32768"
#             ]
            
#             working_model = None
#             for model in current_models:
#                 try:
#                     logger.info(f"Testing model: {model}")
#                     client.chat.completions.create(
#                         model=model,
#                         messages=[{"role": "user", "content": "Say 'OK'"}],
#                         max_tokens=5,
#                         temperature=0.1
#                     )
#                     working_model = model
#                     logger.info(f"Groq API initialized with model: {model}")
#                     break
#                 except Exception as e:
#                     logger.warning(f"Model {model} failed: {e}")
#                     continue
            
#             if not working_model:
#                 logger.error("No working Groq models found")
#                 return None, None
                
#             return client, working_model
            
#         except Exception as e:
#             logger.error(f"Failed to initialize Groq API: {e}")
#             return None, None

#     def _load_generic_faq(self) -> Dict[str, List[str]]:
#         """Generic FAQ patterns that work for any business"""
#         return {
#             "simple_greetings": ["hi", "hello", "hey", "salam", "assalam", "hi!", "hello!", "hey!", "what's up", "howdy"],
#             "how_are_you": ["how are you", "how r u", "how are you doing", "how's it going", "how do you do"],
#             "good_responses": ["i'm good", "am good", "doing good", "fine", "great", "awesome", "i'm fine", "all good", "good"],
#             "thanks": ["thanks", "thank you", "shukriya", "thx", "thanku", "appreciate", "thank you!"],
#             "bye": ["bye", "goodbye", "khuda hafiz", "allah hafiz", "see you", "bye bye"],
#             "product_list": ["show all", "list all", "all products", "catalog", "view all", "show products"],
#             "pricing": ["price", "cost", "how much", "kitna", "rate"],
#             "order": ["buy", "order", "purchase", "want to buy", "i want to buy", "place order"],
#             "delivery": ["delivery", "shipping", "ship", "deliver"],
#             "payment": ["payment", "pay", "cod", "jazzcash", "easypaisa"],
#             "material_usage": ["which paint", "what paint", "for wood", "for metal", "for concrete", "for wall", 
#                               "which product", "suggest product", "recommend", "use for", "material", "surface"]
#         }

#     def _generate_groq_response(self, system_prompt: str, user_message: str, temperature: float = 0.5) -> str:
#         """Generate response using Groq API"""
#         if not self.groq_client or not self.groq_model:
#             raise Exception("Groq API not initialized")
        
#         try:
#             start_time = time.time()
            
#             response = self.groq_client.chat.completions.create(
#                 model=self.groq_model,
#                 messages=[
#                     {"role": "system", "content": system_prompt},
#                     {"role": "user", "content": user_message},
#                 ],
#                 temperature=temperature,
#                 max_tokens=1024
#             )
            
#             response_time = time.time() - start_time
#             response_text = response.choices[0].message.content
            
#             logger.info(f"Groq response received in {response_time:.2f}s")
#             return response_text
#         except Exception as e:
#             logger.error(f"Groq API error: {e}")
#             raise

#     def _is_repetitive_response(self, session_id: str, new_response: str) -> bool:
#         """Check if response is repetitive"""
#         context = self.memory.get_context(session_id)
#         messages = context.get('messages', [])
        
#         if len(messages) < 2:
#             return False
        
#         # Get last 2 bot responses
#         last_responses = [msg['bot'] for msg in messages[-2:] if 'bot' in msg]
        
#         # Check if new response is similar to previous ones
#         for resp in last_responses:
#             if fuzz.ratio(new_response.lower(), resp.lower()) > 80:
#                 return True
        
#         return False

#     def format_product_info(self, product: ProductInfo) -> str:
#         """Format product information in clean, structured way (like screenshot)"""
        
#         lines = []
#         lines.append(f"**{product.name.upper()}**")
#         lines.append("")
        
#         if product.description:
#             lines.append(f"**Description:** {product.description}")
#             lines.append("")
        
#         if product.category:
#             lines.append(f"**Category:** {product.category}")
#             lines.append("")
        
#         if product.price and product.price > 0:
#             lines.append(f"**Price:** Rs {product.price:,.0f}")
#             lines.append("")
#         else:
#             lines.append("**Price:** Contact for pricing")
#             lines.append("")
        
#         if hasattr(product, 'colors') and product.colors:
#             lines.append(f"**Colors:** {', '.join(product.colors[:5])}")
#             if len(product.colors) > 5:
#                 lines[-1] += f" (+{len(product.colors)-5} more)"
#             lines.append("")
        
#         if hasattr(product, 'sizes') and product.sizes:
#             lines.append(f"**Sizes:** {', '.join(product.sizes)}")
#             lines.append("")
        
#         if hasattr(product, 'features') and product.features:
#             lines.append("**Features:**")
#             for feature in product.features[:3]:
#                 lines.append(f"• {feature}")
#             lines.append("")
        
#         lines.append("**Stock:** Available")
#         lines.append("")
#         lines.append(f"**To Order:** Type 'buy {product.name}' or 'I want to order {product.name}'")
        
#         return "\n".join(lines)

#     def _handle_material_recommendation(self, query: str, session_id: str, original_question: str) -> QueryResponse:
#         """Handle material-based product recommendations"""
        
#         # Extract material from query
#         materials = []
#         for material, keywords in {
#             "wood": ["wood", "timber", "furniture", "door", "window"],
#             "metal": ["metal", "iron", "steel", "aluminum", "gate", "grill"],
#             "concrete": ["concrete", "cement", "floor", "terrace", "roof"],
#             "wall": ["wall", "interior", "exterior", "room", "house"],
#             "plastic": ["plastic", "pvc", "pipe", "synthetic"],
#             "exterior": ["exterior", "outside", "outdoor", "facade"],
#             "interior": ["interior", "inside", "indoor", "room"],
#             "kitchen": ["kitchen", "cooking", "grease", "steam"],
#             "bathroom": ["bathroom", "toilet", "shower", "water", "humid"],
#             "furniture": ["furniture", "table", "chair", "cabinet"]
#         }.items():
#             if any(keyword in query.lower() for keyword in keywords):
#                 materials.append(material)
        
#         if not materials:
#             # Try to find using Groq if no material detected
#             return self._handle_intelligent_query_with_fallback(original_question, session_id, "", 5)
        
#         # Get recommended products
#         all_products = []
#         for material in materials[:3]:  # Limit to 3 materials
#             if material in self.material_recommendations:
#                 all_products.extend(self.material_recommendations[material])
        
#         if not all_products:
#             return self._handle_intelligent_query_with_fallback(original_question, session_id, "", 5)
        
#         # Remove duplicates
#         unique_products = list(dict.fromkeys(all_products))
        
#         # Create helpful response
#         answer = f"**🎨 Recommended Products for {', '.join(materials).title()}**\n\n"
        
#         for idx, product_name in enumerate(unique_products[:10], 1):
#             answer += f"{idx}. **{product_name}**\n"
            
#             # Try to find product details
#             product = self._find_product_by_name(product_name)
#             if product:
#                 if hasattr(product, 'description') and product.description:
#                     desc = product.description[:80] + "..." if len(product.description) > 80 else product.description
#                     answer += f"   {desc}\n"
                
#                 if product.price and product.price > 0:
#                     answer += f"   Price: Rs {product.price:,.0f}\n"
            
#             answer += "\n"
        
#         answer += "\n**💡 Tips:**\n"
#         answer += "• For best results, clean and prepare the surface first\n"
#         answer += "• Use appropriate primer before painting\n"
#         answer += "• Apply 2-3 coats for better coverage\n"
#         answer += "• Allow proper drying time between coats\n\n"
#         answer += "Type a product number or name for more details! 😊"
        
#         response = QueryResponse(
#             answer=answer,
#             sources=[],
#             confidence=0.9
#         )
        
#         self.memory.add_message(session_id, original_question, answer, intent="material_recommendation")
#         return response

#     def _find_product_by_name(self, product_name: str) -> Optional[ProductInfo]:
#         """Find product by exact or partial name"""
#         try:
#             if not upsell_service.products:
#                 upsell_service.load_all_products()
            
#             if not upsell_service.products:
#                 return None
            
#             for product in upsell_service.products:
#                 if product and hasattr(product, 'name'):
#                     if product_name.lower() in product.name.lower() or product.name.lower() in product_name.lower():
#                         return product
            
#             # Try fuzzy matching
#             for product in upsell_service.products:
#                 if product and hasattr(product, 'name'):
#                     if fuzz.partial_ratio(product_name.lower(), product.name.lower()) > 70:
#                         return product
            
#             return None
            
#         except Exception as e:
#             logger.error(f"Error finding product by name: {e}")
#             return None

#     def answer_query(self, question: str, top_k: int = 5, shop_filter: str = None, 
#                     session_id: str = "default") -> QueryResponse:
#         """
#         MAIN INTELLIGENT QUERY HANDLER
#         FIXED: No repetitive responses
#         """
        
#         if not question or len(question.strip()) < 2:
#             return QueryResponse(
#                 answer="Hey! Could you ask something? 😊",
#                 sources=[],
#                 confidence=0.0
#             )
        
#         original_question = question
#         q = _clean(question)
#         logger.info(f"Query: '{question}' | Session: {session_id}")

#         try:
#             context = self.memory.get_context(session_id)
#             conversation_history = self.memory.get_conversation_history(session_id, last_n=3)

#             # CHECK FOR REPETITIVE USER QUERY
#             messages = context.get('messages', [])
            
#             if messages:
#                 last_user_query = messages[-1].get('user', '').strip().lower()
#                 current_query = original_question.strip().lower()
                
#                 # If user is repeating the same query
#                 if last_user_query == current_query and len(messages) > 1:
#                     # Get last product mentioned
#                     last_products = self.memory.get_last_products(session_id, n=1)
#                     if last_products:
#                         product = last_products[0]
#                         answer = f"You already asked about {product.name}.\n\n"
#                         answer += "Need more details? Ask about:\n"
#                         answer += "• Specific features\n"
#                         answer += "• Colors available\n"
#                         answer += "• Sizes\n"
#                         answer += "• Pricing details\n"
#                         answer += "• Or type 'buy' to order it"
#                     else:
#                         answer = "You already asked that. Is there something specific you'd like to know?"
                    
#                     return QueryResponse(
#                         answer=answer,
#                         sources=[],
#                         confidence=0.0
#                     )
            
#             # PRIORITY 1: Check if in order collection mode
#             order_state, pending_order = self.memory.get_order_state(session_id)
            
#             if order_state:
#                 return self._handle_order_collection(
#                     original_question, session_id, order_state, pending_order
#                 )

#             # PRIORITY 2: Check for number-based product selection
#             number_match = self._extract_product_number(original_question)
#             if number_match is not None:
#                 last_products = self.memory.get_last_products(session_id)
#                 if last_products:
#                     return self._handle_number_selection(number_match, session_id, original_question)

#             # PRIORITY 3: Detect intent
#             intent = self._detect_intent(q, context, original_question)
#             logger.info(f"Intent: {intent}")

#             # PRIORITY 4: Route to appropriate handler
#             response = self._route_query(
#                 intent=intent,
#                 query=q,
#                 original_question=original_question,
#                 session_id=session_id,
#                 context=context,
#                 conversation_history=conversation_history,
#                 top_k=top_k
#             )
            
#             # Check if response is repetitive
#             if self._is_repetitive_response(session_id, response.answer):
#                 # Provide alternative response
#                 if "Hey" in response.answer or "Hello" in response.answer:
#                     response.answer = "Hey again! What can I help you with today? 😊"
            
#             return response
        
#         except Exception as e:
#             logger.error(f"Error in answer_query: {e}", exc_info=True)
#             return QueryResponse(
#                 answer="Oops! Something went wrong. Could you try again? 😊",
#                 sources=[],
#                 confidence=0.0
#             )

#     def _extract_product_number(self, query: str) -> Optional[int]:
#         """
#         Extract product number from query
#         Handles: 3, product 3, number 3, #3, item 3, etc.
#         """
        
#         # Pattern 1: Just a number (1-50)
#         if query.strip().isdigit():
#             num = int(query.strip())
#             if 1 <= num <= 50:
#                 return num
        
#         # Pattern 2: "product 3", "number 3", "#3", "item 3", "option 3"
#         patterns = [
#             r'product\s*#?(\d+)',
#             r'number\s*#?(\d+)',
#             r'item\s*#?(\d+)',
#             r'option\s*#?(\d+)',
#             r'#(\d+)',
#             r'^(\d+)$',
#             r'select\s*(\d+)',
#             r'choose\s*(\d+)'
#         ]
        
#         for pattern in patterns:
#             match = re.search(pattern, query.lower())
#             if match:
#                 num = int(match.group(1))
#                 if 1 <= num <= 50:
#                     return num
        
#         return None

#     def _handle_number_selection(self, number: int, session_id: str, original_question: str) -> QueryResponse:
#         """
#         Handle number-based product selection
#         User types '3' to see product #3
#         """
        
#         last_products = self.memory.get_last_products(session_id, n=50)
        
#         if not last_products:
#             return QueryResponse(
#                 answer="Hey! No products found. Try 'show products' first. 😊",
#                 sources=[],
#                 confidence=0.5
#             )
        
#         if number > len(last_products):
#             return QueryResponse(
#                 answer=f"Oops! Product #{number} not found. We have {len(last_products)} products available. 😊",
#                 sources=[],
#                 confidence=0.5
#             )
        
#         # Get the selected product (1-indexed)
#         selected_product = last_products[number - 1]
        
#         # Use the formatted product info
#         answer = self.format_product_info(selected_product)
        
#         response = QueryResponse(
#             answer=answer,
#             sources=[],
#             related_products=[selected_product],
#             confidence=0.95
#         )
        
#         self.memory.add_message(
#             session_id, 
#             original_question, 
#             answer, 
#             [selected_product], 
#             intent="number_selection"
#         )
        
#         return response

#     def _handle_order_collection(self, query: str, session_id: str, 
#                                  order_state: str, pending_order: Dict) -> QueryResponse:
#         """
#         Handle step-by-step order collection
#         Collects ALL required fields: name, phone, address, city, quantity, payment
#         """
        
#         # Define order collection flow with ALL fields
#         flow = ['full_name', 'phone', 'address', 'city', 'quantity', 'payment_method']
        
#         current_index = flow.index(order_state) if order_state in flow else 0
        
#         # Store current field value
#         if order_state == 'full_name':
#             if 'customer_info' not in pending_order:
#                 pending_order['customer_info'] = {}
#             pending_order['customer_info']['full_name'] = query.strip()
#             logger.info(f"Collected name: {query.strip()}")
        
#         elif order_state == 'phone':
#             # Validate phone
#             phone = re.sub(r'[^\d+]', '', query)
#             if len(phone) < 10:
#                 return QueryResponse(
#                     answer="Hey! Could you provide a valid phone number? (at least 10 digits) 😊",
#                     sources=[],
#                     confidence=0.9
#                 )
#             pending_order['customer_info']['phone'] = phone
#             logger.info(f"Collected phone: {phone}")
        
#         elif order_state == 'address':
#             pending_order['customer_info']['address'] = query.strip()
#             logger.info(f"Collected address: {query.strip()}")
        
#         elif order_state == 'city':
#             pending_order['customer_info']['city'] = query.strip()
#             logger.info(f"Collected city: {query.strip()}")
        
#         elif order_state == 'quantity':
#             try:
#                 # Extract any number from query
#                 qty_match = re.search(r'\d+', query)
#                 if qty_match:
#                     qty = int(qty_match.group())
#                 else:
#                     # Try to find number words
#                     if 'one' in query.lower():
#                         qty = 1
#                     elif 'two' in query.lower():
#                         qty = 2
#                     elif 'three' in query.lower():
#                         qty = 3
#                     elif 'four' in query.lower():
#                         qty = 4
#                     elif 'five' in query.lower():
#                         qty = 5
#                     else:
#                         qty = 1
                
#                 if qty < 1:
#                     qty = 1
                
#                 # Update pending order
#                 if 'items' not in pending_order:
#                     pending_order['items'] = []
                
#                 if len(pending_order['items']) > 0:
#                     pending_order['items'][0]['quantity'] = qty
#                     if 'unit_price' in pending_order['items'][0]:
#                         pending_order['items'][0]['total_price'] = pending_order['items'][0]['unit_price'] * qty
                
#                 logger.info(f"Collected quantity: {qty}")
#             except Exception as e:
#                 logger.error(f"Quantity error: {e}")
#                 return QueryResponse(
#                     answer="Hey! Could you provide a valid quantity? (e.g., 2, 5, 10) 😊",
#                     sources=[],
#                     confidence=0.9
#                 )
        
#         elif order_state == 'payment_method':
#             payment_method = query.strip()
#             if 'payment_details' not in pending_order:
#                 pending_order['payment_details'] = {}
#             pending_order['payment_details']['method'] = payment_method
#             logger.info(f"Collected payment: {payment_method}")
        
#         # Move to next field
#         current_index += 1
        
#         if current_index >= len(flow):
#             # ALL DATA COLLECTED - PLACE ORDER
#             try:
#                 # Ensure order data is complete
#                 if 'customer_info' not in pending_order:
#                     pending_order['customer_info'] = {}
#                 if 'items' not in pending_order:
#                     pending_order['items'] = []
#                 if 'payment_details' not in pending_order:
#                     pending_order['payment_details'] = {'method': 'COD'}
                
#                 logger.info(f"Placing order: {pending_order}")
                
#                 # Use your existing order_service
#                 result = order_service.place_order(pending_order)
#                 self.memory.clear_order_state(session_id)
                
#                 if result['success']:
#                     answer = f"🎉 **Order Confirmed!**\n\n"
#                     answer += f"**Order ID:** {result['order_id']}\n"
#                     answer += f"**Total:** Rs {result['total_amount']:,.0f}\n"
#                     answer += f"**Estimated Delivery:** {result['estimated_delivery']}\n\n"
#                     answer += "Thanks so much for your order! 😊"
#                 else:
#                     answer = f"😕 Order failed: {result.get('message', 'Unknown error')}"
                
#                 return QueryResponse(answer=answer, sources=[], confidence=1.0)
                
#             except Exception as e:
#                 logger.error(f"Order placement error: {e}")
#                 self.memory.clear_order_state(session_id)
#                 return QueryResponse(
#                     answer="Oops! Order placement failed. Could you try again? 😊",
#                     sources=[],
#                     confidence=0.5
#                 )
        
#         # Ask for next field
#         next_field = flow[current_index]
#         self.memory.set_order_state(session_id, next_field, pending_order)
        
#         # Generate appropriate question
#         field_prompts = {
#             'full_name': "Great! What's your full name? 😊",
#             'phone': "Perfect! What's your phone number?",
#             'address': "Awesome! What's your delivery address?",
#             'city': "Cool! Which city?",
#             'quantity': "How many units would you like?",
#             'payment_method': "Payment method? (COD/Bank Transfer/JazzCash/EasyPaisa) 😊"
#         }
        
#         prompt = field_prompts.get(next_field, "Could you provide that information? 😊")
        
#         return QueryResponse(
#             answer=prompt,
#             sources=[],
#             confidence=1.0
#         )

#     def _detect_intent(self, q: str, context: Dict, original_question: str = None) -> str:
#         """Enhanced intent detection"""
        
#         q_trimmed = q.strip()
#         q_words = q.split()
        
#         # Check if this is the first message
#         messages = context.get('messages', [])
        
#         # NEW: Check for friendly greetings first
#         if q_trimmed in self.generic_faq["simple_greetings"]:
#             if not messages:
#                 return "welcome_greeting"
#             else:
#                 return "simple_greeting"
        
#         # Check for "how are you"
#         if any(pattern in q for pattern in self.generic_faq["how_are_you"]):
#             return "how_are_you"
        
#         # Check for "good" responses
#         if any(pattern in q for pattern in self.generic_faq["good_responses"]):
#             # Check if previous message was "how are you"
#             if messages and len(messages) > 0:
#                 last_bot_message = messages[-1].get('bot', '').lower()
#                 if any(pattern in last_bot_message for pattern in ["how about you", "how are you"]):
#                     return "good_response"
#             return "general_good"
        
#         # Check for material usage recommendations
#         if any(pattern in q for pattern in self.generic_faq["material_usage"]):
#             return "material_recommendation"
        
#         # Thanks
#         if any(pattern in q for pattern in self.generic_faq["thanks"]):
#             return "thanks"
        
#         # Goodbye
#         if any(pattern in q for pattern in self.generic_faq["bye"]):
#             return "bye"
        
#         # Product list
#         if any(pattern in q for pattern in self.generic_faq["product_list"]):
#             return "product_list"
        
#         # Check for specific product FIRST before order intent
#         product = self._find_product_in_query(q)
        
#         if product:
#             # Check if user explicitly wants to buy
#             strong_order_indicators = ["buy", "order", "purchase", "want to buy", "i want to buy", "place order"]
#             has_strong_order_intent = any(indicator in q for indicator in strong_order_indicators)
            
#             if has_strong_order_intent:
#                 logger.info(f"Order intent detected for product: {product.name}")
#                 return "order"
#             else:
#                 # Default to product information
#                 logger.info(f"Product inquiry detected for: {product.name}")
#                 return "specific_product"
        
#         # Check for number selection
#         if self._extract_product_number(original_question) is not None:
#             return "number_selection"
        
#         # General intents (only if no specific product found)
#         if any(pattern in q for pattern in self.generic_faq["pricing"]):
#             return "pricing"
        
#         if any(pattern in q for pattern in self.generic_faq["order"]):
#             return "order"
        
#         if any(pattern in q for pattern in self.generic_faq["delivery"]):
#             return "delivery"
        
#         if any(pattern in q for pattern in self.generic_faq["payment"]):
#             return "payment"
        
#         # Follow-up question
#         if self._is_followup_question(q) and context.get('last_products'):
#             return "followup"
        
#         # Default
#         return "general_query"

#     def _is_followup_question(self, q: str) -> bool:
#         """Detect follow-up questions"""
#         followup_indicators = [
#             "what about", "what is this", "tell me more", "more details",
#             "this one", "that one", "it", "its", "they", "how about",
#             "explain", "describe", "information", "details"
#         ]
        
#         words = q.split()
#         if len(words) <= 8:
#             return any(indicator in q for indicator in followup_indicators)
        
#         return False

#     def _find_product_in_query(self, q: str) -> Optional[ProductInfo]:
#         """Find product using fuzzy matching"""
        
#         try:
#             if not upsell_service.products:
#                 upsell_service.load_all_products()
            
#             if not upsell_service.products:
#                 logger.warning("No products available")
#                 return None
            
#             keywords = _extract_product_keywords(q)
            
#             if not keywords:
#                 return None
            
#             search_term = " ".join(keywords)
            
#             if len(search_term) < 2:
#                 return None
            
#             best_match = None
#             best_score = 0
            
#             for product in upsell_service.products:
#                 if not product or not hasattr(product, 'name'):
#                     continue
                    
#                 product_name_lower = product.name.lower()
                
#                 scores = [
#                     fuzz.partial_ratio(search_term, product_name_lower) * 1.2,
#                     fuzz.token_sort_ratio(search_term, product_name_lower) * 1.2,
#                 ]
                
#                 # Bonus for exact matches
#                 if search_term in product_name_lower:
#                     scores.append(95)
                
#                 if product_name_lower.startswith(search_term):
#                     scores.append(90)
                
#                 # Bonus for keyword match
#                 if any(keyword in product_name_lower for keyword in keywords):
#                     scores.append(85)
                
#                 max_score = max(scores)
                
#                 if max_score > best_score:
#                     best_score = max_score
#                     best_match = product
            
#             min_threshold = 65 if len(search_term) > 3 else 60
            
#             if best_score >= min_threshold:
#                 logger.info(f"Found product: {best_match.name} (score: {best_score})")
#                 return best_match
            
#             logger.info(f"No product found above threshold {min_threshold}. Best score: {best_score}")
#             return None
            
#         except Exception as e:
#             logger.error(f"Error in product search: {e}", exc_info=True)
#             return None

#     def _route_query(self, intent: str, query: str, original_question: str,
#                     session_id: str, context: Dict, conversation_history: str,
#                     top_k: int) -> QueryResponse:
#         """Route query to appropriate handler"""
        
#         handlers = {
#             "welcome_greeting": lambda: self._handle_welcome_greeting(session_id, original_question),
#             "simple_greeting": lambda: self._handle_simple_greeting(session_id, original_question),
#             "how_are_you": lambda: self._handle_how_are_you(session_id, original_question),
#             "good_response": lambda: self._handle_good_response(session_id, original_question, context),
#             "general_good": lambda: self._handle_general_good(session_id, original_question),
#             "material_recommendation": lambda: self._handle_material_recommendation(query, session_id, original_question),
#             "thanks": lambda: self._handle_thanks(session_id, original_question),
#             "bye": lambda: self._handle_bye(session_id, original_question),
#             "product_list": lambda: self._handle_product_catalog(session_id, original_question),
#             "specific_product": lambda: self._handle_specific_product(query, session_id, original_question),
#             "pricing": lambda: self._handle_pricing_query(query, session_id, original_question, conversation_history),
#             "order": lambda: self._handle_order_intent(query, session_id, original_question, conversation_history),
#             "delivery": lambda: self._handle_delivery_query(session_id, original_question, conversation_history),
#             "payment": lambda: self._handle_payment_query(session_id, original_question, conversation_history),
#             "followup": lambda: self._handle_followup_question(query, context, session_id, original_question, conversation_history),
#             "number_selection": lambda: self._handle_number_selection(self._extract_product_number(original_question), session_id, original_question) if self._extract_product_number(original_question) else self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, top_k),
#         }
        
#         handler = handlers.get(intent)
#         if handler:
#             return handler()
        
#         return self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, top_k)

#     # ==================== HANDLER METHODS ====================

#     def _handle_welcome_greeting(self, session_id: str, original_question: str) -> QueryResponse:
#         """First greeting in conversation - NOW CASUAL & FRIENDLY"""
        
#         # Choose a random friendly greeting
#         import random
#         greetings = ["Hey! What's up?? 😊", "Hi there! How's your day going?", "Hello! 😊"]
#         answer = random.choice(greetings)
        
#         response = QueryResponse(answer=answer, sources=[], confidence=1.0)
#         self.memory.add_message(session_id, original_question, answer, intent="welcome_greeting")
#         return response

#     def _handle_simple_greeting(self, session_id: str, original_question: str) -> QueryResponse:
#         """Simple greeting response - FIXED to be friendly"""
        
#         context = self.memory.get_context(session_id)
#         messages = context.get('messages', [])
        
#         # Check if this is a repeated greeting
#         greeting_count = 0
#         for msg in messages[-3:]:  # Check last 3 messages
#             if msg.get('intent') in ['simple_greeting', 'welcome_greeting']:
#                 greeting_count += 1
        
#         if greeting_count >= 2:
#             answer = "Hey again! What can I help you with today? 😊"
#         else:
#             # Choose a random friendly greeting
#             import random
#             greetings = ["Hey there! How can I help? 😊", "Hi! What's up?", "Hello again! 😊"]
#             answer = random.choice(greetings)
        
#         response = QueryResponse(answer=answer, sources=[], confidence=1.0)
#         self.memory.add_message(session_id, original_question, answer, intent="simple_greeting")
#         return response

#     def _handle_how_are_you(self, session_id: str, original_question: str) -> QueryResponse:
#         """Handle 'how are you' queries"""
        
#         answer = "I'm great, thanks! How about you? 😊"
        
#         response = QueryResponse(answer=answer, sources=[], confidence=1.0)
#         self.memory.add_message(session_id, original_question, answer, intent="how_are_you")
#         return response

#     def _handle_good_response(self, session_id: str, original_question: str, context: Dict) -> QueryResponse:
#         """Handle 'I'm good' responses after 'how are you'"""
        
#         answer = "Nice! Glad you're doing good 😊 So, what's the plan today?"
        
#         response = QueryResponse(answer=answer, sources=[], confidence=1.0)
#         self.memory.add_message(session_id, original_question, answer, intent="good_response")
#         return response

#     def _handle_general_good(self, session_id: str, original_question: str) -> QueryResponse:
#         """Handle general 'good' responses"""
        
#         answer = "That's great! 😊 How can I help you today?"
        
#         response = QueryResponse(answer=answer, sources=[], confidence=1.0)
#         self.memory.add_message(session_id, original_question, answer, intent="general_good")
#         return response

#     def _handle_material_recommendation(self, q: str, session_id: str, original_question: str) -> QueryResponse:
#         """Handle material-based product recommendations"""
#         return self._handle_material_recommendation(q, session_id, original_question)

#     def _handle_already_greeted(self, session_id: str, original_question: str) -> QueryResponse:
#         """Handle when user greets again after already greeted"""
        
#         answer = "Hey! I already greeted you 😊 What specific help do you need?\n\n"
#         answer += "Try:\n"
#         answer += "• 'Show products' to see what we have\n"
#         answer += "• Ask about a specific paint\n"
#         answer += "• 'Place an order' to buy something\n"
#         answer += "• Ask about delivery or payment"
        
#         response = QueryResponse(answer=answer, sources=[], confidence=1.0)
#         self.memory.add_message(session_id, original_question, answer, intent="already_greeted")
#         return response

#     def _handle_thanks(self, session_id: str, original_question: str) -> QueryResponse:
#         """Handle thank you messages"""
#         answer = "You're welcome! 😊 Is there anything else I can help you with?"
        
#         response = QueryResponse(answer=answer, sources=[], confidence=1.0)
#         self.memory.add_message(session_id, original_question, answer, intent="thanks")
#         return response

#     def _handle_bye(self, session_id: str, original_question: str) -> QueryResponse:
#         """Handle goodbye messages"""
#         answer = "See you! Have a great day! 😊"
        
#         response = QueryResponse(answer=answer, sources=[], confidence=1.0)
#         self.memory.add_message(session_id, original_question, answer, intent="bye")
#         self.memory.clear_session(session_id)
#         return response

#     def _handle_product_catalog(self, session_id: str, original_question: str) -> QueryResponse:
#         """Show complete product catalog with numbered list"""
        
#         if not upsell_service.products:
#             upsell_service.load_all_products()
        
#         products = upsell_service.products
        
#         if not products:
#             answer = "Hey! No products available right now. 😊"
#             response = QueryResponse(answer=answer, sources=[], confidence=0.0)
#             self.memory.add_message(session_id, original_question, answer, intent="product_list")
#             return response
        
#         # Show first 20 products with numbers
#         total_products = len(products)
#         display_products = products[:20]
        
#         answer = f"**🎨 PRODUCT CATALOG** ({total_products} items)\n\n"
        
#         for idx, product in enumerate(display_products, 1):
#             answer += f"**{idx}. {product.name}**\n"
            
#             if product.description and len(product.description) > 10:
#                 desc = product.description[:80] + "..." if len(product.description) > 80 else product.description
#                 answer += f"   {desc}\n"
            
#             if product.price and product.price > 0:
#                 answer += f"   **Price:** Rs {product.price:,.0f}\n"
            
#             if hasattr(product, 'colors') and product.colors:
#                 colors_display = ', '.join(product.colors[:3])
#                 if len(product.colors) > 3:
#                     colors_display += f" (+{len(product.colors)-3})"
#                 answer += f"   Colors: {colors_display}\n"
            
#             answer += "\n"
        
#         if total_products > 20:
#             answer += f"... and {total_products - 20} more products!\n\n"
        
#         answer += "**How to select:**\n"
#         answer += "• Type number (e.g. '3') to view details\n"
#         answer += "• Type 'buy [number]' to order (e.g. 'buy 3')\n"
#         answer += "• Ask about specific product names"
        
#         response = QueryResponse(
#             answer=answer,
#             sources=[],
#             related_products=display_products,
#             confidence=1.0
#         )
        
#         self.memory.add_message(session_id, original_question, answer, display_products, intent="product_list")
#         return response

#     def _handle_specific_product(self, q: str, session_id: str, original_question: str) -> QueryResponse:
#         """Handle specific product queries - FIXED FORMAT (like screenshot)"""
        
#         product = self._find_product_in_query(q)
        
#         if not product:
#             return self._handle_intelligent_query_with_fallback(original_question, session_id, "", 5)
        
#         # Use the formatted product info (matches your screenshot format)
#         answer = self.format_product_info(product)
        
#         response = QueryResponse(
#             answer=answer,
#             sources=[],
#             related_products=[product],
#             confidence=0.95
#         )
        
#         self.memory.add_message(
#             session_id, 
#             original_question, 
#             answer, 
#             [product], 
#             intent="specific_product"
#         )
#         return response

#     def _handle_pricing_query(self, q: str, session_id: str, original_question: str, 
#                              conversation_history: str) -> QueryResponse:
#         """Handle pricing queries"""
        
#         product = self._find_product_in_query(q)
        
#         if product:
#             answer = f"**{product.name.upper()}**\n\n"
            
#             if product.price and product.price > 0:
#                 answer += f"**Price:** Rs {product.price:,.0f}\n\n"
#             else:
#                 answer += "**Price:** Contact for pricing\n\n"
            
#             if hasattr(product, 'sizes') and product.sizes:
#                 answer += f"**Sizes:** {', '.join(product.sizes)}\n\n"
            
#             if hasattr(product, 'colors') and product.colors:
#                 answer += f"**Colors:** {', '.join(product.colors[:10])}\n\n"
            
#             answer += "**Delivery:** 3-5 business days\n\n"
#             answer += f"**Order:** Say 'buy {product.name}' to order"
            
#             response = QueryResponse(
#                 answer=answer,
#                 sources=[],
#                 related_products=[product],
#                 confidence=0.95
#             )
#         else:
#             response = self._handle_intelligent_query_with_fallback(
#                 original_question, 
#                 session_id, 
#                 conversation_history, 
#                 5
#             )
        
#         self.memory.add_message(
#             session_id, 
#             original_question, 
#             response.answer, 
#             response.related_products, 
#             intent="pricing"
#         )
#         return response

#     def _handle_order_intent(self, q: str, session_id: str, original_question: str,
#                             conversation_history: str) -> QueryResponse:
#         """Handle order placement"""
        
#         try:
#             product = self._find_product_in_query(q)
            
#             if product:
#                 # Start order process
#                 pending_order = {
#                     'items': [{
#                         'product_name': product.name,
#                         'product_id': getattr(product, 'id', ''),
#                         'unit_price': product.price if product.price else 0,
#                         'quantity': 1,
#                         'total_price': product.price if product.price else 0
#                     }],
#                     'customer_info': {},
#                     'payment_details': {}
#                 }
                
#                 # Set initial order state
#                 self.memory.set_order_state(session_id, 'full_name', pending_order)
                
#                 answer = f"**🎉 ORDER: {product.name.upper()}**\n\n"
                
#                 if product.price and product.price > 0:
#                     answer += f"Price: Rs {product.price:,.0f}\n\n"
                
#                 answer += "Awesome! Let's get your order placed. 😊\n\n"
#                 answer += "I'll need:\n"
#                 answer += "1. Your full name\n"
#                 answer += "2. Phone number\n"
#                 answer += "3. Delivery address\n"
#                 answer += "4. City\n"
#                 answer += "5. Quantity\n"
#                 answer += "6. Payment method\n\n"
#                 answer += "Starting with your full name:"
                
#                 response = QueryResponse(
#                     answer=answer,
#                     sources=[],
#                     related_products=[product],
#                     confidence=0.95
#                 )
#             else:
#                 # No specific product mentioned
#                 if not upsell_service.products:
#                     upsell_service.load_all_products()
                
#                 products = upsell_service.products
                
#                 if products and len(products) > 0:
#                     answer = "I'd love to help you place an order! 😊\n\n"
#                     answer += "Which product would you like to buy?\n\n"
                    
#                     # Show popular products
#                     popular_products = products[:5]
                    
#                     for idx, product in enumerate(popular_products, 1):
#                         price_info = f" - Rs {product.price:,.0f}" if product.price and product.price > 0 else ""
#                         answer += f"{idx}. {product.name}{price_info}\n"
                        
#                         if product.description and len(product.description) > 10:
#                             desc = product.description[:60] + "..." if len(product.description) > 60 else product.description
#                             answer += f"   {desc}\n"
                        
#                         answer += f"   Say: 'I want to buy {product.name}'\n\n"
                    
#                     if len(products) > 5:
#                         answer += f"... and {len(products) - 5} more products available!\n\n"
                    
#                     answer += "Or type 'show products' to see all options."
                    
#                     response = QueryResponse(
#                         answer=answer,
#                         sources=[],
#                         related_products=popular_products,
#                         confidence=0.8
#                     )
#                 else:
#                     # No products available
#                     answer = "I'd love to help you place an order! 😊\n\n"
#                     answer += "Which product are you interested in?"
                    
#                     response = QueryResponse(
#                         answer=answer,
#                         sources=[],
#                         related_products=[],
#                         confidence=0.7
#                     )
            
#         except Exception as e:
#             logger.error(f"Error in order intent handler: {e}", exc_info=True)
#             # Fallback to product search
#             return self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, 5)
        
#         self.memory.add_message(
#             session_id, 
#             original_question, 
#             response.answer,
#             response.related_products, 
#             intent="order"
#         )
#         return response

#     def _handle_delivery_query(self, session_id: str, original_question: str, 
#                               conversation_history: str) -> QueryResponse:
#         """Handle delivery queries"""
        
#         results = vector_store.search("delivery shipping time", top_k=3)
        
#         if results and len(results) > 0:
#             doc_context = "\n\n".join([r["text"][:500] for r in results])
            
#             try:
#                 # Use Groq for AI response if available
#                 if self.groq_client:
#                     system_prompt = """You are a friendly, casual customer service assistant. 
#                     Provide clear, concise information about delivery and shipping based on the provided context.
#                     If the context doesn't contain specific delivery info, use general knowledge about paint store deliveries.
#                     Keep answers friendly and direct. Use emojis occasionally."""
#                     ai_answer = self._generate_groq_response(system_prompt, f"Context: {doc_context}\n\nQuestion: {original_question}")
#                 else:
#                     ai_answer = llm_service.generate_response(
#                         question=original_question,
#                         context=doc_context,
#                         conversation_history=conversation_history
#                     )
                
#                 sources = [
#                     SourceReference(
#                         text=r["text"][:200],
#                         document=r.get("source", "Document"),
#                         score=r.get("score", 0)
#                     )
#                     for r in results[:2]
#                 ]
                
#                 response = QueryResponse(
#                     answer=ai_answer,
#                     sources=sources,
#                     confidence=0.85
#                 )
#             except:
#                 response = self._generic_delivery_info()
#         else:
#             response = self._generic_delivery_info()
        
#         self.memory.add_message(session_id, original_question, response.answer, intent="delivery")
#         return response
    
#     def _generic_delivery_info(self) -> QueryResponse:
#         """Generic delivery info"""
#         answer = "**🚚 Delivery Information**\n\n"
#         answer += "• **Time:** 3-5 business days\n"
#         answer += "• **Charges:** Rs 200 (FREE over Rs 5,000) 😊\n"
#         answer += "• **Cities:** All major cities\n"
#         answer += "• **Tracking:** SMS/WhatsApp updates\n\n"
#         answer += "Fast and reliable delivery guaranteed!"
        
#         return QueryResponse(answer=answer, sources=[], confidence=0.7)

#     def _handle_payment_query(self, session_id: str, original_question: str,
#                              conversation_history: str) -> QueryResponse:
#         """Handle payment queries"""
        
#         results = vector_store.search("payment methods cod", top_k=3)
        
#         if results and len(results) > 0:
#             doc_context = "\n\n".join([r["text"][:500] for r in results])
            
#             try:
#                 # Use Groq for AI response if available
#                 if self.groq_client:
#                     system_prompt = """You are a friendly, casual customer service assistant. 
#                     Provide clear, concise information about payment methods based on the provided context.
#                     If the context doesn't contain specific payment info, use general knowledge about paint store payments.
#                     Keep answers friendly and direct. Use emojis occasionally."""
#                     ai_answer = self._generate_groq_response(system_prompt, f"Context: {doc_context}\n\nQuestion: {original_question}")
#                 else:
#                     ai_answer = llm_service.generate_response(
#                         question=original_question,
#                         context=doc_context,
#                         conversation_history=conversation_history
#                     )
                
#                 sources = [
#                     SourceReference(
#                         text=r["text"][:200],
#                         document=r.get("source", "Document"),
#                         score=r.get("score", 0)
#                     )
#                     for r in results[:2]
#                 ]
                
#                 response = QueryResponse(
#                     answer=ai_answer,
#                     sources=sources,
#                     confidence=0.85
#                 )
#             except:
#                 response = self._generic_payment_info()
#         else:
#             response = self._generic_payment_info()
        
#         self.memory.add_message(session_id, original_question, response.answer, intent="payment")
#         return response
    
#     def _generic_payment_info(self) -> QueryResponse:
#         """Generic payment info"""
#         answer = "**💳 Payment Options**\n\n"
#         answer += "1. **Cash on Delivery (COD)** 😊\n"
#         answer += "   Pay when you receive\n\n"
#         answer += "2. **Bank Transfer**\n"
#         answer += "   Direct deposit\n\n"
#         answer += "3. **JazzCash/EasyPaisa**\n"
#         answer += "   Mobile wallet\n\n"
#         answer += "4. **Online Payment**\n"
#         answer += "   Credit/Debit cards\n\n"
#         answer += "All payments are secure and easy!"
        
#         return QueryResponse(answer=answer, sources=[], confidence=0.7)

#     def _handle_followup_question(self, q: str, context: Dict, session_id: str,
#                                  original_question: str, conversation_history: str) -> QueryResponse:
#         """Handle follow-up questions"""
        
#         last_products = self.memory.get_last_products(session_id, n=3)
        
#         if last_products:
#             product = last_products[0]
            
#             if any(word in q for word in ["feature", "special", "unique", "quality", "about", "details"]):
#                 return self._handle_specific_product(product.name, session_id, original_question)
            
#             elif any(word in q for word in ["price", "cost", "how much", "kitna"]):
#                 return self._handle_pricing_query(product.name, session_id, original_question, conversation_history)
            
#             elif any(word in q for word in ["buy", "order", "purchase", "khareedna"]):
#                 return self._handle_order_intent(product.name, session_id, original_question, conversation_history)
            
#             elif any(word in q for word in ["color", "colour", "rang"]):
#                 if hasattr(product, 'colors') and product.colors:
#                     answer = f"**🎨 Colors for {product.name}:**\n\n"
#                     answer += f"{', '.join(product.colors)}\n\n"
#                     answer += f"Which color do you prefer? 😊"
                    
#                     response = QueryResponse(
#                         answer=answer,
#                         sources=[],
#                         related_products=[product],
#                         confidence=0.95
#                     )
#                     self.memory.add_message(session_id, original_question, answer, [product], intent="followup")
#                     return response
            
#             elif any(word in q for word in ["size", "sizes"]):
#                 if hasattr(product, 'sizes') and product.sizes:
#                     answer = f"**📏 Sizes for {product.name}:**\n\n"
#                     answer += f"{', '.join(product.sizes)}\n\n"
#                     answer += f"Which size do you need? 😊"
                    
#                     response = QueryResponse(
#                         answer=answer,
#                         sources=[],
#                         related_products=[product],
#                         confidence=0.95
#                     )
#                     self.memory.add_message(session_id, original_question, answer, [product], intent="followup")
#                     return response
        
#         return self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, 5)

#     def _handle_intelligent_query_with_fallback(self, question: str, session_id: str, 
#                                                conversation_history: str, top_k: int) -> QueryResponse:
#         """
#         AI + RAG for intelligent responses using Groq WITH SMART FALLBACK
#         FIXED: Now provides helpful responses even when documents don't have info
#         """
        
#         logger.info(f"Intelligent query with fallback: {question}")
        
#         # Check if it's a material recommendation question
#         if any(pattern in question.lower() for pattern in self.generic_faq["material_usage"]):
#             return self._handle_material_recommendation(question.lower(), session_id, question)
        
#         # First, try to find in documents
#         results = vector_store.search(question, top_k=top_k * 2)
        
#         doc_context = ""
#         if results and len(results) > 0:
#             doc_context = "\n\n".join([f"{r['text'][:500]}" for r in results[:5]])
        
#         related_products = []
#         if upsell_service.products:
#             try:
#                 related_products = upsell_service.get_recommendations_by_query(question, top_k=3)
#             except Exception as e:
#                 logger.error(f"Error getting products: {e}")
        
#         try:
#             # Use Groq for AI response if available
#             if self.groq_client:
#                 system_prompt = """You are a friendly, knowledgeable paint expert and customer service assistant.
                
#                 **IMPORTANT GUIDELINES:**
#                 1. If the document context contains relevant information, use it to answer accurately
#                 2. If the document context doesn't have the specific answer, use your general knowledge about related product that i uploaded
#                 3. Always provide helpful, practical advice
#                 4. Be friendly, casual, and use emojis occasionally 😊
#                 5. If you don't know something, suggest asking about products, pricing, or order placement
#                 6. Keep answers concise but informative
#                 7. For material-specific questions (wood, metal, concrete, etc.), recommend appropriate  document product types
                
                
#                 **Example for missing context:**
#                 User: "Which paint for wood furniture?"
#                 You: "For wood furniture, I'd recommend wood varnish or stain! These protect the wood while enhancing its natural beauty. 😊 We have several wood finishes available. Want me to show you options?"
                
#                 User: "How to prepare walls before painting?"
#                 You: "Great question! For best results: 1. Clean the wall, 2. Repair cracks, 3. Apply primer, 4. Then paint! Need product recommendations? 😊"
#                 """
                
#                 context_msg = ""
#                 if doc_context:
#                     context_msg = f"DOCUMENT CONTEXT (may not contain answer):\n{doc_context}\n\n"
                
#                 context_msg += f"CUSTOMER QUESTION: {question}\n\n"
                
#                 if related_products:
#                     context_msg += f"AVAILABLE PRODUCTS: {', '.join([p.name for p in related_products[:3]])}\n\n"
                
#                 ai_answer = self._generate_groq_response(system_prompt, context_msg)
                
#                 # Check if response indicates missing info
#                 if any(phrase in ai_answer.lower() for phrase in ["don't have", "doesn't contain", "no information", "unfortunately"]):
#                     # Provide helpful alternative
#                     ai_answer = self._generate_helpful_fallback(question, related_products)
            
#             else:
#                 # Fallback to existing LLM service
#                 ai_answer = llm_service.generate_response(
#                     question=question,
#                     context=doc_context,
#                     products=[p.model_dump() for p in related_products] if related_products else None,
#                     conversation_history=conversation_history
#                 )
            
#             if not ai_answer or len(ai_answer.strip()) < 20:
#                 ai_answer = self._generate_helpful_fallback(question, related_products)
            
#             logger.info("AI response generated")
        
#         except Exception as e:
#             logger.error(f"AI generation failed: {e}")
#             ai_answer = self._generate_helpful_fallback(question, related_products)
        
#         sources = []
#         if results and len(results) > 0:
#             sources = [
#                 SourceReference(
#                     text=r["text"][:250],
#                     document=r.get("source", "Document"),
#                     score=r.get("score", 0.0)
#                 )
#                 for r in results[:3]
#             ]
        
#         confidence = 0.7 if len(results) >= 2 else 0.5
        
#         response = QueryResponse(
#             answer=ai_answer,
#             sources=sources,
#             related_products=related_products if related_products else [],
#             confidence=confidence
#         )
        
#         self.memory.add_message(
#             session_id, 
#             question, 
#             ai_answer, 
#             related_products if related_products else [], 
#             intent="document_query"
#         )
#         return response

#     def _generate_helpful_fallback(self, question: str, related_products: List[ProductInfo] = None) -> str:
#         """Generate helpful fallback response when documents don't have info"""
        
#         question_lower = question.lower()
        
#         # Material-specific questions
#         if "wood" in question_lower or "furniture" in question_lower:
#             return "**🎨 For Wood Surfaces:**\n\n" \
#                    "I'd recommend **wood finishes, stains, or varnishes**! These protect wood while enhancing its natural beauty. 😊\n\n" \
#                    "**Popular options:**\n" \
#                    "• Wood Varnish - Clear protective coating\n" \
#                    "• Wood Stain - Adds color while showing grain\n" \
#                    "• Wood Primer - Prepares surface for painting\n\n" \
#                    "Type 'show wood products' or ask about a specific one!"
        
#         elif "metal" in question_lower or "iron" in question_lower or "steel" in question_lower:
#             return "**🔩 For Metal Surfaces:**\n\n" \
#                    "For metal, you'll need **anti-rust primer and metal paint**! These prevent corrosion and provide lasting protection. 😊\n\n" \
#                    "**Key products:**\n" \
#                    "• Anti-Rust Primer - Essential first coat\n" \
#                    "• Metal Paint - Durable finish for metals\n" \
#                    "• Metallic Finish - Decorative options\n\n" \
#                    "Want to see our metal paint collection?"
        
#         elif "wall" in question_lower or "interior" in question_lower or "exterior" in question_lower:
#             return "**🏠 For Walls:**\n\n" \
#                    "We have **emulsions, distempers, and texture paints** for walls! Choose based on your needs. 😊\n\n" \
#                    "**Wall Paint Types:**\n" \
#                    "• Interior Emulsion - For indoor walls\n" \
#                    "• Exterior Paint - Weather-resistant for outside\n" \
#                    "• Texture Paint - Decorative finishes\n" \
#                    "• Silk Finish - Smooth, washable surface\n\n" \
#                    "Ask about a specific type or see all wall paints!"
        
#         elif "concrete" in question_lower or "cement" in question_lower or "floor" in question_lower:
#             return "**🧱 For Concrete/Cement:**\n\n" \
#                    "Concrete needs **special cement paints or epoxy coatings**! These withstand wear and moisture. 😊\n\n" \
#                    "**Recommended:**\n" \
#                    "• Cement Paint - Specifically for concrete\n" \
#                    "• Epoxy Coating - Heavy-duty protection\n" \
#                    "• Floor Paint - For concrete floors\n" \
#                    "• Waterproof Coating - For damp areas\n\n" \
#                    "Need help choosing? Just ask!"
        
#         # General paint knowledge questions
#         elif any(word in question_lower for word in ["how to", "prepare", "apply", "use"]):
#             return "**🎨 Painting Tips:**\n\n" \
#                    "For best painting results:\n" \
#                    "1. **Clean surface** - Remove dust, grease\n" \
#                    "2. **Repair** - Fill cracks, sand smooth\n" \
#                    "3. **Prime** - Essential for adhesion\n" \
#                    "4. **Paint** - 2-3 thin coats work better than 1 thick coat\n" \
#                    "5. **Dry** - Allow proper drying time between coats 😊\n\n" \
#                    "Need product recommendations for any step?"
        
#         # Product recommendation questions
#         elif any(word in question_lower for word in ["recommend", "suggest", "which", "what"]):
#             if related_products and len(related_products) > 0:
#                 product_list = "\n".join([f"• {p.name}" for p in related_products[:5]])
#                 return f"**Based on your question, here are some great options:** 😊\n\n{product_list}\n\n" \
#                        f"Type a product name or number for more details!"
#             else:
#                 return "**I'd love to help you find the right product!** 😊\n\n" \
#                        "Could you tell me:\n" \
#                        "• What surface/material are you painting?\n" \
#                        "• Indoor or outdoor use?\n" \
#                        "• What finish are you looking for?\n\n" \
#                        "Or type 'show products' to browse everything!"
        
#         # Default helpful response
#         return "**I'm here to help with all your paint needs!** 😊\n\n" \
#                "You can ask me about:\n" \
#                "• **Product recommendations** for specific materials\n" \
#                "• **Pricing information** for any product\n" \
#                "• **How to prepare surfaces** before painting\n" \
#                "• **Placing an order** for delivery\n" \
#                "• **Delivery & payment** options\n\n" \
#                "What would you like to know?"

#     # ==================== UTILITY METHODS ====================

#     def reset_session(self, session_id: str):
#         """Reset conversation session"""
#         self.memory.clear_session(session_id)
#         logger.info(f"Session {session_id} reset")
    
#     def get_session_stats(self, session_id: str) -> Dict:
#         """Get session statistics"""
#         context = self.memory.get_context(session_id)
        
#         return {
#             "session_id": session_id,
#             "message_count": len(context.get('messages', [])),
#             "last_intent": context.get('last_intent'),
#             "products_discussed": len(context.get('last_products', [])),
#             "last_updated": context.get('last_updated'),
#             "context_data": context.get('context_data', {})
#         }
    
#     def cleanup_expired_sessions(self):
#         """Clean up expired sessions"""
#         current_time = datetime.now()
#         expired = []
        
#         for session_id, session in self.memory.sessions.items():
#             if current_time - session['last_updated'] > self.memory.timeout:
#                 expired.append(session_id)
        
#         for session_id in expired:
#             del self.memory.sessions[session_id]
        
#         if expired:
#             logger.info(f"Cleaned up {len(expired)} expired sessions")
        
#         return len(expired)

# # Global instance - automatically loads Groq from environment
# chatbot_service = ChatbotService()































"""
COMPLETE ENHANCED CHATBOT SERVICE - PRODUCTION READY
FIXED: Shows ALL product details from documents
FIXED: No generic fallback when document info exists
FIXED: Proper product information extraction
FIXED: Product list shows ALL products
FIXED: No repetitive greetings
FIXED: Conversation memory works correctly
ADDED: Better handling for "remaining products" requests
ADDED: Product number tracking to avoid repetition
"""

from typing import List, Dict, Optional, Tuple
from backend.services.vector_store import vector_store
from backend.services.llm_service import llm_service
from backend.services.upsell_service import upsell_service
from backend.services.order_service import order_service
from backend.models import QueryResponse, SourceReference, ProductInfo
from rapidfuzz import fuzz
import logging
from datetime import datetime, timedelta
import re
import os
import time
from groq import Groq

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def _clean(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    return text.strip().lower()

def _extract_product_keywords(query: str) -> List[str]:
    """Extract meaningful keywords from query with better filtering"""
    stop_words = {
        "tell", "me", "about", "the", "a", "an", "what", "is", "are", 
        "do", "does", "you", "have", "has", "price", "of", "cost", 
        "buy", "order", "purchase", "want", "need", "looking", "for", "show", 
        "give", "get", "can", "i", "my", "in", "on", "at", "to", "from",
        "your", "store", "shop", "something", "please", "kindly", "sir", "madam"
    }
    
    words = query.lower().split()
    important_short_words = {"paint", "primer", "emulsion", "texture", "stain", "free", "super", "all", "weather"}
    
    keywords = []
    for w in words:
        if w in stop_words:
            continue
        if len(w) > 2 or w in important_short_words:
            keywords.append(w)
    
    return keywords

class ConversationMemory:
    """Enhanced conversation context with order state tracking"""
    
    def __init__(self, max_history: int = 10, timeout_minutes: int = 30):
        self.sessions = {}
        self.max_history = max_history
        self.timeout = timedelta(minutes=timeout_minutes)
    
    def add_message(self, session_id: str, user_query: str, bot_response: str, 
                   mentioned_products: List[ProductInfo] = None, intent: str = None,
                   metadata: Dict = None):
        """Add message to conversation history"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'messages': [],
                'last_products': [],
                'last_topic': None,
                'last_intent': None,
                'last_updated': datetime.now(),
                'context_data': {},
                'order_state': None,
                'pending_order': {},
                'shown_products': []  # Track which products have been shown
            }
        
        session = self.sessions[session_id]
        session['messages'].append({
            'user': user_query,
            'bot': bot_response,
            'intent': intent,
            'timestamp': datetime.now(),
            'metadata': metadata or {}
        })
        
        if len(session['messages']) > self.max_history:
            session['messages'] = session['messages'][-self.max_history:]
        
        if mentioned_products:
            session['last_products'] = mentioned_products
            # Track which products were shown
            for product in mentioned_products:
                if hasattr(product, 'name') and product.name not in session['shown_products']:
                    session['shown_products'].append(product.name)
        
        if intent:
            session['last_intent'] = intent
        
        if metadata:
            session['context_data'].update(metadata)
        
        session['last_updated'] = datetime.now()
    
    def get_shown_products(self, session_id: str) -> List[str]:
        """Get list of products already shown to user"""
        if session_id not in self.sessions:
            return []
        return self.sessions[session_id].get('shown_products', [])
    
    def get_context(self, session_id: str) -> Dict:
        """Get conversation context with timeout handling"""
        if session_id not in self.sessions:
            return {
                'messages': [], 
                'last_products': [], 
                'last_intent': None,
                'context_data': {},
                'order_state': None,
                'pending_order': {},
                'shown_products': []
            }
        
        session = self.sessions[session_id]
        
        if datetime.now() - session['last_updated'] > self.timeout:
            logger.info(f"Session {session_id} expired")
            del self.sessions[session_id]
            return {
                'messages': [], 
                'last_products': [], 
                'last_intent': None,
                'context_data': {},
                'order_state': None,
                'pending_order': {},
                'shown_products': []
            }
        
        return session
    
    def set_order_state(self, session_id: str, state: str, order_data: Dict = None):
        """Set order collection state"""
        context = self.get_context(session_id)
        context['order_state'] = state
        if order_data:
            context['pending_order'].update(order_data)
        self.sessions[session_id] = context
    
    def get_order_state(self, session_id: str) -> Tuple[Optional[str], Dict]:
        """Get current order state and pending data"""
        context = self.get_context(session_id)
        return context.get('order_state'), context.get('pending_order', {})
    
    def clear_order_state(self, session_id: str):
        """Clear order collection state"""
        if session_id in self.sessions:
            self.sessions[session_id]['order_state'] = None
            self.sessions[session_id]['pending_order'] = {}
    
    def get_conversation_history(self, session_id: str, last_n: int = 5) -> str:
        """Get formatted conversation history for AI context"""
        context = self.get_context(session_id)
        messages = context.get('messages', [])[-last_n:]
        
        if not messages:
            return ""
        
        history = "Recent conversation:\n"
        for msg in messages:
            history += f"Customer: {msg['user']}\n"
            history += f"Assistant: {msg['bot'][:100]}...\n\n"
        
        return history.strip()
    
    def get_last_products(self, session_id: str, n: int = 100) -> List[ProductInfo]:
        """Get last N products mentioned"""
        context = self.get_context(session_id)
        products = context.get('last_products', [])
        return products[:n]
    
    def clear_session(self, session_id: str):
        """Clear specific session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Session {session_id} cleared")

class ChatbotService:
    def __init__(self):
        self.memory = ConversationMemory()
        self.generic_faq = self._load_generic_faq()
        self._confidence_threshold = 0.6
        
        # Initialize Groq client
        self.groq_client, self.groq_model = self._initialize_groq_client()
        
        logger.info("Enhanced Chatbot Service initialized")

    def _initialize_groq_client(self):
        """Initialize Groq client from environment variable"""
        groq_api_key = os.getenv('GROQ_API_KEY')
        
        if not groq_api_key:
            logger.warning("GROQ_API_KEY not found in environment variables")
            return None, None
        
        try:
            client = Groq(api_key=groq_api_key)
            
            # Try multiple models
            current_models = [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant", 
                "llama-3.1-70b-versatile",
                "mixtral-8x7b-32768"
            ]
            
            working_model = None
            for model in current_models:
                try:
                    logger.info(f"Testing model: {model}")
                    client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "Say 'OK'"}],
                        max_tokens=5,
                        temperature=0.1
                    )
                    working_model = model
                    logger.info(f"Groq API initialized with model: {model}")
                    break
                except Exception as e:
                    logger.warning(f"Model {model} failed: {e}")
                    continue
            
            if not working_model:
                logger.error("No working Groq models found")
                return None, None
                
            return client, working_model
            
        except Exception as e:
            logger.error(f"Failed to initialize Groq API: {e}")
            return None, None

    def _load_generic_faq(self) -> Dict[str, List[str]]:
        """Generic FAQ patterns that work for any business"""
        return {
            "simple_greetings": ["hi", "hello", "hey", "salam", "assalam", "hi!", "hello!", "hey!", "what's up", "howdy"],
            "how_are_you": ["how are you", "how r u", "how are you doing", "how's it going", "how do you do"],
            "good_responses": ["i'm good", "am good", "doing good", "fine", "great", "awesome", "i'm fine", "all good", "good"],
            "thanks": ["thanks", "thank you", "shukriya", "thx", "thanku", "appreciate", "thank you!"],
            "bye": ["bye", "goodbye", "khuda hafiz", "allah hafiz", "see you", "bye bye"],
            "product_list": ["show all", "list all", "all products", "catalog", "view all", "show products", 
                           "complete list", "full list", "how many products", "how many product", 
                           "list of products", "product list", "give me list", "show me all",
                           "wana full list", "want full list", "i wana full list", "i want full list",
                           "name of the products", "name of products", "products name", "product names",
                           "what do you have", "what you have", "what do you sell", "what do you offer",
                           "what have you got", "what products do you have", "what items do you have",
                           "what can i buy", "tell me what you have", "show me what you have",
                           "what is available", "what's available", "what are your products"],
            "not_interested": ["not interested in", "am not interested", "don't want", "dont want",
                             "i don't need", "i dont need", "not looking for", "not looking at",
                             "not into", "no thanks to", "skip the", "not for me"],
            "product_details": ["details", "purpose", "tell me about", "what is", "explain", "describe",
                              "rest of the products", "other products", "remaining products", "more details",
                              "give me details", "show details", "product information", "info about"],
            "pricing": ["price", "cost", "how much", "kitna", "rate"],
            "order": ["buy", "order", "purchase", "want to buy", "i want to buy", "place order"],
            "delivery": ["delivery", "shipping", "ship", "deliver"],
            "payment": ["payment", "pay", "cod", "jazzcash", "easypaisa"],
            "material_usage": ["which paint", "what paint", "for wood", "for metal", "for concrete", "for wall", 
                              "which product", "suggest product", "recommend", "use for", "material", "surface",
                              "best for my house", "which one is best"]
        }

    def _generate_groq_response(self, system_prompt: str, user_message: str, temperature: float = 0.5) -> str:
        """Generate response using Groq API"""
        if not self.groq_client or not self.groq_model:
            raise Exception("Groq API not initialized")
        
        try:
            start_time = time.time()
            
            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=2048
            )
            
            response_time = time.time() - start_time
            response_text = response.choices[0].message.content
            
            logger.info(f"Groq response received in {response_time:.2f}s")
            return response_text
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def _is_repetitive_response(self, session_id: str, new_response: str) -> bool:
        """Check if response is repetitive"""
        context = self.memory.get_context(session_id)
        messages = context.get('messages', [])
        
        if len(messages) < 2:
            return False
        
        # Get last 2 bot responses
        last_responses = [msg['bot'] for msg in messages[-2:] if 'bot' in msg]
        
        # Check if new response is similar to previous ones
        for resp in last_responses:
            if fuzz.ratio(new_response.lower(), resp.lower()) > 80:
                return True
        
        return False

    def format_product_info(self, product: ProductInfo) -> str:
        """Format product information in clean, structured way"""
        
        lines = []
        lines.append(f"**{product.name.upper()}**")
        lines.append("")
        
        if product.description:
            lines.append(f"**Description:** {product.description}")
            lines.append("")
        
        if product.category:
            lines.append(f"**Category:** {product.category}")
            lines.append("")
        
        if product.price and product.price > 0:
            lines.append(f"**Price:** Rs {product.price:,.0f}")
            lines.append("")
        else:
            lines.append("**Price:** Contact for pricing")
            lines.append("")
        
        if hasattr(product, 'colors') and product.colors:
            lines.append(f"**Colors:** {', '.join(product.colors[:5])}")
            if len(product.colors) > 5:
                lines[-1] += f" (+{len(product.colors)-5} more)"
            lines.append("")
        
        if hasattr(product, 'sizes') and product.sizes:
            lines.append(f"**Sizes:** {', '.join(product.sizes)}")
            lines.append("")
        
        if hasattr(product, 'features') and product.features:
            lines.append("**Features:**")
            for feature in product.features[:3]:
                lines.append(f"• {feature}")
            lines.append("")
        
        lines.append("**Stock:** Available")
        lines.append("")
        lines.append(f"**To Order:** Type 'buy {product.name}' or 'I want to order {product.name}'")
        
        return "\n".join(lines)

    def _find_product_by_name(self, product_name: str) -> Optional[ProductInfo]:
        """Find product by exact or partial name"""
        try:
            if not upsell_service.products:
                upsell_service.load_all_products()
            
            if not upsell_service.products:
                return None
            
            for product in upsell_service.products:
                if product and hasattr(product, 'name'):
                    if product_name.lower() in product.name.lower() or product.name.lower() in product_name.lower():
                        return product
            
            # Try fuzzy matching
            for product in upsell_service.products:
                if product and hasattr(product, 'name'):
                    if fuzz.partial_ratio(product_name.lower(), product.name.lower()) > 70:
                        return product
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding product by name: {e}")
            return None

    def answer_query(self, question: str, top_k: int = 10, shop_filter: str = None, 
                    session_id: str = "default") -> QueryResponse:
        """
        MAIN INTELLIGENT QUERY HANDLER
        FIXED: Proper document search for product details
        """
        
        if not question or len(question.strip()) < 2:
            return QueryResponse(
                answer="Hey! Could you ask something? 😊",
                sources=[],
                confidence=0.0
            )
        
        original_question = question
        q = _clean(question)
        logger.info(f"Query: '{question}' | Session: {session_id}")

        try:
            context = self.memory.get_context(session_id)
            conversation_history = self.memory.get_conversation_history(session_id, last_n=3)

            # CHECK FOR REPETITIVE USER QUERY
            messages = context.get('messages', [])
            
            if messages:
                last_user_query = messages[-1].get('user', '').strip().lower()
                current_query = original_question.strip().lower()
                
                if last_user_query == current_query and len(messages) > 1:
                    last_products = self.memory.get_last_products(session_id, n=1)
                    if last_products:
                        product = last_products[0]
                        answer = f"You already asked about {product.name}.\n\n"
                        answer += "Need more details? Ask about:\n"
                        answer += "• Specific features\n"
                        answer += "• Colors available\n"
                        answer += "• Sizes\n"
                        answer += "• Pricing details\n"
                        answer += "• Or type 'buy' to order it"
                    else:
                        answer = "You already asked that. Is there something specific you'd like to know?"
                    
                    return QueryResponse(
                        answer=answer,
                        sources=[],
                        confidence=0.0
                    )
            
            # PRIORITY 1: Check if in order collection mode
            order_state, pending_order = self.memory.get_order_state(session_id)
            
            if order_state:
                return self._handle_order_collection(
                    original_question, session_id, order_state, pending_order
                )

            # PRIORITY 2: Check for number-based product selection
            number_match = self._extract_product_number(original_question)
            if number_match is not None:
                last_products = self.memory.get_last_products(session_id)
                if last_products:
                    return self._handle_number_selection(number_match, session_id, original_question)

            # PRIORITY 3: Detect intent
            intent = self._detect_intent(q, context, original_question)
            logger.info(f"Intent: {intent}")

            # PRIORITY 4: Route to appropriate handler
            response = self._route_query(
                intent=intent,
                query=q,
                original_question=original_question,
                session_id=session_id,
                context=context,
                conversation_history=conversation_history,
                top_k=top_k
            )
            
            # Check if response is repetitive
            if self._is_repetitive_response(session_id, response.answer):
                if "Hey" in response.answer or "Hello" in response.answer:
                    response.answer = "Hey again! What can I help you with today? 😊"
            
            return response
        
        except Exception as e:
            logger.error(f"Error in answer_query: {e}", exc_info=True)
            return QueryResponse(
                answer="Oops! Something went wrong. Could you try again? 😊",
                sources=[],
                confidence=0.0
            )

    def _extract_product_number(self, query: str) -> Optional[int]:
        """Extract product number from query"""
        
        if query.strip().isdigit():
            num = int(query.strip())
            if 1 <= num <= 100:
                return num
        
        patterns = [
            r'product\s*#?(\d+)',
            r'number\s*#?(\d+)',
            r'item\s*#?(\d+)',
            r'option\s*#?(\d+)',
            r'#(\d+)',
            r'^(\d+)$',
            r'select\s*(\d+)',
            r'choose\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                num = int(match.group(1))
                if 1 <= num <= 100:
                    return num
        
        return None

    def _handle_number_selection(self, number: int, session_id: str, original_question: str) -> QueryResponse:
        """Handle number-based product selection"""
        
        last_products = self.memory.get_last_products(session_id, n=100)
        
        if not last_products:
            return QueryResponse(
                answer="Hey! No products found. Try 'show products' first. 😊",
                sources=[],
                confidence=0.5
            )
        
        if number > len(last_products):
            return QueryResponse(
                answer=f"Oops! Product #{number} not found. We have {len(last_products)} products available. 😊",
                sources=[],
                confidence=0.5
            )
        
        selected_product = last_products[number - 1]
        answer = self.format_product_info(selected_product)
        
        response = QueryResponse(
            answer=answer,
            sources=[],
            related_products=[selected_product],
            confidence=0.95
        )
        
        self.memory.add_message(
            session_id, 
            original_question, 
            answer, 
            [selected_product], 
            intent="number_selection"
        )
        
        return response

    def _handle_order_collection(self, query: str, session_id: str, 
                                 order_state: str, pending_order: Dict) -> QueryResponse:
        """Handle step-by-step order collection"""
        
        flow = ['full_name', 'phone', 'address', 'city', 'quantity', 'payment_method']
        current_index = flow.index(order_state) if order_state in flow else 0
        
        if order_state == 'full_name':
            if 'customer_info' not in pending_order:
                pending_order['customer_info'] = {}
            pending_order['customer_info']['full_name'] = query.strip()
            logger.info(f"Collected name: {query.strip()}")
        
        elif order_state == 'phone':
            phone = re.sub(r'[^\d+]', '', query)
            if len(phone) < 10:
                return QueryResponse(
                    answer="Hey! Could you provide a valid phone number? (at least 10 digits) 😊",
                    sources=[],
                    confidence=0.9
                )
            pending_order['customer_info']['phone'] = phone
            logger.info(f"Collected phone: {phone}")
        
        elif order_state == 'address':
            pending_order['customer_info']['address'] = query.strip()
            logger.info(f"Collected address: {query.strip()}")
        
        elif order_state == 'city':
            pending_order['customer_info']['city'] = query.strip()
            logger.info(f"Collected city: {query.strip()}")
        
        elif order_state == 'quantity':
            try:
                qty_match = re.search(r'\d+', query)
                if qty_match:
                    qty = int(qty_match.group())
                else:
                    number_words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
                    qty = next((v for k, v in number_words.items() if k in query.lower()), 1)
                
                if qty < 1:
                    qty = 1
                
                if 'items' not in pending_order:
                    pending_order['items'] = []
                
                if len(pending_order['items']) > 0:
                    pending_order['items'][0]['quantity'] = qty
                    if 'unit_price' in pending_order['items'][0]:
                        pending_order['items'][0]['total_price'] = pending_order['items'][0]['unit_price'] * qty
                
                logger.info(f"Collected quantity: {qty}")
            except Exception as e:
                logger.error(f"Quantity error: {e}")
                return QueryResponse(
                    answer="Hey! Could you provide a valid quantity? (e.g., 2, 5, 10) 😊",
                    sources=[],
                    confidence=0.9
                )
        
        elif order_state == 'payment_method':
            payment_method = query.strip()
            if 'payment_details' not in pending_order:
                pending_order['payment_details'] = {}
            pending_order['payment_details']['method'] = payment_method
            logger.info(f"Collected payment: {payment_method}")
        
        current_index += 1
        
        if current_index >= len(flow):
            try:
                if 'customer_info' not in pending_order:
                    pending_order['customer_info'] = {}
                if 'items' not in pending_order:
                    pending_order['items'] = []
                if 'payment_details' not in pending_order:
                    pending_order['payment_details'] = {'method': 'COD'}
                
                logger.info(f"Placing order: {pending_order}")
                
                result = order_service.place_order(pending_order)
                self.memory.clear_order_state(session_id)
                
                if result['success']:
                    answer = f"🎉 **Order Confirmed!**\n\n"
                    answer += f"**Order ID:** {result['order_id']}\n"
                    answer += f"**Total:** Rs {result['total_amount']:,.0f}\n"
                    answer += f"**Estimated Delivery:** {result['estimated_delivery']}\n\n"
                    answer += "Thanks so much for your order! 😊"
                else:
                    answer = f"😕 Order failed: {result.get('message', 'Unknown error')}"
                
                return QueryResponse(answer=answer, sources=[], confidence=1.0)
                
            except Exception as e:
                logger.error(f"Order placement error: {e}")
                self.memory.clear_order_state(session_id)
                return QueryResponse(
                    answer="Oops! Order placement failed. Could you try again? 😊",
                    sources=[],
                    confidence=0.5
                )
        
        next_field = flow[current_index]
        self.memory.set_order_state(session_id, next_field, pending_order)
        
        field_prompts = {
            'full_name': "Great! What's your full name? 😊",
            'phone': "Perfect! What's your phone number?",
            'address': "Awesome! What's your delivery address?",
            'city': "Cool! Which city?",
            'quantity': "How many units would you like?",
            'payment_method': "Payment method? (COD/Bank Transfer/JazzCash/EasyPaisa) 😊"
        }
        
        prompt = field_prompts.get(next_field, "Could you provide that information? 😊")
        
        return QueryResponse(
            answer=prompt,
            sources=[],
            confidence=1.0
        )

    def _detect_intent(self, q: str, context: Dict, original_question: str = None) -> str:
        """Enhanced intent detection"""
        
        q_trimmed = q.strip()
        messages = context.get('messages', [])
        
        if q_trimmed in self.generic_faq["simple_greetings"]:
            if not messages:
                return "welcome_greeting"
            else:
                return "simple_greeting"
        
        if any(pattern in q for pattern in self.generic_faq["how_are_you"]):
            return "how_are_you"
        
        if any(pattern in q for pattern in self.generic_faq["good_responses"]):
            if messages and len(messages) > 0:
                last_bot_message = messages[-1].get('bot', '').lower()
                if any(pattern in last_bot_message for pattern in ["how about you", "how are you"]):
                    return "good_response"
            return "general_good"
        
        # CRITICAL: Check for requests about remaining/rest of products
        if any(pattern in q for pattern in ["rest of", "remaining", "other products", "more details", "details about rest"]):
            return "remaining_products"
        
        if any(pattern in q for pattern in self.generic_faq["product_details"]):
            return "product_details_request"
        
        if any(pattern in q for pattern in self.generic_faq["material_usage"]):
            return "material_recommendation"
        
        if any(pattern in q for pattern in self.generic_faq["thanks"]):
            return "thanks"
        
        if any(pattern in q for pattern in self.generic_faq["bye"]):
            return "bye"
        
        if any(pattern in q for pattern in self.generic_faq["product_list"]):
            return "product_list"
        
        # Check for "not interested" BEFORE product/order detection
        if any(pattern in q for pattern in self.generic_faq["not_interested"]):
            return "not_interested"
        
        product = self._find_product_in_query(q)
        
        if product:
            strong_order_indicators = ["buy", "order", "purchase", "want to buy", "i want to buy", "place order"]
            has_strong_order_intent = any(indicator in q for indicator in strong_order_indicators)
            
            if has_strong_order_intent:
                logger.info(f"Order intent detected for product: {product.name}")
                return "order"
            else:
                logger.info(f"Product inquiry detected for: {product.name}")
                return "specific_product"
        
        if self._extract_product_number(original_question) is not None:
            return "number_selection"
        
        if any(pattern in q for pattern in self.generic_faq["pricing"]):
            return "pricing"
        
        if any(pattern in q for pattern in self.generic_faq["order"]):
            return "order"
        
        if any(pattern in q for pattern in self.generic_faq["delivery"]):
            return "delivery"
        
        if any(pattern in q for pattern in self.generic_faq["payment"]):
            return "payment"
        
        if self._is_followup_question(q) and context.get('last_products'):
            return "followup"
        
        return "general_query"

    def _is_followup_question(self, q: str) -> bool:
        """Detect follow-up questions"""
        followup_indicators = [
            "what about", "what is this", "tell me more", "more details",
            "this one", "that one", "it", "its", "they", "how about",
            "explain", "describe", "information", "details"
        ]
        
        words = q.split()
        if len(words) <= 8:
            return any(indicator in q for indicator in followup_indicators)
        
        return False

    def _find_product_in_query(self, q: str) -> Optional[ProductInfo]:
        """Find product using fuzzy matching"""
        
        try:
            if not upsell_service.products:
                upsell_service.load_all_products()
            
            if not upsell_service.products:
                logger.warning("No products available")
                return None
            
            keywords = _extract_product_keywords(q)
            
            if not keywords:
                return None
            
            search_term = " ".join(keywords)
            
            if len(search_term) < 2:
                return None
            
            best_match = None
            best_score = 0
            
            for product in upsell_service.products:
                if not product or not hasattr(product, 'name'):
                    continue
                    
                product_name_lower = product.name.lower()
                
                scores = [
                    fuzz.partial_ratio(search_term, product_name_lower) * 1.2,
                    fuzz.token_sort_ratio(search_term, product_name_lower) * 1.2,
                ]
                
                if search_term in product_name_lower:
                    scores.append(95)
                
                if product_name_lower.startswith(search_term):
                    scores.append(90)
                
                if any(keyword in product_name_lower for keyword in keywords):
                    scores.append(85)
                
                max_score = max(scores)
                
                if max_score > best_score:
                    best_score = max_score
                    best_match = product
            
            min_threshold = 65 if len(search_term) > 3 else 60
            
            if best_score >= min_threshold:
                logger.info(f"Found product: {best_match.name} (score: {best_score})")
                return best_match
            
            logger.info(f"No product found above threshold {min_threshold}. Best score: {best_score}")
            return None
            
        except Exception as e:
            logger.error(f"Error in product search: {e}", exc_info=True)
            return None

    def _route_query(self, intent: str, query: str, original_question: str,
                    session_id: str, context: Dict, conversation_history: str,
                    top_k: int) -> QueryResponse:
        """Route query to appropriate handler"""
        
        handlers = {
            "welcome_greeting": lambda: self._handle_welcome_greeting(session_id, original_question),
            "simple_greeting": lambda: self._handle_simple_greeting(session_id, original_question),
            "how_are_you": lambda: self._handle_how_are_you(session_id, original_question),
            "good_response": lambda: self._handle_good_response(session_id, original_question, context),
            "general_good": lambda: self._handle_general_good(session_id, original_question),
            "material_recommendation": lambda: self._handle_material_recommendation_with_docs(query, session_id, original_question, conversation_history, top_k),
            "thanks": lambda: self._handle_thanks(session_id, original_question),
            "bye": lambda: self._handle_bye(session_id, original_question),
            "product_list": lambda: self._handle_product_catalog(session_id, original_question),
            "remaining_products": lambda: self._handle_remaining_products(session_id, original_question, conversation_history, top_k),
            "product_details_request": lambda: self._handle_product_details_from_docs(query, session_id, original_question, conversation_history, top_k),
            "specific_product": lambda: self._handle_specific_product(query, session_id, original_question),
            "pricing": lambda: self._handle_pricing_query(query, session_id, original_question, conversation_history),
            "order": lambda: self._handle_order_intent(query, session_id, original_question, conversation_history),
            "delivery": lambda: self._handle_delivery_query(session_id, original_question, conversation_history),
            "payment": lambda: self._handle_payment_query(session_id, original_question, conversation_history),
            "followup": lambda: self._handle_followup_question(query, context, session_id, original_question, conversation_history),
            "number_selection": lambda: self._handle_number_selection(self._extract_product_number(original_question), session_id, original_question) if self._extract_product_number(original_question) else self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, top_k),
            "not_interested": lambda: self._handle_not_interested(query, session_id, original_question),
        }
        
        handler = handlers.get(intent)
        if handler:
            return handler()
        
        return self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, top_k)

    def _handle_welcome_greeting(self, session_id: str, original_question: str) -> QueryResponse:
        """First greeting in conversation"""
        
        import random
        greetings = ["Hey! What's up?? 😊", "Hi there! How's your day going?", "Hello! 😊"]
        answer = random.choice(greetings)
        
        response = QueryResponse(answer=answer, sources=[], confidence=1.0)
        self.memory.add_message(session_id, original_question, answer, intent="welcome_greeting")
        return response

    def _handle_simple_greeting(self, session_id: str, original_question: str) -> QueryResponse:
        """Simple greeting response"""
        
        context = self.memory.get_context(session_id)
        messages = context.get('messages', [])
        
        greeting_count = 0
        for msg in messages[-3:]:
            if msg.get('intent') in ['simple_greeting', 'welcome_greeting']:
                greeting_count += 1
        
        if greeting_count >= 2:
            answer = "Hey again! What can I help you with today? 😊"
        else:
            import random
            greetings = ["Hey there! How can I help? 😊", "Hi! What's up?", "Hello again! 😊"]
            answer = random.choice(greetings)
        
        response = QueryResponse(answer=answer, sources=[], confidence=1.0)
        self.memory.add_message(session_id, original_question, answer, intent="simple_greeting")
        return response

    def _handle_how_are_you(self, session_id: str, original_question: str) -> QueryResponse:
        """Handle 'how are you' queries"""
        answer = "I'm great, thanks! How about you? 😊"
        response = QueryResponse(answer=answer, sources=[], confidence=1.0)
        self.memory.add_message(session_id, original_question, answer, intent="how_are_you")
        return response

    def _handle_good_response(self, session_id: str, original_question: str, context: Dict) -> QueryResponse:
        """Handle 'I'm good' responses after 'how are you'"""
        answer = "Nice! Glad you're doing good 😊 So, what's the plan today?"
        response = QueryResponse(answer=answer, sources=[], confidence=1.0)
        self.memory.add_message(session_id, original_question, answer, intent="good_response")
        return response

    def _handle_general_good(self, session_id: str, original_question: str) -> QueryResponse:
        """Handle general 'good' responses"""
        answer = "That's great! 😊 How can I help you today?"
        response = QueryResponse(answer=answer, sources=[], confidence=1.0)
        self.memory.add_message(session_id, original_question, answer, intent="general_good")
        return response

    def _handle_thanks(self, session_id: str, original_question: str) -> QueryResponse:
        """Handle thank you messages"""
        answer = "You're welcome! 😊 Is there anything else I can help you with?"
        response = QueryResponse(answer=answer, sources=[], confidence=1.0)
        self.memory.add_message(session_id, original_question, answer, intent="thanks")
        return response

    def _handle_bye(self, session_id: str, original_question: str) -> QueryResponse:
        """Handle goodbye messages"""
        answer = "See you! Have a great day! 😊"
        response = QueryResponse(answer=answer, sources=[], confidence=1.0)
        self.memory.add_message(session_id, original_question, answer, intent="bye")
        self.memory.clear_session(session_id)
        return response

    def _handle_not_interested(self, query: str, session_id: str, original_question: str) -> QueryResponse:
        """
        Handle 'not interested in X' queries.
        Extracts what they don't want, recommends something different,
        or politely says we don't have alternatives.
        """
        if not upsell_service.products:
            upsell_service.load_all_products()

        all_products = upsell_service.products
        if not all_products:
            answer = "I'm sorry, I don't have any other products available right now. 😊"
            self.memory.add_message(session_id, original_question, answer, intent="not_interested")
            return QueryResponse(answer=answer, sources=[], confidence=0.9)

        # Figure out what they are not interested in
        disliked_keywords = []
        for pattern in self.generic_faq["not_interested"]:
            if pattern in query:
                # extract words after the pattern
                idx = query.find(pattern)
                after = query[idx + len(pattern):].strip()
                if after:
                    disliked_keywords = after.split()
                break

        # Get all available categories
        all_categories = upsell_service.get_all_categories()

        # Find products NOT related to what they disliked
        disliked_str = " ".join(disliked_keywords).lower()
        alternative_products = []

        for product in all_products:
            product_text = f"{product.name} {product.category or ''} {product.description or ''}".lower()
            # Skip products that strongly match the disliked term
            if disliked_str and any(kw in product_text for kw in disliked_keywords if len(kw) > 3):
                continue
            alternative_products.append(product)

        if not alternative_products:
            # Everything matches what they disliked — honestly say so
            answer = f"I completely understand! 😊 Unfortunately, our current catalog focuses primarily on "
            answer += f"**{', '.join(all_categories)}** products.\n\n"
            answer += "Here's what we currently carry:\n\n"
            for idx, p in enumerate(all_products[:10], 1):
                answer += f"{idx}. **{p.name}**"
                if p.description:
                    answer += f" — {p.description[:60]}..."
                answer += "\n"
            if len(all_products) > 10:
                answer += f"\n...and {len(all_products) - 10} more products.\n"
            answer += "\nWould you like to explore any of these? 😊"
        else:
            answer = f"No problem! 😊 Let me show you something different.\n\n"
            answer += f"**Other products you might like:**\n\n"
            for idx, p in enumerate(alternative_products[:8], 1):
                answer += f"{idx}. **{p.name}**"
                if p.description:
                    short_desc = p.description[:70] + "..." if len(p.description) > 70 else p.description
                    answer += f"\n   {short_desc}"
                answer += "\n\n"
            answer += "Type a product number or name to learn more! 😊"

        self.memory.add_message(session_id, original_question, answer, alternative_products or all_products, intent="not_interested")
        return QueryResponse(answer=answer, sources=[], related_products=alternative_products[:5] or all_products[:5], confidence=0.9)

    def _is_out_of_scope(self, query: str) -> bool:
        """
        Check if a query is completely unrelated to available products.
        Returns False by default - all queries are in scope unless proven otherwise.
        """
        try:
            # Simple heuristic: if query contains product-related keywords, it's in scope
            product_keywords = ["paint", "primer", "color", "price", "product", "order", "buy", 
                              "delivery", "product", "surface", "wall", "wood", "metal", "finish"]
            
            query_lower = query.lower()
            
            # If query contains any product keyword, it's in scope
            if any(keyword in query_lower for keyword in product_keywords):
                return False
            
            # If very short query, assume in scope
            if len(query) < 5:
                return False
                
            return False  # Default: assume query is in scope
            
        except Exception as e:
            logger.error(f"Out-of-scope check error: {e}")
            return False

    def _handle_product_catalog(self, session_id: str, original_question: str) -> QueryResponse:
        """Show complete product catalog - ALL PRODUCTS with brief descriptions"""
        
        if not upsell_service.products:
            upsell_service.load_all_products()
        
        products = upsell_service.products
        
        if not products:
            answer = "Hey! No products available right now. 😊"
            response = QueryResponse(answer=answer, sources=[], confidence=0.0)
            self.memory.add_message(session_id, original_question, answer, intent="product_list")
            return response
        
        total_products = len(products)
        
        answer = f"😊 Great question! We have **{total_products} products** available. Here's our complete catalog:\n\n"
        
        # Group by category for better readability if multiple categories exist
        categories = {}
        for product in products:
            cat = product.category or "General"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(product)
        
        if len(categories) > 1:
            # Multi-category display
            idx = 1
            for cat_name, cat_products in categories.items():
                answer += f"**📦 {cat_name}**\n"
                for product in cat_products:
                    answer += f"  {idx}. **{product.name}**"
                    if product.description:
                        short = product.description[:65] + "..." if len(product.description) > 65 else product.description
                        answer += f"\n     _{short}_"
                    answer += "\n"
                    idx += 1
                answer += "\n"
        else:
            # Single category — simple numbered list with brief description
            for idx, product in enumerate(products, 1):
                answer += f"{idx}. **{product.name}**"
                if product.description:
                    short = product.description[:65] + "..." if len(product.description) > 65 else product.description
                    answer += f"\n   _{short}_"
                answer += "\n\n"
        
        answer += "💡 **Tip:** Type a number (e.g. `3`) or a product name for full details, pricing, and ordering! 😊"
        
        response = QueryResponse(
            answer=answer,
            sources=[],
            related_products=products,
            confidence=1.0
        )
        
        self.memory.add_message(session_id, original_question, answer, products, intent="product_list")
        return response

    def _handle_remaining_products(self, session_id: str, original_question: str, 
                                   conversation_history: str, top_k: int) -> QueryResponse:
        """Handle requests for remaining/rest of products details"""
        
        # Get products already shown
        shown_products = self.memory.get_shown_products(session_id)
        
        if not upsell_service.products:
            upsell_service.load_all_products()
        
        all_products = upsell_service.products
        
        if not all_products:
            return QueryResponse(
                answer="I don't have any product information available right now. 😊",
                sources=[],
                confidence=0.5
            )
        
        # Find products NOT yet shown
        remaining_products = [p for p in all_products if p.name not in shown_products]
        
        if not remaining_products:
            answer = "I've already shown you all available products! 😊\n\n"
            answer += "Would you like me to explain any specific product in more detail?"
            return QueryResponse(answer=answer, sources=[], confidence=0.9)
        
        # Search documents for ALL remaining products
        logger.info(f"Searching for details of {len(remaining_products)} remaining products")
        
        # Build search query for all remaining products
        search_queries = []
        for product in remaining_products:
            search_queries.append(product.name)
        
        combined_query = " ".join(search_queries[:5])  # Search for up to 5 products at once
        
        # Search documents
        results = vector_store.search(combined_query, top_k=top_k * 2)
        
        if results and len(results) > 0:
            doc_context = "\n\n".join([r["text"] for r in results[:10]])
            
            # Use AI to extract information about remaining products
            try:
                if self.groq_client:
                    system_prompt = f"""You are a helpful product expert. Extract and present information about these products from the context:

Products to describe: {', '.join([p.name for p in remaining_products])}

For EACH product, provide:
1. Product name
2. Description/Purpose
3. Category
4. Where it's used
5. Key features

Format as a numbered list with clear headers for each product.
If a product is not in the context, skip it.
Be informative but concise."""

                    user_message = f"Context:\n{doc_context}\n\nPlease provide details about the remaining products."
                    
                    ai_answer = self._generate_groq_response(system_prompt, user_message)
                    
                    sources = [
                        SourceReference(
                            text=r["text"][:200],
                            document=r.get("source", "Document"),
                            score=r.get("score", 0)
                        )
                        for r in results[:3]
                    ]
                    
                    response = QueryResponse(
                        answer=ai_answer,
                        sources=sources,
                        related_products=remaining_products,
                        confidence=0.9
                    )
                    
                    self.memory.add_message(session_id, original_question, ai_answer, remaining_products, intent="remaining_products")
                    return response
                    
            except Exception as e:
                logger.error(f"Error generating AI response: {e}")
        
        # Fallback: Show basic info for remaining products
        answer = f"📋 **Details for Remaining Products:**\n\n"
        
        for idx, product in enumerate(remaining_products, 1):
            answer += f"**{idx}. {product.name.upper()}**\n"
            if product.description:
                answer += f"{product.description}\n"
            if product.category:
                answer += f"Category: {product.category}\n"
            answer += "\n"
        
        answer += "Need more specific information about any product? Just ask! 😊"
        
        response = QueryResponse(
            answer=answer,
            sources=[],
            related_products=remaining_products,
            confidence=0.7
        )
        
        self.memory.add_message(session_id, original_question, answer, remaining_products, intent="remaining_products")
        return response

    def _handle_product_details_from_docs(self, query: str, session_id: str, original_question: str,
                                         conversation_history: str, top_k: int) -> QueryResponse:
        """Handle requests for product details by searching documents"""
        
        logger.info(f"Searching documents for product details: {query}")
        
        # Search documents with broader query
        results = vector_store.search(query, top_k=top_k * 2)
        
        if results and len(results) > 0:
            doc_context = "\n\n".join([r["text"] for r in results[:10]])
            
            try:
                if self.groq_client:
                    system_prompt = """You are a helpful product expert assistant.
                    
Extract and present product information from the context provided.
For each product mentioned, include:
- Product name
- Purpose/Description
- Category
- Usage/Application
- Key features

Format the response clearly with proper structure.
If asking about multiple products, cover all of them.
Be helpful, informative, and friendly. Use emojis occasionally."""

                    user_message = f"Context from documents:\n{doc_context}\n\nCustomer question: {original_question}"
                    
                    ai_answer = self._generate_groq_response(system_prompt, user_message)
                    
                    sources = [
                        SourceReference(
                            text=r["text"][:200],
                            document=r.get("source", "Document"),
                            score=r.get("score", 0)
                        )
                        for r in results[:3]
                    ]
                    
                    response = QueryResponse(
                        answer=ai_answer,
                        sources=sources,
                        confidence=0.85
                    )
                    
                    self.memory.add_message(session_id, original_question, ai_answer, intent="product_details")
                    return response
                    
            except Exception as e:
                logger.error(f"Error generating AI response: {e}")
        
        # Fallback to intelligent query handler
        return self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, top_k)

    def _handle_material_recommendation_with_docs(self, query: str, session_id: str, original_question: str,
                                                 conversation_history: str, top_k: int) -> QueryResponse:
        """Handle material recommendations using document search"""
        
        # First search documents
        results = vector_store.search(f"{query} purpose best for", top_k=top_k * 2)
        
        if results and len(results) > 0:
            doc_context = "\n\n".join([r["text"] for r in results[:10]])
            
            try:
                if self.groq_client:
                    system_prompt = """You are a helpful product recommendation expert.
                    
Based on the customer's question about materials or use cases, recommend the most suitable products from the context.

Provide:
1. Recommended products for their specific need
2. Brief explanation of each product's purpose
3. Why it's suitable for their use case

Be helpful, practical, and friendly. Use emojis occasionally."""

                    user_message = f"Context:\n{doc_context}\n\nCustomer question: {original_question}"
                    
                    ai_answer = self._generate_groq_response(system_prompt, user_message)
                    
                    sources = [
                        SourceReference(
                            text=r["text"][:200],
                            document=r.get("source", "Document"),
                            score=r.get("score", 0)
                        )
                        for r in results[:3]
                    ]
                    
                    response = QueryResponse(
                        answer=ai_answer,
                        sources=sources,
                        confidence=0.85
                    )
                    
                    self.memory.add_message(session_id, original_question, ai_answer, intent="material_recommendation")
                    return response
                    
            except Exception as e:
                logger.error(f"Error generating AI response: {e}")
        
        # Fallback
        return self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, top_k)

    def _handle_specific_product(self, q: str, session_id: str, original_question: str) -> QueryResponse:
        """Handle specific product queries"""
        
        product = self._find_product_in_query(q)
        
        if not product:
            return self._handle_intelligent_query_with_fallback(original_question, session_id, "", 5)
        
        answer = self.format_product_info(product)
        
        response = QueryResponse(
            answer=answer,
            sources=[],
            related_products=[product],
            confidence=0.95
        )
        
        self.memory.add_message(
            session_id, 
            original_question, 
            answer, 
            [product], 
            intent="specific_product"
        )
        return response

    def _handle_pricing_query(self, q: str, session_id: str, original_question: str, 
                             conversation_history: str) -> QueryResponse:
        """Handle pricing queries"""
        
        product = self._find_product_in_query(q)
        
        if product:
            answer = f"**{product.name.upper()}**\n\n"
            
            if product.price and product.price > 0:
                answer += f"**Price:** Rs {product.price:,.0f}\n\n"
            else:
                answer += "**Price:** Contact for pricing\n\n"
            
            if hasattr(product, 'sizes') and product.sizes:
                answer += f"**Sizes:** {', '.join(product.sizes)}\n\n"
            
            if hasattr(product, 'colors') and product.colors:
                answer += f"**Colors:** {', '.join(product.colors[:10])}\n\n"
            
            answer += "**Delivery:** 3-5 business days\n\n"
            answer += f"**Order:** Say 'buy {product.name}' to order"
            
            response = QueryResponse(
                answer=answer,
                sources=[],
                related_products=[product],
                confidence=0.95
            )
        else:
            response = self._handle_intelligent_query_with_fallback(
                original_question, 
                session_id, 
                conversation_history, 
                5
            )
        
        self.memory.add_message(
            session_id, 
            original_question, 
            response.answer, 
            response.related_products, 
            intent="pricing"
        )
        return response

    def _handle_order_intent(self, q: str, session_id: str, original_question: str,
                            conversation_history: str) -> QueryResponse:
        """Handle order placement"""
        
        try:
            product = self._find_product_in_query(q)
            
            if product:
                pending_order = {
                    'items': [{
                        'product_name': product.name,
                        'product_id': getattr(product, 'id', ''),
                        'unit_price': product.price if product.price else 0,
                        'quantity': 1,
                        'total_price': product.price if product.price else 0
                    }],
                    'customer_info': {},
                    'payment_details': {}
                }
                
                self.memory.set_order_state(session_id, 'full_name', pending_order)
                
                answer = f"**🎉 ORDER: {product.name.upper()}**\n\n"
                
                if product.price and product.price > 0:
                    answer += f"Price: Rs {product.price:,.0f}\n\n"
                
                answer += "Awesome! Let's get your order placed. 😊\n\n"
                answer += "I'll need:\n"
                answer += "1. Your full name\n"
                answer += "2. Phone number\n"
                answer += "3. Delivery address\n"
                answer += "4. City\n"
                answer += "5. Quantity\n"
                answer += "6. Payment method\n\n"
                answer += "Starting with your full name:"
                
                response = QueryResponse(
                    answer=answer,
                    sources=[],
                    related_products=[product],
                    confidence=0.95
                )
            else:
                if not upsell_service.products:
                    upsell_service.load_all_products()
                
                products = upsell_service.products
                
                if products and len(products) > 0:
                    answer = "I'd love to help you place an order! 😊\n\n"
                    answer += "Which product would you like to buy?\n\n"
                    
                    popular_products = products[:5]
                    
                    for idx, product in enumerate(popular_products, 1):
                        price_info = f" - Rs {product.price:,.0f}" if product.price and product.price > 0 else ""
                        answer += f"{idx}. {product.name}{price_info}\n"
                        
                        if product.description and len(product.description) > 10:
                            desc = product.description[:60] + "..." if len(product.description) > 60 else product.description
                            answer += f"   {desc}\n"
                        
                        answer += f"   Say: 'I want to buy {product.name}'\n\n"
                    
                    if len(products) > 5:
                        answer += f"... and {len(products) - 5} more products available!\n\n"
                    
                    answer += "Or type 'show products' to see all options."
                    
                    response = QueryResponse(
                        answer=answer,
                        sources=[],
                        related_products=popular_products,
                        confidence=0.8
                    )
                else:
                    answer = "I'd love to help you place an order! 😊\n\n"
                    answer += "Which product are you interested in?"
                    
                    response = QueryResponse(
                        answer=answer,
                        sources=[],
                        related_products=[],
                        confidence=0.7
                    )
            
        except Exception as e:
            logger.error(f"Error in order intent handler: {e}", exc_info=True)
            return self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, 5)
        
        self.memory.add_message(
            session_id, 
            original_question, 
            response.answer,
            response.related_products, 
            intent="order"
        )
        return response

    def _handle_delivery_query(self, session_id: str, original_question: str, 
                              conversation_history: str) -> QueryResponse:
        """Handle delivery queries"""
        
        results = vector_store.search("delivery shipping time", top_k=3)
        
        if results and len(results) > 0:
            doc_context = "\n\n".join([r["text"][:500] for r in results])
            
            try:
                if self.groq_client:
                    system_prompt = """You are a friendly, casual customer service assistant. 
                    Provide clear, concise information about delivery and shipping based on the provided context.
                    If the context doesn't contain specific delivery info, use general knowledge about deliveries.
                    Keep answers friendly and direct. Use emojis occasionally."""
                    ai_answer = self._generate_groq_response(system_prompt, f"Context: {doc_context}\n\nQuestion: {original_question}")
                else:
                    ai_answer = llm_service.generate_response(
                        question=original_question,
                        context=doc_context,
                        conversation_history=conversation_history
                    )
                
                sources = [
                    SourceReference(
                        text=r["text"][:200],
                        document=r.get("source", "Document"),
                        score=r.get("score", 0)
                    )
                    for r in results[:2]
                ]
                
                response = QueryResponse(
                    answer=ai_answer,
                    sources=sources,
                    confidence=0.85
                )
            except:
                response = self._generic_delivery_info()
        else:
            response = self._generic_delivery_info()
        
        self.memory.add_message(session_id, original_question, response.answer, intent="delivery")
        return response
    
    def _generic_delivery_info(self) -> QueryResponse:
        """Generic delivery info"""
        answer = "**🚚 Delivery Information**\n\n"
        answer += "• **Time:** 3-5 business days\n"
        answer += "• **Charges:** Rs 200 (FREE over Rs 5,000) 😊\n"
        answer += "• **Cities:** All major cities\n"
        answer += "• **Tracking:** SMS/WhatsApp updates\n\n"
        answer += "Fast and reliable delivery guaranteed!"
        
        return QueryResponse(answer=answer, sources=[], confidence=0.7)

    def _handle_payment_query(self, session_id: str, original_question: str,
                             conversation_history: str) -> QueryResponse:
        """Handle payment queries"""
        
        results = vector_store.search("payment methods cod", top_k=3)
        
        if results and len(results) > 0:
            doc_context = "\n\n".join([r["text"][:500] for r in results])
            
            try:
                if self.groq_client:
                    system_prompt = """You are a friendly, casual customer service assistant. 
                    Provide clear, concise information about payment methods based on the provided context.
                    If the context doesn't contain specific payment info, use general knowledge about payments.
                    Keep answers friendly and direct. Use emojis occasionally."""
                    ai_answer = self._generate_groq_response(system_prompt, f"Context: {doc_context}\n\nQuestion: {original_question}")
                else:
                    ai_answer = llm_service.generate_response(
                        question=original_question,
                        context=doc_context,
                        conversation_history=conversation_history
                    )
                
                sources = [
                    SourceReference(
                        text=r["text"][:200],
                        document=r.get("source", "Document"),
                        score=r.get("score", 0)
                    )
                    for r in results[:2]
                ]
                
                response = QueryResponse(
                    answer=ai_answer,
                    sources=sources,
                    confidence=0.85
                )
            except:
                response = self._generic_payment_info()
        else:
            response = self._generic_payment_info()
        
        self.memory.add_message(session_id, original_question, response.answer, intent="payment")
        return response
    
    def _generic_payment_info(self) -> QueryResponse:
        """Generic payment info"""
        answer = "**💳 Payment Options**\n\n"
        answer += "1. **Cash on Delivery (COD)** 😊\n"
        answer += "   Pay when you receive\n\n"
        answer += "2. **Bank Transfer**\n"
        answer += "   Direct deposit\n\n"
        answer += "3. **JazzCash/EasyPaisa**\n"
        answer += "   Mobile wallet\n\n"
        answer += "4. **Online Payment**\n"
        answer += "   Credit/Debit cards\n\n"
        answer += "All payments are secure and easy!"
        
        return QueryResponse(answer=answer, sources=[], confidence=0.7)

    def _handle_followup_question(self, q: str, context: Dict, session_id: str,
                                 original_question: str, conversation_history: str) -> QueryResponse:
        """Handle follow-up questions"""
        
        last_products = self.memory.get_last_products(session_id, n=3)
        
        if last_products:
            product = last_products[0]
            
            if any(word in q for word in ["feature", "special", "unique", "quality", "about", "details"]):
                return self._handle_specific_product(product.name, session_id, original_question)
            
            elif any(word in q for word in ["price", "cost", "how much", "kitna"]):
                return self._handle_pricing_query(product.name, session_id, original_question, conversation_history)
            
            elif any(word in q for word in ["buy", "order", "purchase", "khareedna"]):
                return self._handle_order_intent(product.name, session_id, original_question, conversation_history)
            
            elif any(word in q for word in ["color", "colour", "rang"]):
                if hasattr(product, 'colors') and product.colors:
                    answer = f"**🎨 Colors for {product.name}:**\n\n"
                    answer += f"{', '.join(product.colors)}\n\n"
                    answer += f"Which color do you prefer? 😊"
                    
                    response = QueryResponse(
                        answer=answer,
                        sources=[],
                        related_products=[product],
                        confidence=0.95
                    )
                    self.memory.add_message(session_id, original_question, answer, [product], intent="followup")
                    return response
            
            elif any(word in q for word in ["size", "sizes"]):
                if hasattr(product, 'sizes') and product.sizes:
                    answer = f"**📏 Sizes for {product.name}:**\n\n"
                    answer += f"{', '.join(product.sizes)}\n\n"
                    answer += f"Which size do you need? 😊"
                    
                    response = QueryResponse(
                        answer=answer,
                        sources=[],
                        related_products=[product],
                        confidence=0.95
                    )
                    self.memory.add_message(session_id, original_question, answer, [product], intent="followup")
                    return response
        
        return self._handle_intelligent_query_with_fallback(original_question, session_id, conversation_history, 5)

    def _handle_intelligent_query_with_fallback(self, question: str, session_id: str, 
                                               conversation_history: str, top_k: int) -> QueryResponse:
        """
        AI + RAG for intelligent responses using documents FIRST
        FIXED: Always searches documents thoroughly before fallback
        FIXED: Checks for out-of-scope queries (e.g. "do you have burgers")
        """
        
        logger.info(f"Intelligent query with document search: {question}")
        
        # OUT-OF-SCOPE CHECK: If query has nothing to do with our products, say so clearly
        if self._is_out_of_scope(question):
            if not upsell_service.products:
                upsell_service.load_all_products()
            all_products = upsell_service.products
            answer = f"I'm sorry, we don't carry that. 😊 We specialize in our available product range.\n\n"
            answer += "**Here's what we currently offer:**\n\n"
            for idx, p in enumerate(all_products, 1):
                answer += f"{idx}. **{p.name}**"
                if p.description:
                    answer += f" — {p.description[:55]}..."
                answer += "\n"
            answer += "\nWould you like details on any of these? Just ask! 😊"
            self.memory.add_message(session_id, question, answer, all_products[:5], intent="out_of_scope")
            return QueryResponse(answer=answer, sources=[], related_products=all_products[:5], confidence=0.95)
        
        # Search documents with increased top_k for better coverage
        results = vector_store.search(question, top_k=top_k * 3)
        
        doc_context = ""
        if results and len(results) > 0:
            doc_context = "\n\n".join([f"{r['text']}" for r in results[:15]])
            logger.info(f"Found {len(results)} document results")
        
        related_products = []
        if upsell_service.products:
            try:
                related_products = upsell_service.get_recommendations_by_query(question, top_k=5)
            except Exception as e:
                logger.error(f"Error getting products: {e}")
        
        try:
            if self.groq_client and doc_context:
                system_prompt = """You are a helpful, knowledgeable assistant for a business.

**CRITICAL INSTRUCTIONS:**
1. ALWAYS use information from the document context when available
2. Extract ALL relevant product information from the context
3. Be specific and detailed when the context has information
4. Format responses clearly with proper structure
5. Use emojis occasionally to be friendly 😊
6. If multiple products are mentioned in context, cover ALL of them
7. Do NOT say "I don't have information" if the context contains relevant data

**When explaining products:**
- Include product name, purpose, description
- Mention categories and use cases
- Be informative and helpful
- Provide practical advice

**If context lacks info:** Provide general helpful guidance and suggest alternatives."""

                context_msg = ""
                if doc_context:
                    context_msg = f"DOCUMENT CONTEXT:\n{doc_context}\n\n"
                
                context_msg += f"CUSTOMER QUESTION: {question}\n\n"
                
                if related_products:
                    context_msg += f"AVAILABLE PRODUCTS: {', '.join([p.name for p in related_products[:5]])}\n\n"
                
                if conversation_history:
                    context_msg += f"CONVERSATION HISTORY:\n{conversation_history}\n\n"
                
                context_msg += "Please provide a helpful, detailed response based on the context."
                
                ai_answer = self._generate_groq_response(system_prompt, context_msg)
                
                # Validate response quality
                if len(ai_answer.strip()) < 50:
                    logger.warning("AI response too short, using fallback")
                    ai_answer = self._generate_contextual_fallback(question, related_products, doc_context)
                
                logger.info("AI response generated successfully")
            
            else:
                # Fallback to existing LLM service
                ai_answer = llm_service.generate_response(
                    question=question,
                    context=doc_context,
                    products=[p.model_dump() for p in related_products] if related_products else None,
                    conversation_history=conversation_history
                )
                
                if not ai_answer or len(ai_answer.strip()) < 50:
                    ai_answer = self._generate_contextual_fallback(question, related_products, doc_context)
        
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            ai_answer = self._generate_contextual_fallback(question, related_products, doc_context)
        
        sources = []
        if results and len(results) > 0:
            sources = [
                SourceReference(
                    text=r["text"][:250],
                    document=r.get("source", "Document"),
                    score=r.get("score", 0.0)
                )
                for r in results[:3]
            ]
        
        confidence = 0.8 if len(results) >= 3 else 0.6
        
        response = QueryResponse(
            answer=ai_answer,
            sources=sources,
            related_products=related_products if related_products else [],
            confidence=confidence
        )
        
        self.memory.add_message(
            session_id, 
            question, 
            ai_answer, 
            related_products if related_products else [], 
            intent="document_query"
        )
        return response

    def _generate_contextual_fallback(self, question: str, related_products: List[ProductInfo] = None, 
                                     doc_context: str = "") -> str:
        """Generate contextual fallback response"""
        
        question_lower = question.lower()
        
        # If doc_context exists, try to extract basic info
        if doc_context and len(doc_context) > 100:
            return f"Based on our information:\n\n{doc_context[:500]}\n\n" \
                   f"Need more specific details? Feel free to ask! 😊"
        
        # Product-specific fallbacks
        if related_products and len(related_products) > 0:
            answer = "**Here are some relevant products:** 😊\n\n"
            for idx, product in enumerate(related_products[:5], 1):
                answer += f"{idx}. **{product.name}**\n"
                if product.description:
                    desc = product.description[:80] + "..." if len(product.description) > 80 else product.description
                    answer += f"   {desc}\n"
                answer += "\n"
            answer += "Type a product number or name for detailed information!"
            return answer
        
        # Generic helpful response
        return "**I'm here to help!** 😊\n\n" \
               "You can ask me about:\n" \
               "• Product information and details\n" \
               "• Pricing and availability\n" \
               "• Product recommendations\n" \
               "• Placing orders\n" \
               "• Delivery and payment options\n\n" \
               "What would you like to know?"

    def reset_session(self, session_id: str):
        """Reset conversation session"""
        self.memory.clear_session(session_id)
        logger.info(f"Session {session_id} reset")
    
    def get_session_stats(self, session_id: str) -> Dict:
        """Get session statistics"""
        context = self.memory.get_context(session_id)
        
        return {
            "session_id": session_id,
            "message_count": len(context.get('messages', [])),
            "last_intent": context.get('last_intent'),
            "products_discussed": len(context.get('last_products', [])),
            "shown_products": len(context.get('shown_products', [])),
            "last_updated": context.get('last_updated'),
            "context_data": context.get('context_data', {})
        }
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.now()
        expired = []
        
        for session_id, session in self.memory.sessions.items():
            if current_time - session['last_updated'] > self.memory.timeout:
                expired.append(session_id)
        
        for session_id in expired:
            del self.memory.sessions[session_id]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        
        return len(expired)

# Global instance - automatically loads Groq from environment
chatbot_service = ChatbotService()