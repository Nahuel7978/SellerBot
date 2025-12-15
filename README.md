# SellerBot
## Agente de Ventas Mayorista con Gemini & FastAPI

Este repositorio contiene la implementación completa de un Agente de IA Conversacional capaz de vender productos mayoristas (lotes de 50, 100 o 200 unidades) mediante el consumo de una API REST propia y una base de datos PostgreSQL.

El Agente está diseñado bajo una arquitectura de Loopback HTTP, asegurando que el LLM consume los endpoints de la API REST y no llama directamente a la lógica interna, lo que garantiza el desacoplamiento y cumple el requisito de "ejecutar solicitudes HTTP".

## 1. Tecnologías utilizadas.
| Componente     | Tecnología | Rol                                                                                         |
|----------------|------------|---------------------------------------------------------------------------------------------|
| Interfaz       | Twilio     | Canal de comunicación con el cliente.                                                       |
| Hosting        | Railway.app| Plataforma unificada para hosting de la API y la base de datos PostgreSQL.                  |
| Agente         | Gemini 2.5 | Cerebro del agente, encargado de la comprensión del lenguaje y la toma de decisiones.       |
| Backend        | FastAPI    | Recibe un mensaje, gestiona la memoria de la sesión y actúa como orquestador del Agente.    |
| Acceso a Datos | psycopg2   | Capa DAO (Data Access Object) profesional para la manipulación segura de PostgreSQL         |
| Base de Datos  | PostgreSQL | Persistencia de datos para productos (products) y transacciones (carts, cart_items).        |

## 2. Arquitectura del sistema.
El sistema está construido en base a dos servicios diferentes (Seller API y Seller API bot) y una base de datos postgreSQL.

Para el envio y recepción de mensajes de whatsapp se utilizo la plataforma de Twilio.

### 2.1 Seller API.
Servicio encargado de manejar peticiones de acceso a datos.
Este servicio posee multiples endpoints que permiten a un cliente buscar, modificar y agregar datos a la base de datos propuesta.

Los endpoints implementados son:
| Método     | Ruta          | Descripción                                                     |
|------------|---------------|-----------------------------------------------------------------|
| GET        | /products     | Lista productos con filtros dinámicos (nombre, color, talle).   |
| GET        | /products/:id | Detalle de un producto específico. (Requisito Cubierto).        |
| GET        | /cart/:phone  | Devuelve el id de un carrito en base al numero de telefono.     |
| GET        | /cart/:id/items | Devuelve todos los items de un carrito.     |
| POST       | /carts        | Crea un carrito vacío o con ítems iniciales.                    |
| PATCH      | /carts/:id    | Actualiza cantidades o elimina ítems.                           |

El código está estructurado en capas separadas (Controller, Service, DAO) para facilitar la escalabilidad y el mantenimiento.
    
    └── SellerApi/
        ├── Controllers/   
        │   └── controller_api.py (Controladores HTTP)
        ├── Services/
        │   └──  database_service.py (Orquestación de la lógica de negocio)
        ├── Models/
        │   └──  schemas.py
        ├── Dao/
        │   └── seller_dao.py     (SQL puro y Connection Pooling con psycopg2)
        └── main.py             (Punto de entrada de FastAPI)

## 2.2 Seller API Bot.
Este servicio es el encargado de tratar los mensajes envíados por los clientes y generar una respuesta a través de un LLM.
Su funcionamiento consta de exponer un endopoint Webhook para recibir notificaciones automáticas (en tiempo real) cuando se recibe un mensaje de whatsapp y un servicio que trate dicho mensaje.

Endpoint implementado:

| Método     | Ruta          | Descripción                                                     |
|------------|---------------|-----------------------------------------------------------------|
| POST       | /webhook      | Recibe un mensaje y envia una respuesta generada.               |

El servicio que trata el mensaje utiliza el modelo de gemini-2.5-flash como LLM central y el mismo implementa un ciclo de vida de Agente/ToolUse utilizando el Function Calling de Gemini. Las tool programadas para el uso se encargan de acceder a los datos a través de peticiones *http* a **SellerAPI**. 

