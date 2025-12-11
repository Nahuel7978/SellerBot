from pydantic import BaseModel
from typing import List, Optional

# Modelo para cuando agregamos/editamos un ítem en el carrito
class CartItemRequest(BaseModel):
    product_id: int
    qty: int # Si es positivo agrega/actualiza, si es 0 o negativo podría descartar

# Modelo para la actualización del carrito (Lista de ítems)
class CartUpdate(BaseModel):
    phone_number:int
    items: List[CartItemRequest]