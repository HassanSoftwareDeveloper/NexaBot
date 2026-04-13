#chatbot_service.py

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
from groq import Groq

logger = logging.getLogger(__name__)


def _clean(text: str) -> str:
    if not text:
        return ""
    return text.strip().lower()


class ConversationMemory:
    def __init__(self, max_history: int = 15, timeout_minutes: int = 30):
        self.sessions = {}
        self.max_history = max_history
        self.timeout = timedelta(minutes=timeout_minutes)

    def _init_session(self, session_id: str):
        self.sessions[session_id] = {
            'messages': [], 'last_products': [], 'last_intent': None,
            'last_updated': datetime.now(), 'context_data': {},
            'order_state': None, 'pending_order': {}, 'shown_products': []
        }

    def add_message(self, session_id: str, user_query: str, bot_response: str,
                    mentioned_products: List[ProductInfo] = None, intent: str = None,
                    metadata: Dict = None):
        if session_id not in self.sessions:
            self._init_session(session_id)
        session = self.sessions[session_id]
        session['messages'].append({
            'user': user_query, 'bot': bot_response,
            'intent': intent, 'timestamp': datetime.now(), 'metadata': metadata or {}
        })
        if len(session['messages']) > self.max_history:
            session['messages'] = session['messages'][-self.max_history:]
        if mentioned_products:
            session['last_products'] = mentioned_products
            for p in mentioned_products:
                if hasattr(p, 'name') and p.name not in session['shown_products']:
                    session['shown_products'].append(p.name)
        if intent:
            session['last_intent'] = intent
        if metadata:
            session['context_data'].update(metadata)
        session['last_updated'] = datetime.now()

    def get_context(self, session_id: str) -> Dict:
        if session_id not in self.sessions:
            return {'messages': [], 'last_products': [], 'last_intent': None,
                    'context_data': {}, 'order_state': None, 'pending_order': {}, 'shown_products': []}
        session = self.sessions[session_id]
        if datetime.now() - session['last_updated'] > self.timeout:
            del self.sessions[session_id]
            return {'messages': [], 'last_products': [], 'last_intent': None,
                    'context_data': {}, 'order_state': None, 'pending_order': {}, 'shown_products': []}
        return session

    def get_conversation_history(self, session_id: str, last_n: int = 6) -> str:
        context = self.get_context(session_id)
        messages = context.get('messages', [])[-last_n:]
        if not messages:
            return ""
        return "\n".join([f"Customer: {m['user']}\nAssistant: {m['bot']}" for m in messages])

    def set_order_state(self, session_id: str, state: str, order_data: Dict = None):
        if session_id not in self.sessions:
            self._init_session(session_id)
        self.sessions[session_id]['order_state'] = state
        if order_data:
            self.sessions[session_id]['pending_order'].update(order_data)

    def get_order_state(self, session_id: str) -> Tuple[Optional[str], Dict]:
        context = self.get_context(session_id)
        return context.get('order_state'), context.get('pending_order', {})

    def clear_order_state(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]['order_state'] = None
            self.sessions[session_id]['pending_order'] = {}

    def get_last_products(self, session_id: str, n: int = 100) -> List[ProductInfo]:
        return self.get_context(session_id).get('last_products', [])[:n]

    def get_shown_products(self, session_id: str) -> List[str]:
        return self.sessions.get(session_id, {}).get('shown_products', [])

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]