El Agente es capaz de gestionar los siguientes flujos:

1. **Búsqueda (Tool: search_products)**: El agente consume GET /products para responder consultas como "¿Tenés camisetas talle s?" o "¿Productos rojos?".

2. **Creación (Tool: create_cart)**: Consume POST /carts cuando el usuario pide iniciar una compra.

3. **Adición/Edición (Tool: add_to_cart / dismiss_to_cart /remove_item)**: El agente puede agregar o disminuir la cantidad de unidades de un producto en el carrito, como tambien eliminar al mismo. En esta acción siempre se verifica:

  -  _Validación de Lote_: Solo permite cantidades de 50, 100 o 200 unidades, rechazando otras cantidades con un error HTTP 400 que el LLM explica al usuario (Lógica de Negocio implementada en la capa Service).

  -  _Precios por Volumen_: El cálculo del subtotal en el carrito utiliza el precio correcto (price_fivety_units, price_one_hundred_units, etc.) según la cantidad ingresada, garantizando la precisión transaccional.


La estructura del proyecto es una arquitectura de dos capas.

     └── SellerApiBot/
        ├── Controllers/
        │   └── controller.py (Webhook)
        ├── Services/
        |   └── ai_service.py(Cerebro LLM, Tools HTTP y Memoria)
        └── main.py (Punto de entrada de FastAPI)

## 2.3 Database postgreSQL.
La base de datos posee sólo tres tablas: 
- Products: Almacena todos los productos disponibles.
- Carts: Almacena los carritos correspondientes a un número de telefono.
- Carts_items: Tabla intermedia que almacena los productos por carrito.
<img width="741" height="151" alt="Design diagram-DB" src="https://github.com/user-attachments/assets/6abd1c3d-9ecc-4a27-8be8-f10230b407ed" />

## 2.4 Twilio para WhatsApp.
Twilio para WhatsApp es una API que permite a las empresas integrar WhatsApp en sus sistemas para enviar y recibir mensajes a gran escala, automatizar conversaciones y gestionar interacciones. 
Esta plataforma te provee de un telefono de prueba el cual se configura para que al recibir mensajes los mismos sean desviados a un webhook conocido. En este caso en particular, los mensajes son redirigidos al webhook de **SellerApiBot**.

## 3. Configuración y Despliegue
- Python ≥3.10
- Librerías: Consulte el archivo requirements.txt
- - fastapi, uvicorn
- - httpx (para que el Agente haga peticiones HTTP internas).
- - google-generativeai (para el LLM).
- - psycopg2-binary (para la conexión a PostgreSQL).

El despliegue de ambos servicios, como el de la base de datos, se hizo en la plataforma Railway.

### 3.3 Diagrama de Secuencia (Busqueda de productos) .
<img width="2200" height="1320" alt="Diagrama de secuencia - busqueda de productos(1)" src="https://github.com/user-attachments/assets/114ded4b-069d-4d6f-94bc-e781a9ea8535" />

### 3.4 Diagrama de Secuencia (Crear y agregar producto al carrito)
<img width="2276" height="1807" alt="Diagrama de secuencia - Crear y agregar un producto" src="https://github.com/user-attachments/assets/80c5b7f7-1707-4daa-aebe-b71e67bab848" />

### 3.5 Vista Componentes y Conectores (C&C)
<img width="1421" height="1031" alt="Design diagram-C C - Seller API(2)" src="https://github.com/user-attachments/assets/084c0449-9b09-4de4-bb2b-3c00dc117d40" />

## 4. Mejoras futuras.
En base al avance logrado en el proyecto las futuras implementaciones vendrían de la mano de:
- Manejo de multiples usuarios
- La ampliación de la base de datos para almacenar el perfil del cliente.
- Multiples carritos por usuario.
- Separación de repositorios(repositorio para LLM y otro para API_database).
