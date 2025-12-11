import os
from fastapi import APIRouter, Request, HTTPException , Query, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import PlainTextResponse
import json
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from dotenv import load_dotenv
from Services.whatsapp_service import send_whatsapp_message
from Services.database_service import DatabaseService
from Model.schemas import  CartUpdate

# Carga variables de entorno (para desarrollo local)
load_dotenv()

# Define el token de verificación desde las variables de entorno
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

router = APIRouter()

db_service = DatabaseService()


# -----------------------------------------------------------
# 1. ENDPOINT DE VERIFICACIÓN (GET)
# Meta lo usa solo una vez para validar que el webhook es tuyo.
# -----------------------------------------------------------

@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Maneja la verificación del webhook de Meta.
    """
    try:
        # Extrae los parámetros de la URL
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                # Éxito: El token es válido, devuelve el 'challenge'
                print("Webhook verificado con éxito!")
                return PlainTextResponse(content=challenge, status_code=200)
            else:
                # Error: Tokens no coinciden
                raise HTTPException(status_code=403, detail="Token de verificación inválido")
        
        # Si no tiene los parámetros de verificación, es un GET normal
        return {"status": "Webhook endpoint está funcionando."}

    except Exception as e:
        print(f"Error en la verificación: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# -----------------------------------------------------------
# 2. ENDPOINT DE MENSAJES (POST)
# Aquí llegan todos los mensajes de WhatsApp.
# -----------------------------------------------------------

@router.post("/webhook")
async def handle_message(request: Request):
    try:
        data = await request.json()
        
        # Validación rápida para evitar procesar estados (sent, delivered, read)
        # Solo nos interesan los mensajes entrantes
        is_status_update = data.get("entry", [])[0].get("changes", [])[0].get("value", {}).get("statuses")
        if is_status_update:
            return {"status": "ignored_status_update"}

        if data.get("object") == "whatsapp_business_account":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "messages":
                        messages = change.get("value", {}).get("messages", [])
                        
                        for message in messages:
                            # Procesamos solo texto por ahora
                            if message.get("type") == "text":
                                # 1. Extraer el número del usuario
                                from_number = message.get("from") 
                                incoming_text = message.get("text", {}).get("body")
                                
                                print(f"Mensaje de {from_number}: {incoming_text}")
                                
                                # 2. Generar respuesta (Echo)
                                response_text = f"Echo: {incoming_text}"
                                
                                # 3. LLAMAR A LA FUNCIÓN DE ENVÍO
                                # Nota: await es obligatorio porque la función es async
                                await send_whatsapp_message(from_number, response_text)

        return {"status": "ok"}
        
    except Exception as e:
        print(f"Error procesando webhook: {e}")
        # Siempre devolver 200 a Meta, o te bloquearán el webhook si fallas mucho
        return {"status": "error", "message": str(e)}

# -----------------------------------------------------------

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
    
@router.get("/carts/{cart_phone}/items")
async def get_cart_items(cart_phone: int):
    """
    Busca solo los ítems de un carrito específico.
    """
    try:
        items = db_service.get_cart_items(db_service.get_cart(cart_phone))
        return JSONResponse(content=items, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.patch("/carts/{cart_phone}")    
async def update_cart(cart_update: CartUpdate):
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
        cart_id = db_service.get_cart(cart_update.phone_number)
        if not cart_id:
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