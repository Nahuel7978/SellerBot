import os
from fastapi import APIRouter, HTTPException , Query, status, Form
from fastapi.responses import JSONResponse, Response
import json
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from dotenv import load_dotenv
from Services.ai_service import AIService

# Carga variables de entorno (para desarrollo local)
load_dotenv()

router = APIRouter()

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
