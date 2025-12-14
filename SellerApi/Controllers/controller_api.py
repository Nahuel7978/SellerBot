import os
from fastapi import APIRouter, HTTPException , Query, status
from fastapi.responses import JSONResponse
import json
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from dotenv import load_dotenv
from Services.database_service import DatabaseService
from Model.schemas import  CartUpdate

# Carga variables de entorno (para desarrollo local)
load_dotenv()

router = APIRouter()

db_service = DatabaseService()


@router.get("/products/{product_id}")
async def get_product_detail(product_id: int):
    """
    Detalle de un producto específico.
    args:
    - product_id: ID del producto a buscar.
    """
    product = db_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return JSONResponse(content=product, status_code=200)

@router.get("/products")
async def get_products(
    q: Optional[str] = Query(None, description="Búsqueda general por nombre o descripción"),
    size: Optional[str] = Query(None, description="Filtro por talle"),
    color: Optional[str] = Query(None, description="Filtro por color"),
    category: Optional[str] = Query(None, description="Filtro por categoría")
):
    """
    Busca productos. Si no se pasan parámetros, devuelve todos.
    Si se pasan parámetros (q, talle, color, categoria), filtra los resultados.

    args:
    - q: Búsqueda general (nombre o descripción).
    - size: Filtro por talle.
    - color: Filtro por color.
    - category: Filtro por categoría.
    """
    try:
        # Empaquetamos los filtros en un diccionario limpio
        filters = {
            "name": q,
            "talle": size, 
            "color": color, 
            "category": category
        }
        
        # Llamamos al servicio (método que crearemos luego)
        # Nota: Eliminamos claves con valor None para no ensuciar la query
        
        active_filters = {k: v for k, v in filters.items() if v is not None}
        
        products = db_service.search_products(active_filters)
        
        if not products:
            # Retornamos lista vacía en vez de 404 para búsquedas sin resultados
            return JSONResponse(content=[], status_code=200)
            
        return JSONResponse(content=products, status_code=200)

    except Exception as e:
        print(f"Error buscando productos: {e}")
        raise HTTPException(status_code=500, detail="Error interno buscando productos")

@router.get("/carts/{cart_phone}/id")
async def get_cart(cart_phone: int):
    """
    Busca un carrito por su ID.
    
    args:
    - cart_phone: Número de teléfono asociado al carrito.
    """
    try:
        cart = db_service.get_cart(cart_phone)
        if not cart:
            raise HTTPException(status_code=404, detail=f"Carrito correspondiente a {cart_phone} no encontrado")
        return JSONResponse(content=json.loads(to_json(cart)) , status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/carts/{cart_id}/items")
async def get_cart_items(cart_id: int):
    """
    Busca solo los ítems de un carrito específico.

    args:
     - cart_id: ID del carrito.
    """
    try:
        items = db_service.get_cart_items(cart_id)
        return JSONResponse(content=items, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.patch("/carts/{cart_id}")    
async def update_cart(cart_id:int,cart_update: CartUpdate):
    """
    Agrega, actualiza o elimina productos del carrito.
    Body esperado: {"phone_number":2284, "items": [{ "product_id": 1, "qty": 2 }] }
    
    Lógica:
    - Si qty > 0: Agrega o actualiza cantidad.
    - Si qty == 0: Elimina el producto del carrito (Lógica de 'Discard').
    - Si qty < 0: Disminuye la cantidad (si queda 0 o menos, elimina el ítem).

    args:
    - cart_id: ID del carrito a modificar.
    - cart_update: Objeto con número de teléfono y lista de ítems a modificar.
    """
    try:
        # Verificamos primero si el carrito existe
        found_cart_id = db_service.get_cart(cart_update.phone_number)
        if found_cart_id is None:
            raise HTTPException(status_code=404, detail="Carrito no encontrado")
        
        if found_cart_id != cart_id:
            raise HTTPException(
                status_code=400, 
                detail="El cart_id no corresponde al teléfono proporcionado"
            )

        results = []
        for item in cart_update.items:
            if item.qty > 0:
                # Caso: Agregar / Actualizar
                res = db_service.add_to_cart(cart_id, item.product_id, item.qty)
                results.append(res)
            elif(item.qty < 0):
                res = db_service.dismiss_to_cart(cart_id, item.product_id, abs(item.qty))
            else:
                res = db_service.remove_item_from_cart(cart_id, item.product_id)
                results.append({"product_id": item.product_id, "status": "removed"})
        
        return JSONResponse(content={"status": "updated", "changes": results}, status_code=200)

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error actualizando carrito: {e}")
        raise HTTPException(status_code=500, detail="Error actualizando el carrito")
    
@router.post("/carts", status_code=status.HTTP_201_CREATED)
async def create_cart(cart_data: CartUpdate):
    """
    Crea un nuevo carrito de compras.
    Opcionalmente puede recibir ítems iniciales.
    Body: { "items": [{ "product_id": 1, "qty": 1 }] }

    args:
        - cart_data: Objeto con número de teléfono y lista de ítems iniciales.
    """
    try:
        # Llamamos al servicio para crear el carrito en la BD
        # Le pasamos la lista de ítems (puede estar vacía)
        new_cart_id = db_service.create_cart(cart_data.phone_number,cart_data.items)
        
        if not new_cart_id:
            raise HTTPException(status_code=500, detail="No se pudo crear el carrito")

        return JSONResponse(
            content={
                "message": "Carrito creado exitosamente", 
                "cart_id": new_cart_id
            }, 
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        print(f"Error creando carrito: {e}")
        raise HTTPException(status_code=500, detail="Error interno al crear carrito")
    

# ---------------------------------------------------------
# MÉTODO AUXILIAR PARA SERIALIZACIÓN JSON
# ---------------------------------------------------------

class DateTimeEncoder(json.JSONEncoder):
    """Encoder personalizado para manejar datetime, date y Decimal en JSON."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def to_json(data: Any) -> str:
    """
    Convierte cualquier estructura de datos a JSON,
    manejando automáticamente datetime, date y Decimal.
    """
    return json.dumps(data, cls=DateTimeEncoder, ensure_ascii=False)