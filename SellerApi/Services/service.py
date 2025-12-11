import httpx
import os
import logging

# Configuración logger
logger = logging.getLogger("scapi")

# Credenciales
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
API_VERSION = "v24.0" # O la versión que te indique Meta

async def send_whatsapp_message(to_number: str, message_text: str):
    """
    Envía un mensaje de texto a través de la Cloud API de WhatsApp de forma asíncrona.
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        logger.error("Faltan credenciales de WhatsApp en el .env")
        return

    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            
            # Verificación básica de error HTTP
            response.raise_for_status()
            
            logger.info(f"Mensaje enviado a {to_number}: {response.json()}")
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Error HTTP al enviar mensaje: {e.response.text}")
    except Exception as e:
        logger.error(f"Error inesperado enviando mensaje: {e}")