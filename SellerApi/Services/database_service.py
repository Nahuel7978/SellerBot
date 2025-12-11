import logging
# Asumimos que la clase DAO estará en este path. 
# La crearemos en el siguiente paso.
from SellerApi.Dao.seller_dao import SellerDao 

logger = logging.getLogger("scapi")

class DatabaseService:
    def __init__(self):
        self.dao = SellerDao()


    def search_products(self, filters: dict):
        """
        Recibe un diccionario de filtros (ej: {'color': 'rojo'})
        y llama al DAO para obtener la lista.
        """
        logger.info(f"Servicio: Buscando productos con filtros: {filters}")
        return self.dao.get_products(filters)

    def create_cart(self, initial_items: list):
        """
        Crea un carrito. Si vienen ítems iniciales, los inserta también.
        """
        try:
            cart_id = self.dao.create_empty_cart()
            logger.info(f"Servicio: Carrito {cart_id} creado.")

            if initial_items:
                for item in initial_items:
                    self.dao.add_item(cart_id, item.product_id, item.qty)
            
            return cart_id
        except Exception as e:
            logger.error(f"Error en servicio creando carrito: {e}")
            #  lógica de rollback si fallan los items
            raise e

    def get_cart(self, cart_id: int):
        """
        Lógica de Negocio: Un carrito "útil" para el frontend/agente 
        no es solo la tabla 'carts', es la combinación del carrito + sus ítems.
        """
        cart_header = self.dao.get_cart_header(cart_id)
        
        if not cart_header:
            return None

        items = self.dao.get_cart_items(cart_id)

        response = dict(cart_header) 
        response["items"] = items # Agregamos la lista de productos dentro del objeto

        return response

    def get_cart_items(self, cart_id: int):
        """
        Devuelve solo los ítems (validaciones rápidas).
        """
        return self.dao.get_cart_items(cart_id)

    def add_to_cart(self, cart_id: int, product_id: int, qty: int):
        """
        Agrega o actualiza un ítem.
        """
        # Verificar stock antes de agregar
        product = self.dao.get_product_by_id(product_id)
        if product['stock'] < qty: raise Exception(f"No hay stock suficiente, disponible: {product['stock']} unidades.")
        
        return self.dao.add_item(cart_id, product_id, qty)

    def remove_item_from_cart(self, cart_id: int, product_id: int):
        """
        Elimina un ítem del carrito.
        """
        return self.dao.remove_item(cart_id, product_id)