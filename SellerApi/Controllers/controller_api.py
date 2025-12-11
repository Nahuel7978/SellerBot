import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from Services.service import send_whatsapp_message

# Carga variables de entorno (para desarrollo local)
load_dotenv()

# Define el token de verificación desde las variables de entorno
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

router = APIRouter() # <--- ¡FALTA ESTA LÍNEA!

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