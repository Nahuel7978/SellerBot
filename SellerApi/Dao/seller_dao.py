import os
import logging
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from typing import List, Optional, Dict, Any

logger = logging.getLogger("scapi")

class SellerDao:
    _db_pool = None

    def __init__(self):
        """
        Singleton pattern: Inicializa el Pool de conexiones la primera vez que se instancia la clase.
        """
        if not SellerDao._db_pool:
            try:
                # Obtenemos la URL directamente de las variables de entorno
                db_url = os.getenv("DATABASE_URL")
                if not db_url:
                    raise ValueError("DATABASE_URL no está definida en las variables de entorno.")

                # Creamos un pool de conexiones (min: 1, max: 10)
                # sslmode='require' es obligatorio para Railway/Neon/Supabase en producción
                SellerDao._db_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 10, dsn=db_url, sslmode='require'
                )
                logger.info("Connection Pool de PostgreSQL inicializado correctamente.")
            except Exception as e:
                logger.error(f"Error fatal iniciando el pool de BD: {e}")
                raise e

    @contextmanager
    def get_cursor(self):
        """
        Context Manager para obtener una conexión del pool y devolverla automáticamente.
        Maneja commit/rollback y cierre de cursor.
        """
        conn = None
        try:
            conn = SellerDao._db_pool.getconn()
            cursor = conn.cursor()
            yield cursor
            conn.commit()
            cursor.close()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error ejecutando SQL: {e}")
            raise e
        finally:
            if conn:
                SellerDao._db_pool.putconn(conn)

    # ---------------------------------------------------------
    # MÉTODOS DE PRODUCTOS
    # ---------------------------------------------------------

    def get_products(self, filters: Dict[str, Any]) -> List[Dict]:
        """
        Construye una query dinámica basada en los filtros recibidos.
        """
        sql = "SELECT id, name, description, price, stock FROM products WHERE 1=1"
        params = []

        if filters.get("name"):
            # Búsqueda parcial (ILIKE es case-insensitive)
            sql += " AND (name ILIKE %s OR description ILIKE %s)"
            search_term = f"%{filters['name']}%"
            params.extend([search_term, search_term])

        if filters.get("categoria"):
             sql += " AND category = %s"
             params.append(filters["categoria"])
        

        with self.get_cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            
            # Convertimos tuplas a lista de diccionarios
            columns = [desc[0] for desc in cur.description]
            result = [dict(zip(columns, row)) for row in rows]
            return result

    # ---------------------------------------------------------
    # MÉTODOS DE CARRITO
    # ---------------------------------------------------------

    def create_empty_cart(self) -> int:
        """Crea un carrito vacío y devuelve su ID"""
        sql = "INSERT INTO carts (created_at, updated_at) VALUES (NOW(), NOW()) RETURNING id"
        with self.get_cursor() as cur:
            cur.execute(sql)
            cart_id = cur.fetchone()[0]
            return cart_id

    def get_cart_header(self, cart_id: int) -> Optional[Dict]:
        """Obtiene los datos generales del carrito"""
        sql = "SELECT id, created_at, updated_at FROM carts WHERE id = %s"
        with self.get_cursor() as cur:
            cur.execute(sql, (cart_id,))
            row = cur.fetchone()
            if row:
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, row))
            return None

    def get_cart_items(self, cart_id: int) -> List[Dict]:
        """
        Obtiene los items uniendo con la tabla de productos para dar contexto (nombre, precio)
        """
        sql = """
            SELECT ci.product_id, p.name, p.price, ci.qty, (p.price * ci.qty) as subtotal
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.cart_id = %s
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (cart_id,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]

    def add_item(self, cart_id: int, product_id: int, qty: int):
        """
        Agrega un ítem o actualiza la cantidad si ya existe.
        Usa lógica 'Upsert' manual para compatibilidad máxima.
        """
        # 1. Intentamos actualizar primero (si ya existe el producto en el carrito)
        update_sql = """
            UPDATE cart_items 
            SET qty = qty + %s 
            WHERE cart_id = %s AND product_id = %s
        """
        
        # 2. Si no actualizó nada, insertamos
        insert_sql = """
            INSERT INTO cart_items (cart_id, product_id, qty)
            VALUES (%s, %s, %s)
        """

        with self.get_cursor() as cur:
            # Intentamos update (sumar a lo que había)
            # NOTA: Si quieres reemplazar la cantidad en vez de sumar, cambia 'qty + %s' por '%s'
            cur.execute(update_sql, (qty, cart_id, product_id))
            
            if cur.rowcount == 0:
                # No existía, hacemos insert
                cur.execute(insert_sql, (cart_id, product_id, qty))
            
            # Actualizamos el timestamp del carrito
            cur.execute("UPDATE carts SET updated_at = NOW() WHERE id = %s", (cart_id,))
            
            return {"product_id": product_id, "added_qty": qty}

    def remove_item(self, cart_id: int, product_id: int):
        """Elimina un ítem del carrito"""
        sql = "DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s"
        with self.get_cursor() as cur:
            cur.execute(sql, (cart_id, product_id))
            # Actualizamos timestamp
            cur.execute("UPDATE carts SET updated_at = NOW() WHERE id = %s", (cart_id,))
            return True