class ChatbotService:
    def __init__(self):
        self.memory = ConversationMemory()
        self.groq_client, self.groq_model = self._initialize_groq_client()
        logger.info("ChatbotService initialized")

    def _initialize_groq_client(self):
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            return None, None
        try:
            client = Groq(api_key=api_key)
            for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]:
                try:
                    client.chat.completions.create(
                        model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=5
                    )
                    logger.info(f"Groq ready: {model}")
                    return client, model
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Groq init failed: {e}")
        return None, None

    def _groq(self, system: str, user: str, temperature: float = 0.4) -> str:
        if not self.groq_client:
            raise Exception("Groq not available")
        resp = self.groq_client.chat.completions.create(
            model=self.groq_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature, max_tokens=1024
        )
        return resp.choices[0].message.content.strip()

    # ── MAIN ENTRY POINT ──────────────────────────────────────────────────────

    def answer_query(self, question: str, top_k: int = 10,
                     shop_filter: str = None, session_id: str = "default") -> QueryResponse:
        if not question or len(question.strip()) < 2:
            return QueryResponse(answer="Go ahead, ask me anything! 😊", sources=[], confidence=0.0)

        original = question.strip()
        q = _clean(original)
        logger.info(f"[{session_id}] Query: {original}")

        try:
            # ORDER FLOW — highest priority
            order_state, pending_order = self.memory.get_order_state(session_id)
            if order_state:
                return self._handle_order_collection(original, session_id, order_state, pending_order)

            # NUMBER SELECTION
            num = self._extract_number(original)
            if num is not None and self.memory.get_last_products(session_id):
                return self._handle_number_selection(num, session_id, original)

            # SMART AI RESPONSE
            return self._smart_response(original, q, session_id, top_k)

        except Exception as e:
            logger.error(f"answer_query error: {e}", exc_info=True)
            return QueryResponse(answer="Something went wrong. Could you try again? 😊", sources=[], confidence=0.0)

    # ── SMART AI RESPONSE ─────────────────────────────────────────────────────

    def _smart_response(self, original: str, q: str, session_id: str, top_k: int) -> QueryResponse:
        if not upsell_service.products:
            upsell_service.load_all_products()
        all_products = upsell_service.products or []

        doc_results = vector_store.search(original, top_k=top_k * 2)
        doc_context = "\n\n".join([r["text"] for r in doc_results[:12]]) if doc_results else ""

        relevant_products = []
        try:
            relevant_products = upsell_service.get_recommendations_by_query(original, top_k=6)
        except Exception:
            pass

        history = self.memory.get_conversation_history(session_id, last_n=6)
        catalog_text = self._build_catalog_text(all_products)
        system_prompt = self._build_system_prompt(catalog_text)
        user_msg = self._build_user_message(original, doc_context, relevant_products, history)

        try:
            if self.groq_client:
                answer = self._groq(system_prompt, user_msg, temperature=0.5)
            else:
                answer = llm_service.generate_response(
                    question=original, context=doc_context,
                    products=[p.model_dump() for p in relevant_products] if relevant_products else None,
                    conversation_history=history
                )
        except Exception as e:
            logger.error(f"LLM error: {e}")
            answer = self._fallback_response(original, relevant_products, doc_context)

        # Detect order intent and start flow
        if self._is_order_intent(q):
            product = self._find_product_in_query(q) or (relevant_products[0] if relevant_products else None)
            if product:
                return self._start_order_flow(product, session_id, original)

        sources = [
            SourceReference(text=r["text"][:200], document=r.get("source", "Document"), score=r.get("score", 0))
            for r in doc_results[:3]
        ] if doc_results else []

        response = QueryResponse(
            answer=answer, sources=sources,
            related_products=relevant_products[:5],
            confidence=0.9 if doc_results else 0.7
        )
        self.memory.add_message(session_id, original, answer, relevant_products, intent="smart_response")
        return response

    def _build_system_prompt(self, catalog_text: str) -> str:
        return f"""You are a smart, friendly shopping assistant. Help customers find products, answer questions, and guide purchases — like a knowledgeable salesperson.

PERSONALITY: Warm, natural, conversational. Understand what the customer needs. Only show relevant products. Use simple language and occasional emojis.

PRODUCT CATALOG:
{catalog_text}

RULES:
1. Only recommend products relevant to the question — don't list everything
2. Answer greetings/delivery/payment naturally without pushing products
3. For specific product questions, give full details from documents
4. If customer wants to buy, say "Great! To order, just say 'buy [product name]'"
5. Prices in Pakistani Rupees (Rs)
6. Keep responses under 300 words
7. Never say "based on the context provided" — just answer naturally"""

    def _build_user_message(self, question: str, doc_context: str,
                             relevant_products: List[ProductInfo], history: str) -> str:
        msg = ""
        if history:
            msg += f"CONVERSATION SO FAR:\n{history}\n\n"
        if doc_context:
            msg += f"RELEVANT DOCUMENT INFO:\n{doc_context[:4000]}\n\n"
        if relevant_products:
            msg += "POSSIBLY RELEVANT PRODUCTS:\n"
            for p in relevant_products[:5]:
                msg += f"- {p.name}"
                if p.price:
                    msg += f" (Rs {p.price:,.0f})"
                if p.description:
                    msg += f": {p.description[:100]}"
                msg += "\n"
            msg += "\n"
        msg += f"CUSTOMER: {question}"
        return msg

    def _build_catalog_text(self, products: List[ProductInfo]) -> str:
        if not products:
            return "No products loaded yet."
        lines = []
        for p in products:
            line = f"• {p.name}"
            if p.category:
                line += f" [{p.category}]"
            if p.price:
                line += f" — Rs {p.price:,.0f}"
            if p.description:
                line += f": {p.description[:80]}"
            lines.append(line)
        return "\n".join(lines)

    # ── ORDER FLOW ────────────────────────────────────────────────────────────

    def _is_order_intent(self, q: str) -> bool:
        order_words = ["buy", "order", "purchase", "want to buy", "place order", "khareedna", "lena hai"]
        return any(w in q for w in order_words)

    def _start_order_flow(self, product: ProductInfo, session_id: str, original: str) -> QueryResponse:
        pending_order = {
            'items': [{'product_name': product.name, 'unit_price': product.price or 0,
                       'quantity': 1, 'total_price': product.price or 0}],
            'customer_info': {}, 'payment_details': {}
        }
        self.memory.set_order_state(session_id, 'full_name', pending_order)

        answer = f"Great choice! 🎉 Let's get **{product.name}** ordered.\n\n"
        if product.price:
            answer += f"Price: Rs {product.price:,.0f}\n\n"
        answer += "You can type everything at once:\n"
        answer += "`Name, Phone, Address, City, Quantity, Payment`\n\n"
        answer += "Example: `Hassan, 0312345678, Street 5 Gulberg, Lahore, 2, JazzCash`\n\n"
        answer += "Or just type your **full name** and I'll ask the rest:"

        self.memory.add_message(session_id, original, answer, [product], intent="order_start")
        return QueryResponse(answer=answer, sources=[], related_products=[product], confidence=1.0)

    def _parse_all_in_one(self, query: str, pending_order: Dict) -> Optional[Dict]:
        """Parse comma-separated input: Name, Phone, Address, City, Qty, Payment"""
        parts = [p.strip() for p in re.split(r'[,|]', query) if p.strip()]
        if len(parts) < 4:
            return None

        # Part 1 must look like a name (letters/spaces, no digits)
        if re.search(r'\d{5,}', parts[0]):
            return None  # looks like a phone number, not a name

        # Part 2 must look like a phone number
        phone = re.sub(r'[^\d+]', '', parts[1])
        if len(phone) < 9:
            return None

        if 'customer_info' not in pending_order:
            pending_order['customer_info'] = {}
        if 'payment_details' not in pending_order:
            pending_order['payment_details'] = {}

        pending_order['customer_info']['full_name'] = parts[0]
        pending_order['customer_info']['phone'] = phone
        pending_order['customer_info']['address'] = parts[2]
        pending_order['customer_info']['city'] = parts[3] if len(parts) > 3 else ''

        qty = 1
        if len(parts) > 4:
            m = re.search(r'\d+', parts[4])
            if m:
                qty = max(1, int(m.group()))

        if pending_order.get('items'):
            pending_order['items'][0]['quantity'] = qty
            pending_order['items'][0]['total_price'] = pending_order['items'][0].get('unit_price', 0) * qty

        if len(parts) > 5:
            pending_order['payment_details']['method'] = parts[5]
        else:
            pending_order['payment_details']['method'] = 'COD'

        return pending_order

    def _handle_order_collection(self, query: str, session_id: str,
                                  order_state: str, pending_order: Dict) -> QueryResponse:
        if 'customer_info' not in pending_order:
            pending_order['customer_info'] = {}
        if 'payment_details' not in pending_order:
            pending_order['payment_details'] = {}

        # Try all-in-one parse when waiting for name
        if order_state == 'full_name':
            parsed = self._parse_all_in_one(query, pending_order)
            if parsed:
                return self._finalize_order(parsed, session_id)

        flow = ['full_name', 'phone', 'address', 'city', 'quantity', 'payment_method']
        current_index = flow.index(order_state) if order_state in flow else 0

        if order_state == 'full_name':
            pending_order['customer_info']['full_name'] = query.strip()
        elif order_state == 'phone':
            phone = re.sub(r'[^\d+]', '', query)
            if len(phone) < 9:
                return QueryResponse(answer="Please provide a valid phone number (at least 10 digits).", sources=[], confidence=0.9)
            pending_order['customer_info']['phone'] = phone
        elif order_state == 'address':
            pending_order['customer_info']['address'] = query.strip()
        elif order_state == 'city':
            pending_order['customer_info']['city'] = query.strip()
        elif order_state == 'quantity':
            m = re.search(r'\d+', query)
            qty = max(1, int(m.group())) if m else 1
            if pending_order.get('items'):
                pending_order['items'][0]['quantity'] = qty
                pending_order['items'][0]['total_price'] = pending_order['items'][0].get('unit_price', 0) * qty
        elif order_state == 'payment_method':
            pending_order['payment_details']['method'] = query.strip()

        current_index += 1
        if current_index >= len(flow):
            return self._finalize_order(pending_order, session_id)

        next_field = flow[current_index]
        self.memory.set_order_state(session_id, next_field, pending_order)

        prompts = {
            'full_name': "What's your full name?",
            'phone': "Your phone number?",
            'address': "Your delivery address?",
            'city': "Which city?",
            'quantity': "How many units would you like?",
            'payment_method': "Payment method? (COD / JazzCash / EasyPaisa / Bank Transfer)"
        }
        return QueryResponse(answer=prompts.get(next_field, "Please continue."), sources=[], confidence=1.0)

    def _finalize_order(self, pending_order: Dict, session_id: str) -> QueryResponse:
        try:
            result = order_service.place_order(pending_order)
            self.memory.clear_order_state(session_id)
            if result['success']:
                c = pending_order.get('customer_info', {})
                items = pending_order.get('items', [])
                product_name = items[0]['product_name'] if items else 'your product'
                qty = items[0].get('quantity', 1) if items else 1
                payment = pending_order.get('payment_details', {}).get('method', 'COD')
                answer = (
                    f"✅ **Order Confirmed!**\n\n"
                    f"**Order ID:** `{result['order_id']}`\n"
                    f"**Product:** {product_name} × {qty}\n"
                    f"**Name:** {c.get('full_name', '')}\n"
                    f"**Phone:** {c.get('phone', '')}\n"
                    f"**Address:** {c.get('address', '')}, {c.get('city', '')}\n"
                    f"**Payment:** {payment}\n"
                    f"**Delivery:** {result['estimated_delivery']}\n\n"
                    f"Thank you! We'll contact you soon to confirm. 😊"
                )
            else:
                answer = f"Sorry, order failed: {result.get('message', 'Unknown error')}. Please try again."
            return QueryResponse(answer=answer, sources=[], confidence=1.0)
        except Exception as e:
            logger.error(f"Order finalize error: {e}")
            self.memory.clear_order_state(session_id)
            return QueryResponse(answer="Order placement failed. Please try again. 😊", sources=[], confidence=0.5)

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _extract_number(self, query: str) -> Optional[int]:
        q = query.strip()
        if q.isdigit():
            n = int(q)
            if 1 <= n <= 100:
                return n
        for pattern in [r'product\s*#?(\d+)', r'number\s*(\d+)', r'item\s*(\d+)', r'^(\d+)\b']:
            m = re.search(pattern, q.lower())
            if m:
                n = int(m.group(1))
                if 1 <= n <= 100:
                    return n
        return None

    def _handle_number_selection(self, number: int, session_id: str, original: str) -> QueryResponse:
        products = self.memory.get_last_products(session_id)
        if not products:
            return QueryResponse(answer="No products to select from. Try 'show products' first.", sources=[], confidence=0.5)
        if number > len(products):
            return QueryResponse(answer=f"I only have {len(products)} products listed. Which one did you mean?", sources=[], confidence=0.5)
        product = products[number - 1]
        answer = self._format_product_detail(product)
        self.memory.add_message(session_id, original, answer, [product], intent="number_selection")
        return QueryResponse(answer=answer, sources=[], related_products=[product], confidence=0.95)

    def _find_product_in_query(self, q: str) -> Optional[ProductInfo]:
        if not upsell_service.products:
            upsell_service.load_all_products()
        if not upsell_service.products:
            return None
        best, best_score = None, 0
        for product in upsell_service.products:
            if not product or not hasattr(product, 'name'):
                continue
            score = max(
                fuzz.partial_ratio(q, product.name.lower()),
                fuzz.token_sort_ratio(q, product.name.lower())
            )
            if score > best_score:
                best_score = score
                best = product
        return best if best_score >= 60 else None

    def _format_product_detail(self, product: ProductInfo) -> str:
        lines = [f"**{product.name}**\n"]
        if product.description:
            lines.append(f"{product.description}\n")
        if product.category:
            lines.append(f"Category: {product.category}")
        if product.price and product.price > 0:
            lines.append(f"Price: Rs {product.price:,.0f}")
        else:
            lines.append("Price: Contact us for pricing")
        if product.colors:
            lines.append(f"Colors: {', '.join(product.colors[:8])}")
        lines.append(f"\nTo order: say **'buy {product.name}'** 😊")
        return "\n".join(lines)

    def _fallback_response(self, question: str, products: List[ProductInfo], doc_context: str) -> str:
        if doc_context:
            return f"Here's what I found:\n\n{doc_context[:400]}\n\nAnything else I can help with? 😊"
        if products:
            answer = "Here are some products that might help:\n\n"
            for i, p in enumerate(products[:4], 1):
                answer += f"{i}. **{p.name}**"
                if p.price:
                    answer += f" — Rs {p.price:,.0f}"
                answer += "\n"
            return answer
        return "I'm here to help! Ask me about our products, pricing, delivery, or anything else. 😊"

    def reset_session(self, session_id: str):
        self.memory.clear_session(session_id)

    def get_session_stats(self, session_id: str) -> Dict:
        context = self.memory.get_context(session_id)
        return {
            "session_id": session_id,
            "message_count": len(context.get('messages', [])),
            "last_intent": context.get('last_intent'),
            "products_discussed": len(context.get('last_products', [])),
        }

    def cleanup_expired_sessions(self):
        now = datetime.now()
        expired = [sid for sid, s in self.memory.sessions.items()
                   if now - s['last_updated'] > self.memory.timeout]
        for sid in expired:
            del self.memory.sessions[sid]
        return len(expired)


# Global instance
chatbot_service = ChatbotService()
