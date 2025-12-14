import httpx
import os
import google.generativeai as genai
from google.generativeai.types import content_types, HarmCategory, HarmBlockThreshold
from collections import defaultdict
import logging
from dotenv import load_dotenv

# Carga variables de entorno (para desarrollo local)
load_dotenv()

# Configuración básica
logger = logging.getLogger("scapi")
BASE_URL = os.getenv("BASE_URL")

# ---------------------------------------------------------
# 1. DEFINICIÓN DE HERRAMIENTAS (WRAPPERS)
# ---------------------------------------------------------
# Estas son las funciones que Gemini podrá "ver" y ejecutar.

def get_product_detail(product_id: int):
    """
    Obtiene los detalles completos de un producto específico por su ID.
    Úsalo si necesitas confirmar precio o stock exacto de un ítem antes de agregarlo.
    Args:
        product_id: El ID numérico del producto a consultar.
    """
    try:
        with httpx.Client() as client:
            response = client.get(f"{BASE_URL}/products/{product_id}", timeout=10)
            if response.status_code == 404:
                return "Producto no encontrado."
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return f"Error consultando detalle: {str(e)}"

def search_products(query: str = None, talle: str = None, color: str = None, categoria: str = None):
    """
    Busca productos en el catálogo basándose en palabras clave o características.
    Si el usuario pregunta algo similar a "¿qué tienes?", "¿Tienes el producto X?", usa esta función sin parámetros.
    Esta función tambien se utiliza para buscar un producto específico si el usuario lo requiriera.

    Args:
        query: Nombre del producto o palabra clave general (ej: "camiseta").
        talle: Talle o tamaño buscado (ej: "40", "S", "M").
        color: Color buscado (ej: "rojo", "negro").
        categoria: Categoría del producto (ej: "calzado", "ropa").
    """
    # Empaquetamos los argumentos en el diccionario que espera db_service
    filters = {
        "q": query,
        "color": color,
        "size": talle,
        "category": categoria
    }
    # Filtramos los Nones para limpiar la búsqueda
    params = {k: v for k, v in filters.items() if v is not None}

    try:
        # EL CAMBIO CLAVE: Petición HTTP real en lugar de db_service
        with httpx.Client() as client:
            response = client.get(f"{BASE_URL}/products", params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                return "La API respondió sin resultados."
            return data
            
    except Exception as e:
        return f"Error HTTP al consultar API de productos: {str(e)}"

def create_cart(phone : str):
    """
    Crea un nuevo carrito de compras vacío para el usuario.
    Úsalo cuando el usuario exprese intención explícita de comenzar una compra
    o si necesita un carrito y no tiene uno (aunque esto último deberías preguntarlo).
    
    Returns:
        El ID del carrito creado (int).
    """
    try:
        # Payload para crear carrito vacío
        body = {"phone_number":int(phone),"items": []}

        # EJECUCIÓN HTTP
        with httpx.Client() as client:
            # Consume POST /carts [cite: 90]
            response = client.post(f"{BASE_URL}/carts", json=body, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return f"Carrito creado exitosamente. ID: {data.get('cart_id')}"

    except Exception as e:
        return f"Error creando carrito vía API: {str(e)}"

def add_to_cart(cart_id: int ,phone: str, product_id: int, qty: int):
    """
    Agrega un producto a un carrito existente o aumenta las unidades compradas.
    IMPORTANTE: Las cantidades SOLO pueden ser 50, 100 o 200.
    
    Args:
        cart_id: El número ID del carrito activo (debes haberlo creado o preguntado antes).
        product_id: El ID numérico del producto a agregar (búscalo con tool_search_products si no lo sabes).
        qty: Cantidad a agregar. Valores permitidos: 50, 100, 200.
    """
    try:
        # Estructura requerida por tu Controller: CartUpdate -> items list
        body = {
            "phone_number": int(phone),
            "items": [
                {"product_id": product_id, "qty": qty}
            ]
        }

        # EJECUCIÓN HTTP
        with httpx.Client() as client:
            # Consume PATCH /carts/:id [cite: 92]
            url = f"{BASE_URL}/carts/{cart_id}"
            response = client.patch(url, json=body, timeout=10)
            
            # Si la API devuelve 400 (Bad Request) por la validación de cantidad,
            # httpx lanzará un error aquí que capturamos abajo.
            response.raise_for_status()
            
            return response.json()

    except httpx.HTTPStatusError as e:
        # Aquí capturamos el mensaje de "Solo cantidad 50, 100, 200" que manda tu API
        return f"La API rechazó la operación: {e.response.text}"
    except Exception as e:
        return f"Error agregando producto: {str(e)}"
    
def dismiss_to_cart(cart_id: int, phone: str, product_id: int, qty: int):
    """
    Disminuye la cantidad de unidades de un producto a un carrito existente.
    IMPORTANTE: Las cantidades a disminuir SOLO pueden ser 50, 100 o 200.
    
    Args:
        cart_id: El número ID del carrito activo (debes haberlo creado o preguntado antes).
        product_id: El ID numérico del producto a agregar (búscalo con tool_search_products si no lo sabes).
        qty: Cantidad a disminuir. Valores permitidos: 50, 100, 200.
    """
    try:
        # Estructura requerida por tu Controller: CartUpdate -> items list
        body = {
            "phone_number": int(phone),
            "items": [
                {"product_id": product_id, "qty": (-1*qty)}
            ]
        }

        # EJECUCIÓN HTTP
        with httpx.Client() as client:
            url = f"{BASE_URL}/carts/{cart_id}"
            response = client.patch(url, json=body, timeout=10)
            
            response.raise_for_status()
            
            return response.json()

    except httpx.HTTPStatusError as e:
        # Aquí capturamos el mensaje de "Solo cantidad 50, 100, 200" que manda tu API
        return f"La API rechazó la operación: {e.response.text}"
    except Exception as e:
        return f"Error agregando producto: {str(e)}"

def get_cart_details(phone: int):
    """
    Consulta el ID de un carrito en base al número de teléfono del cliente.
    
    Args:
        phone: numero de telefono del cliente
    """
    try:
        with httpx.Client() as client:
            response = client.get(f"{BASE_URL}/carts/{phone}/id", timeout=10)
            
            if response.status_code == 404:
                return "El carrito no existe."
            
            response.raise_for_status()
            return response.json()

    except Exception as e:
        return f"Error consultando carrito: {str(e)}"

def get_cart_items(cart_id:int):
    """
    Busca los productos que tiene un carrito específico.
    
    Args:
        cart_id: El ID del carrito a consultar.
    """
    try:
        with httpx.Client() as client:
            # Consume GET /carts/:id/items
            response = client.get(f"{BASE_URL}/carts/{cart_id}/items", timeout=10)
            if response.status_code == 404:
                return "El carrito no existe."
            response.raise_for_status()
            return response.json()

    except Exception as e:
        return f"Error consultando ítems del carrito: {str(e)}"

def remove_item(cart_id: int,phone:str, product_id: int):
    """
    Elimina un producto específico del carrito.
    
    Args:
        cart_id: El ID del carrito.
        product_id: El ID del producto a borrar.
    """
    try:
        # En tu lógica de controller, enviar qty=0 elimina el ítem.
        body = {
            "phone_number": int(phone),
            "items": [
                {"product_id": product_id, "qty": 0} # 0 indica borrar
            ]
        }

        with httpx.Client() as client:
            # Reutiliza PATCH /carts/:id
            response = client.patch(f"{BASE_URL}/carts/{cart_id}", json=body, timeout=10)
            response.raise_for_status()
            return "Producto eliminado del carrito vía API."

    except Exception as e:
        return f"Error eliminando producto: {str(e)}"


# Esta lista se la pasaremos al modelo.
my_tools_list = [
    get_product_detail,
    search_products,
    create_cart,
    add_to_cart,
    dismiss_to_cart,
    get_cart_details,
    get_cart_items,
    remove_item
]

tools_map = {
    'search_products': search_products,
    'create_cart': create_cart,
    'add_to_cart': add_to_cart,
    'dismiss_to_cart': dismiss_to_cart,
    'get_cart_details': get_cart_details,
    'get_cart_items': get_cart_items,
    'remove_item': remove_item,
    'get_product_detail': get_product_detail
}

# ---------------------------------------------------------
# PROMPT DEL SISTEMA (PERSONALIDAD)
# ---------------------------------------------------------
SYSTEM_INSTRUCTION = """
Eres el Asistente Virtual de Ventas de Laburen.com, especializado en pedidos mayoristas de vestimenta.

CAPACIDADES:
- Consultar productos del catálogo (nombre, precio, stock)
- Gestionar carritos de compra (crear, agregar, modificar, consultar)
- Responder preguntas sobre productos específicos y disponibilidad

REGLAS DE NEGOCIO CRÍTICAS:
1. TIPOS DE PRENDAS: 
    - Los tipos son: camiseta, falda, sudadera, pantalón, chaqueta, camisa. 
    - Intenta siempre clasificar los productos con estos tipos.
    - Para cada categoría deber respetar las tildes.
    - Estos tipos están incluidos en el nombre del producto (formato: tipo_talle_color)
    - Si el usuario pide una prenda que no pertenece a los tipos listados, dile que no la tenemos ese tipo de prenda e indícale los tipos de prendas que sí tenemos(camiseta, falda, pantalón, chaqueta y camisa.).

2. TALLAS DISPONIBLES: s, m, l, xl, xxl.

3. CATEGORIAS: 
    - Categorias válidas: formal, deportivo, casual.
    - Intenta siempre clasificar los productos en estas categorías.

4. LOTES FIJOS: Solo vendemos en cantidades de 50, 100 o 200 unidades por producto
   - Si el usuario pide otra cantidad, explícale amablemente que solo manejamos esos lotes.
   
5. PRECIOS VARIABLES: Los precios cambian según el lote (50/100/200)
   - Siempre consulta precios con las herramientas, nunca los inventes
   
6. GESTIÓN DE CARRITO:
   - Primero verifica si el cliente tiene un carrito activo, usa la tool get_cart_details
   - Si no conoces el cart_id de un cliente, usa usa la tool  get_cart_details para obtenerlo
   - Si no existe carrito: créalo automáticamente sin preguntarle al cliente con la tool create_cart
   - Guarda el cart_id en contexto para operaciones futuras
   - Si un cliente pide ver el carrito, usa get_cart_details
   - Para agregar productos SIEMPRE necesitas: product_id y cart_id
   - Los clientes no conocen los IDs, así que si quieres eliminar o modificar la cantidad de unidades de un producto dentro de un carrito busca primero el product_id con get_cart_items y luego preguntale al cliente si ese es realmente el producto que quiere modificar. 

7. CONSIDERACIONES:
   - Formato del nombre de un producto en la base de datos: "camiseta_m_rojo"
   - Formato para mostrar al usuario: "ID:87 - Camiseta roja talle M"
   - Al listar productos incluye: ID, nombre descriptivo, precio por lote (50/100/200), y stock
   - Usa viñetas, un producto por línea
   - Optimiza para WhatsApp.

FLUJO DE TRABAJO:
1. Pregunta del usuario -> Identifica intención (consulta/compra/modificación)
2. Si menciona un producto sin ID -> Usa search_products primero
3. Para agregar al carrito -> Verifica cart_id -> Si no existe, créalo -> Luego agrega con add_to_cart
4. Para modificar cantidades → Usa update_cart_item o remove_from_cart

TONO Y ESTILO:
- Conciso y directo (ideal para WhatsApp)
- Profesional pero cercano
- Respuestas cortas: 1-3 oraciones máximo cuando sea posible.
- Las respuestas no pueden tener más de 1300 caracteres.
- Usa emojis ocasionales para calidez: ✅ 📦 🛒 (sin excederte)

RESTRICCIONES ESTRICTAS:
 - Las respuestas no pueden tener más de 1300 caracteres.
 - Si el listado de productos que devuelves supera los 1300 caracteres, devuelve hasta los que alcancen ese límite y di "Hay más productos disponibles, si te interesa alguno en particular hazmelo saber."
 - NO inventes información: productos, precios, promociones, stock o IDs
 - NO hables de temas ajenos a la venta mayorista de Laburen.com
 - NO ofrezcas servicios que no están en tus herramientas
 - Si el usuario se desvía del tema: "Mi función es ayudarte con pedidos mayoristas de Laburen.com. ¿Te puedo mostrar nuestro catálogo?"

"""

class AIService:
    """
    Servicio para interactuar con el modelo Gemini de Google Generative AI
    """
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("Falta GEMINI_API_KEY en variables de entorno")
            raise ValueError("Falta GEMINI_API_KEY")

        genai.configure(api_key=api_key)
        

        self.model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=my_tools_list,
            system_instruction=SYSTEM_INSTRUCTION,
            #safety_settings=safety_settings
        )

        # Memoria de sesiones: { 'phone_number': ChatSession }
        self.chat_sessions = {}

    def get_response(self, phone_number: str, user_message: str) -> str:
        """
        Procesa el mensaje del usuario, ejecuta herramientas si es necesario 
        y devuelve la respuesta en texto natural.

        Args:
            - phone_number: Identificador único del usuario (número de teléfono).
            - user_message: Mensaje de entrada del usuario.
        """
        try:
            if phone_number not in self.chat_sessions:
                # history=[] inicia el chat vacío. 
                # enable_automatic_function_calling=True permite que el SDK maneje el bucle de herramientas
                self.chat_sessions[phone_number] = self.model.start_chat(
                    #enable_automatic_function_calling=True
                )
                logger.info(f"Nueva sesión iniciada para {phone_number}")

            
            chat = self.chat_sessions[phone_number]
            
            # Agregar contexto del teléfono
            full_message = f"{user_message}\n\nNúmero de teléfono del cliente: {phone_number}"
            
            # 1. Enviar mensaje inicial
            response = chat.send_message(full_message)
            
            # 2. BUCLE DE RESOLUCIÓN DE HERRAMIENTAS (con límite de iteraciones)
            max_iterations = 100
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                if not response.candidates:
                    logger.warning("No hay candidatos en la respuesta")
                    break
                
                candidate = response.candidates[0]
                
                if candidate.finish_reason == 3:
                    logger.error("🚨 BLOQUEADO POR SAFETY FILTER")
                    if hasattr(candidate, 'safety_ratings'):
                        logger.error(f"Safety ratings: {candidate.safety_ratings}")

                if not candidate.content or not candidate.content.parts:
                    logger.info("No hay más partes de contenido")
                    break
                
                # Extraer function calls
                function_calls = [
                    part.function_call 
                    for part in candidate.content.parts 
                    if hasattr(part, 'function_call') and part.function_call
                ]
                
                if not function_calls:
                    logger.info("No hay más function calls pendientes")
                    break
                
                # Ejecutar todas las function calls
                function_responses = []
                
                for fc in function_calls:
                    func_name = fc.name
                    func_args = dict(fc.args)
                    
                    logger.info(f"[{iteration}] Ejecutando: {func_name} con {func_args}")
                    
                    if func_name in tools_map:
                        try:
                            tool_result = tools_map[func_name](**func_args)
                            logger.info(f"Resultado de {func_name}: {str(tool_result)[:100]}...")
                        except Exception as tool_error:
                            tool_result = f"Error ejecutando {func_name}: {str(tool_error)}"
                            logger.error(f"{tool_result}")
                    else:
                        tool_result = f"Error: Herramienta '{func_name}' no encontrada."
                        logger.error(tool_result)
                    
                    # Crear la respuesta para Gemini
                    function_responses.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=func_name,
                                response={'result': str(tool_result)}
                            )
                        )
                    )
                
                # Enviar todos los resultados de vuelta a Gemini
                if function_responses:
                    response = chat.send_message(function_responses)
                else:
                    break
            
            if iteration >= max_iterations:
                logger.warning(f"⚠️ Límite de iteraciones alcanzado ({max_iterations})")
                return "He procesado tu solicitud, pero tomó más tiempo del esperado. ¿Puedo ayudarte con algo más?"
            
            # 3. Retornar respuesta final
            if response.text:
                return response.text
            else:
                logger.warning("Respuesta sin texto después del ciclo")
                return "Operación completada. ¿Necesitas algo más?"
                
        except Exception as e:
            logger.error(f"Error CRÍTICO en AI Service: {e}")
            status_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
            if(status_code==429):
                return "Lo siento, se alcanzo el límite de consultas en el día. Por favor intenta de nuevo mañana."
            else:
                return "Lo siento, hubo un error interno procesando tu solicitud. Por favor intenta de nuevo."

if __name__ == "__main__":
    #print(tool_search_products(query="camiseta"))
    #print(tool_get_product_detail(140))
    #print(tool_get_cart_details("2284540126"))
    #print(tool_get_cart_items(5))
    #print(tool_add_to_cart("5","2284540126","82","50"))
    #print(get_cart_details("2284540126.0"))
    pass
