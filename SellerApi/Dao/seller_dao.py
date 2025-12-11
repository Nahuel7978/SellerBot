import os
import logging
import psycopg2
from psycopg2 import pool, extensions
from contextlib import contextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
import json

logger = logging.getLogger("scapi")


# Función para convertir el tipo DECIMAL a float de Python
def decimal_to_float(value, curs):
    if value is None:
        return None
    return float(value)


class DateTimeEncoder(json.JSONEncoder):
    """Encoder personalizado para manejar datetime, date y Decimal en JSON."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


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
                SellerDao._db_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 10, dsn=db_url, sslmode='require'
                )
                
                # Registrar solo el adaptador de DECIMAL globalmente
                DECIMAL_OID = extensions.new_type(
                    extensions.DECIMAL.values,
                    'DECIMAL_AS_FLOAT',
                    decimal_to_float
                )
                extensions.register_type(DECIMAL_OID)
                
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
        Busca productos construyendo un patrón de coincidencia
        dentro del campo 'name' basado en q, talle y color.
        """
        # SQL base
        sql = """
            SELECT id, name, descripcion, stock, 
                   price_fivety_units, price_one_hundred_units, price_two_hundred_units 
            FROM products 
            WHERE 1=1
        """
        params = []
        
        # Extraer los filtros
        main_query = filters.get("name", "")
        product_size = filters.get("talle", "")
        product_color = filters.get("color", "")
        
        # Construir condiciones activas
        conditions = [main_query, product_size, product_color]
        active_conditions = [c for c in conditions if c]
        
        # Si hay filtros activos, construir la cláusula WHERE
        if active_conditions:
            search_pattern = "%" + "%".join(active_conditions) + "%"
            sql += " AND name ILIKE %s"
            params.append(search_pattern)
        
        with self.get_cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            result = [dict(zip(columns, row)) for row in rows]
            return result

    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """
        Busca un producto por ID y devuelve sus detalles, incluyendo los precios por volumen.
        Devuelve un diccionario con los detalles del producto o None si no existe.
        """
        sql = """
            SELECT 
                id, 
                name,
                stock 
            FROM products 
            WHERE id = %s
        """
        
        with self.get_cursor() as cur:
            cur.execute(sql, (product_id,))
            row = cur.fetchone() # Usamos fetchone() porque esperamos 0 o 1 resultado

            if row:
                # Mapeo: Transforma tupla a Diccionario Python
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, row))
            
            return None # Retorna None si el producto no fue encontrado

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
        Obtiene los ítems aplicando la lógica de precios por volumen (50, 100, 200 unidades).
        """
        sql = """
            SELECT 
                ci.product_id, 
                p.name, 
                ci.qty, 
                
                CASE ci.qty
                    WHEN 50 THEN p.price_fivety_units
                    WHEN 100 THEN p.price_one_hundred_units
                    WHEN 200 THEN p.price_two_hundred_units
                    ELSE p.price_fivety_units
                END AS applied_price,
                
                (
                    CASE ci.qty
                        WHEN 50 THEN p.price_fivety_units
                        WHEN 100 THEN p.price_one_hundred_units
                        WHEN 200 THEN p.price_two_hundred_units
                        ELSE p.price_fivety_units
                    END * ci.qty
                ) AS subtotal
                
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.cart_id = %s
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (cart_id,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]
        
    def get_cart_one_item(self, cart_id:int, product_id: int):
        """
        Obtiene un ítem específico del carrito.
        """
        sql = """
            SELECT 
                ci.product_id, 
                p.name, 
                ci.qty 
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.cart_id = %s AND ci.product_id = %s
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (cart_id, product_id))
            row = cur.fetchone()
            if row:
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, row))
            return None


    def add_item(self, cart_id: int, product_id: int, qty: int):
        """
        Agrega un ítem o actualiza la cantidad si ya existe.
        Usa lógica 'Upsert' manual para compatibilidad máxima.
        """
        update_sql = """
            UPDATE cart_items 
            SET qty = qty + %s 
            WHERE cart_id = %s AND product_id = %s
        """
        
        insert_sql = """
            INSERT INTO cart_items (cart_id, product_id, qty)
            VALUES (%s, %s, %s)
        """
        
        dissmiss_product_sql="""
            UPDATE products
            SET stock = stock - %s
            WHERE id = %s
        """

        with self.get_cursor() as cur:
            # Intentar actualizar primero
            cur.execute(update_sql, (qty, cart_id, product_id))
            
            if cur.rowcount == 0:
                # No existía, hacer insert
                cur.execute(insert_sql, (cart_id, product_id, qty))
            
            # Actualizar timestamp del carrito
            cur.execute("UPDATE carts SET updated_at = NOW() WHERE id = %s", (cart_id,))
            
            cur.execute(dissmiss_product_sql, (qty, product_id))

            return {"product_id": product_id, "added_qty": qty}
        
    def dismiss_item(self, cart_id: int, product_id: int, qty: int):
        """
        Disminuye la cantidad de un item.
        """
        update_sql = """
            UPDATE cart_items 
            SET qty = qty - %s 
            WHERE cart_id = %s AND product_id = %s
        """
        
        add_product_sql="""
            UPDATE products
            SET stock = stock + %s
            WHERE id = %s
        """

        with self.get_cursor() as cur:
            # Intentar actualizar primero
            cur.execute(update_sql, (qty, cart_id, product_id))
            
            # Actualizar timestamp del carrito
            cur.execute("UPDATE carts SET updated_at = NOW() WHERE id = %s", (cart_id,))
            
            cur.execute(add_product_sql, (qty, product_id))

            return {"product_id": product_id, "added_qty": qty}

    def remove_item(self, cart_id: int, product_id: int):
        """Elimina un ítem del carrito"""
        sql = "DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s"
        with self.get_cursor() as cur:
            cur.execute(sql, (cart_id, product_id))
            # Actualizar timestamp
            cur.execute("UPDATE carts SET updated_at = NOW() WHERE id = %s", (cart_id,))
            return True

