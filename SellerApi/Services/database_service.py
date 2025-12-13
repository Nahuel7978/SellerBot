import logging
# Asumimos que la clase DAO estará en este path. 
# La crearemos en el siguiente paso.
from Dao.seller_dao import SellerDao 

logger = logging.getLogger("scapi")

ALLOWED_QUANTITIES = {50, 100, 200}

class DatabaseService:
    """
    Clase de Servicio que contiene la Lógica de Negocio para el acceso a los datos.
    """
    def __init__(self):
        self.dao = SellerDao()


    def _validate_quantity(self, qty: int):
        """
        Método de validación de negocio para la cantidad mínima.

        args:
            - qty: Cantidad a validar.
        """
        if qty not in ALLOWED_QUANTITIES:
            raise ValueError(
                f"La cantidad de un producto debe ser 50, 100 o 200 unidades. Se recibió {qty}."
            )
    
    def get_product(self, id:int):
        """
        Llama al DAO para obtener un producto por ID.

        args:
            - id: ID del producto a buscar.
        """
        logger.info(f"Servicio: Obteniendo producto con ID: {id}")
        return self.dao.get_product_by_id(id)

    def search_products(self, filters: dict):
        """
        Recibe un diccionario de filtros (ej: {'color': 'rojo'})
        y llama al DAO para obtener la lista.

        args:
            - filters: Diccionario con filtros de búsqueda.
        """
        logger.info(f"Servicio: Buscando productos con filtros: {filters}")
        return self.dao.get_products(filters)

    def create_cart(self, phone: int, initial_items: list):
        """
        Crea un carrito. Si vienen ítems iniciales, los inserta también.

        args:
            - phone: Teléfono asociado al carrito.
            - initial_items: Lista de ítems iniciales (puede estar vacía).
        """
        try:
            # 1. Validar todos los ítems antes de la creación
            if initial_items:
                for item in initial_items:
                    # Validamos la cantidad de cada ítem
                    self._validate_quantity(item.qty) 
            
            # 2. Crear la cabecera del carrito (Solo si todos los ítems son válidos)
            cart_id = self.dao.create_empty_cart(phone)
            logger.info(f"Servicio: Carrito {cart_id} creado.")

            # 3. Si hay ítems iniciales, agregarlos
            if initial_items:
                for item in initial_items:
                    # Aquí usamos el método del DAO.
                    self.dao.add_item(cart_id, item.product_id, item.qty)
            
            return cart_id
        except Exception as e:
            logger.error(f"Error en servicio creando carrito: {e}")
            raise e

    def get_cart(self, cart_phone: int):
        """
        Lógica de Negocio: Un carrito "útil" para el frontend/agente 
        no es solo la tabla 'carts', es la combinación del carrito + sus ítems.

        args:
            - cart_phone: Número de teléfono asociado al carrito.
        """
        cart_header = self.dao.get_cart_header(cart_phone)
        
        if not cart_header:
            return None

        return cart_header["id"]

    def get_cart_items(self, cart_id: int):
        """
        Devuelve solo los ítems (validaciones rápidas).

        args:
            - cart_id: ID del carrito.
        """
        
        return self.dao.get_cart_items(cart_id)

    def add_to_cart(self, cart_id: int, product_id: int, qty: int):
        """
        Agrega o actualiza un ítem.

        args:
            - cart_id: ID del carrito.
            - product_id: ID del producto a agregar.
            - qty: Cantidad a agregar.
        """
        self._validate_quantity(abs(qty))

        # Verificar stock antes de agregar
        product = self.dao.get_product_by_id(product_id)
        if product['stock'] < qty: raise Exception(f"No hay stock suficiente, disponible: {product['stock']} unidades.")

        return self.dao.add_item(cart_id, product_id, qty)
    
    def dismiss_to_cart(self, cart_id: int, product_id: int, qty: int):
        """
        Disminuye la cantidad de un ítem en el carrito.

        args:
            - cart_id: ID del carrito.
            - product_id: ID del producto a disminuir.
            - qty: Cantidad a disminuir.
        """
        self._validate_quantity(qty)
        item = self.dao.get_cart_one_item(cart_id, product_id)
        if not item:
            raise Exception(f"El producto {product_id} no está en el carrito {cart_id}.")
        elif(item['qty']<qty):
            raise Exception(f"No se puede disminuir {qty} unidades del producto {product_id} ya que solo hay {item['qty']} en el carrito.")
        elif(item['qty']-qty == 0):
            return self.remove_item_from_cart(cart_id, product_id)
        else:
            return self.dao.dismiss_item(cart_id, product_id, qty)

    def remove_item_from_cart(self, cart_id: int, product_id: int):
        """
        Elimina un ítem del carrito.

        args:
            - cart_id: ID del carrito.
            - product_id: ID del producto a eliminar.
        """
        return self.dao.remove_item(cart_id, product_id)