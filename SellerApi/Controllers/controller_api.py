import os
from fastapi import APIRouter, HTTPException , Query, status, Form
from fastapi.responses import JSONResponse, Response
import json
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from dotenv import load_dotenv
from Services.database_service import DatabaseService
from Services.ai_service import AIService
from Model.schemas import  CartUpdate

# Carga variables de entorno (para desarrollo local)
load_dotenv()

# Define el token de verificación desde las variables de entorno
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

router = APIRouter()

db_service = DatabaseService()
ai_service = AIService()

# -----------------------------------------------------------
# 1. ENDPOINT DE VERIFICACIÓN (GET)
# Meta lo usa solo una vez para validar que el webhook es tuyo.
# -----------------------------------------------------------
@router.post("/webhook", status_code=status.HTTP_200_OK)
async def whatsapp_webhook(
    # Twilio envía el número del remitente en el campo 'From'
    From: str = Form(..., alias="From"), 
    # Twilio envía el contenido del mensaje en el campo 'Body'
    Body: str = Form(..., alias="Body") 
):
    # 1. Limpieza del número: Twilio incluye "whatsapp:" (ej: "whatsapp:+549...")
    phone_number = From.replace("whatsapp:", "")
    user_message = Body

    # 2. Procesar el mensaje con tu AI Service
    ai_response_text = ai_service.get_response(phone_number, user_message)

    # 3. Twilio espera una respuesta en formato TwiML (XML)
    twiml_response = f"""
    <Response>
        <Message>{ai_response_text}</Message>
    </Response>
    """
    return Response(content=twiml_response, media_type="application/xml")

# -----------------------------------------------------------

@router.post("/test-message")
async def test_message(message: str, phone_number: int):
    try:
        response = ai_service.get_response(str(phone_number), message)        
        return JSONResponse(content={"response": response}, status_code=200)
    except Exception as e:
        print(f"Error respondiendo la consulta: {e}")
        raise HTTPException(status_code=500, detail="Error interno respondiendo la consulta")


@router.get("/products/{product_id}")
async def get_product_detail(product_id: int):
    """
    Endpoint requerido: Detalle de un producto específico.
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

@router.get("/carts/{cart_phone}")
async def get_cart(cart_phone: int):
    """
    Busca un carrito por su ID.
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
    """
    try:
        # Verificamos primero si el carrito existe
        id = db_service.get_cart(cart_update.phone_number)
        if not id:
             # Si no existe, opcionalmente podríamos crearlo aquí o dar 404
             raise HTTPException(status_code=404, detail="Carrito no encontrado")

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