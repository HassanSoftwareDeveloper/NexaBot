#order_service.py

import os
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

ORDER_DIR = Path(os.getenv("ORDERS_DIR", "./data/orders"))
ORDER_DIR.mkdir(parents=True, exist_ok=True)


class OrderService:
    def __init__(self):
        self.orders_dir = ORDER_DIR
        self.json_file = self.orders_dir / "orders.json"
        if not self.json_file.exists():
            self.json_file.write_text("[]")

        # Try PostgreSQL — fall back silently if unavailable
        self.use_postgres = False
        self.pool = None
        self._try_init_postgres()

    # ── PostgreSQL (optional) ─────────────────────────────────────────────────

    def _try_init_postgres(self):
        try:
            from psycopg2 import pool
            cfg = {
                "host":     os.getenv("DB_HOST", "localhost"),
                "port":     os.getenv("DB_PORT", "5432"),
                "database": os.getenv("DB_NAME", "chatbot_orders"),
                "user":     os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", ""),
            }
            self.pool = pool.ThreadedConnectionPool(1, 10, **cfg)
            self._init_tables()
            self.use_postgres = True
            logger.info("PostgreSQL connected")
        except Exception as e:
            logger.warning(f"PostgreSQL unavailable, using JSON fallback: {e}")

    def _init_tables(self):
        sql = """
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR(50) UNIQUE NOT NULL,
            order_date DATE NOT NULL,
            customer_name VARCHAR(255),
            customer_phone VARCHAR(50),
            customer_email VARCHAR(255),
            delivery_address TEXT,
            city VARCHAR(100),
            order_total DECIMAL(10,2),
            payment_method VARCHAR(50),
            order_status VARCHAR(50) DEFAULT 'pending',
            order_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR(50) REFERENCES orders(order_id) ON DELETE CASCADE,
            product_name VARCHAR(255),
            quantity INTEGER,
            unit_price DECIMAL(10,2),
            total_price DECIMAL(10,2),
            color VARCHAR(50),
            size VARCHAR(50)
        );
        """
        conn = self.pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
            cur.close()
        finally:
            self.pool.putconn(conn)

    # ── Place Order ───────────────────────────────────────────────────────────

    def place_order(self, order_data: Dict) -> Dict:
        """Validate and save a new order. Returns result dict."""
        try:
            # Normalise incoming data (supports both chatbot flow and API)
            customer = order_data.get("customer_info", {})
            items    = order_data.get("items", [])
            payment  = order_data.get("payment_details", {"method": "COD"})

            # Basic validation
            if not customer.get("full_name") or not customer.get("phone"):
                return {"success": False, "message": "Customer name and phone are required", "order_id": None}

            if not items:
                return {"success": False, "message": "Order must contain at least one item", "order_id": None}

            # Ensure items have required fields
            clean_items = []
            for item in items:
                unit_price  = float(item.get("unit_price") or item.get("price") or 0)
                quantity    = int(item.get("quantity", 1))
                total_price = float(item.get("total_price") or unit_price * quantity)
                clean_items.append({
                    "product_name":     str(item.get("product_name", "Unknown")),
                    "product_category": item.get("product_category"),
                    "quantity":         quantity,
                    "unit_price":       unit_price,
                    "total_price":      total_price,
                    "color":            item.get("color"),
                    "size":             item.get("size"),
                    "specifications":   item.get("specifications"),
                })

            order_total = sum(i["total_price"] for i in clean_items)
            order_id    = f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            order_date  = datetime.now().date()
            estimated   = self._estimate_delivery(customer.get("city", ""))

            full_record = {
                "order_id":    order_id,
                "order_date":  str(order_date),
                "customer":    customer,
                "items":       clean_items,
                "payment":     payment,
                "order_total": order_total,
                "order_status": "pending",
                "estimated_delivery": estimated,
                "created_at":  datetime.now().isoformat(),
                "delivery_instructions": order_data.get("delivery_instructions"),
            }

            # Save
            if self.use_postgres:
                self._save_postgres(order_id, order_date, customer, clean_items, payment,
                                    order_total, full_record)
            self._save_json(full_record)
            self._save_backup(order_id, full_record)

            logger.info(f"Order {order_id} placed — total Rs {order_total:,.0f}")
            return {
                "success":            True,
                "order_id":           order_id,
                "total_amount":       order_total,
                "estimated_delivery": estimated,
                "message":            f"Order placed successfully! ID: {order_id}",
            }

        except Exception as e:
            logger.error(f"Order placement error: {e}", exc_info=True)
            return {"success": False, "message": str(e), "order_id": None}

    # ── Storage helpers ───────────────────────────────────────────────────────

    def _save_postgres(self, order_id, order_date, customer, items, payment,
                       order_total, full_record):
        conn = self.pool.getconn()
        try:
            from psycopg2.extras import Json
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders
                  (order_id, order_date, order_time, customer_name, customer_phone, customer_email,
                   delivery_address, city, postal_code, order_total, payment_method,
                   payment_details, order_status, delivery_instructions,
                   preferred_delivery_date, estimated_delivery_date, created_at)
                VALUES (%s,%s,NOW(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (order_id) DO NOTHING
            """, (
                order_id, order_date,
                customer.get("full_name"), customer.get("phone"), customer.get("email"),
                customer.get("address"), customer.get("city"), customer.get("postal_code"),
                order_total, payment.get("method", "COD"),
                Json(payment), "pending",
                full_record.get("delivery_instructions"),
                full_record.get("preferred_delivery_date"),
                full_record.get("estimated_delivery")
            ))
            for item in items:
                cur.execute("""
                    INSERT INTO order_items
                      (order_id, product_name, quantity, unit_price, total_price, color, size)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    order_id, item["product_name"], item["quantity"],
                    item["unit_price"], item["total_price"],
                    item.get("color"), item.get("size")
                ))
            conn.commit()
            cur.close()
            logger.info(f"Order {order_id} saved to PostgreSQL")
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL save failed: {e}")
        finally:
            self.pool.putconn(conn)

    def _save_json(self, record: Dict):
        try:
            orders = json.loads(self.json_file.read_text(encoding="utf-8"))
            orders.append(record)
            self.json_file.write_text(json.dumps(orders, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"JSON save error: {e}")

    def _save_backup(self, order_id: str, record: Dict):
        try:
            path = self.orders_dir / f"{order_id}.json"
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Backup save error: {e}")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _estimate_delivery(self, city: str) -> str:
        major = ["karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "multan"]
        days = 3 if any(c in city.lower() for c in major) else 5
        return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    # ── Read / Update ─────────────────────────────────────────────────────────

    def get_order_statistics(self) -> Dict:
        try:
            orders = json.loads(self.json_file.read_text(encoding="utf-8"))
            total_revenue = sum(o.get("order_total", 0) for o in orders)
            return {
                "total_orders":        len(orders),
                "total_revenue":       total_revenue,
                "average_order_value": total_revenue / len(orders) if orders else 0,
                "orders_by_status":    self._count_by_status(orders),
            }
        except Exception as e:
            logger.error(f"Statistics error: {e}")
            return {"total_orders": 0, "total_revenue": 0, "average_order_value": 0}

    def _count_by_status(self, orders: List[Dict]) -> Dict:
        counts: Dict = {}
        for o in orders:
            s = o.get("order_status", "pending")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def update_order_status(self, order_id: str, status: str) -> Dict:
        try:
            orders = json.loads(self.json_file.read_text(encoding="utf-8"))
            found = False
            for o in orders:
                if o.get("order_id") == order_id:
                    o["order_status"] = status
                    found = True
                    break
            if not found:
                return {"success": False, "message": f"Order {order_id} not found"}
            self.json_file.write_text(json.dumps(orders, indent=2, ensure_ascii=False), encoding="utf-8")

            # Update backup file too
            backup = self.orders_dir / f"{order_id}.json"
            if backup.exists():
                data = json.loads(backup.read_text(encoding="utf-8"))
                data["order_status"] = status
                backup.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

            return {"success": True, "message": f"Status updated to {status}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def export_orders(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Path:
        import pandas as pd
        orders = json.loads(self.json_file.read_text(encoding="utf-8"))
        df = pd.json_normalize(orders)
        path = self.orders_dir / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(path, index=False)
        return path

    def __del__(self):
        if self.pool:
            try:
                self.pool.closeall()
            except Exception:
                pass


order_service = OrderService()
