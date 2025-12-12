# SellerBot
## Agente de Ventas Mayorista con Gemini & FastAPI

Este repositorio contiene la implementación completa de un Agente de IA Conversacional capaz de vender productos mayoristas (lotes de 50, 100 o 200 unidades) mediante el consumo de una API REST propia y una base de datos PostgreSQL.

El Agente está diseñado bajo una arquitectura de Loopback HTTP, asegurando que el LLM consume los endpoints de la API REST y no llama directamente a la lógica interna, lo que garantiza el desacoplamiento y cumple el requisito de "ejecutar solicitudes HTTP".

## 1. ⚙️ Arquitectura de Alto Nivel
| Componente     | Tecnología | Rol                                                                                         |
|----------------|------------|---------------------------------------------------------------------------------------------|
| Interfaz       | Twilio     | Canal de comunicación con el cliente.                                                       |
| Hosting        | Railway.app| Plataforma unificada para hosting de la API y la base de datos PostgreSQL.                  |
| Agente         | Gemini 2.5 | Cerebro del agente, encargado de la comprensión del lenguaje y la toma de decisiones.       |
| Backend        | FastAPI    | Recibe un mensaje, gestiona la memoria de la sesión y actúa como orquestador del Agente.    |
| Acceso a Datos | psycopg2   | Capa DAO (Data Access Object) profesional para la manipulación segura de PostgreSQL         |
| Base de Datos  | PostgreSQL | Persistencia de datos para productos (products) y transacciones (carts, cart_items).        |
|----------------|------------|---------------------------------------------------------------------------------------------|

## 2. Configuración y Despliegue
- Python ≥3.10
- Librerías: Consulte el archivo requirements.txt
- - fastapi, uvicorn
- - httpx (para que el Agente haga peticiones HTTP internas).
- - google-generativeai (para el LLM).
- - psycopg2-binary (para la conexión a PostgreSQL).

### 2.1 Estructura del Proyecto
El código está estructurado en capas separadas (Controller, Service, DAO) para facilitar la escalabilidad y el mantenimiento.
.
└── SellerApi/
    ├── Controllers/
    │   └── controller_api.py (Controladores HTTP, Webhook)
    ├── Services/
    │   ├── ai_service.py     (🧠 Cerebro LLM, Tools HTTP y Memoria)
    │   ├── database_service.py (Orquestación de la lógica de negocio)
    │   └── tools.py          (Funciones que el LLM puede ejecutar)
    ├── Dao/
    │   └── seller_dao.py     (SQL puro y Connection Pooling con psycopg2)
    └── main.py             (Punto de entrada de FastAPI)

## 3 Pruebas y Funcionalidad del Agente

El Agente implementa un ciclo de vida de Agente/Tool Use utilizando el Function Calling de Gemini.

### 3.1 Endpoints Implementados (API REST)

Se han implementado y validado todos los endpoints requeridos.

| Método     | Ruta          | Descripción                                                     |
|------------|---------------|-----------------------------------------------------------------|
| GET        | /products     | Lista productos con filtros dinámicos (nombre, color, talle).   |
| GET        | /products/:id | Detalle de un producto específico. (Requisito Cubierto).        |
| POST       | /carts        | Crea un carrito vacío o con ítems iniciales.                    |
| PATCH      | /carts/:id    | Actualiza cantidades o elimina ítems.                           |
|------------|---------------|-----------------------------------------------------------------|

## 3.2. Lógica de Negocio y Tools

El Agente es capaz de gestionar los siguientes flujos:

1. Búsqueda (Tool: tool_search_products): El agente consume GET /products para responder consultas como "¿Tenés camisetas talle s?" o "¿Productos rojos?".

2. Creación (Tool: tool_create_cart): Consume POST /carts cuando el usuario pide iniciar una compra.

3.   Adición/Edición (Tool: tool_add_to_cart / tool_remove_item): El agente gestiona la lógica de precios por volumen:

  -  Validación de Lote: Solo permite cantidades de 50, 100 o 200 unidades, rechazando otras cantidades con un error HTTP 400 que el LLM explica al usuario (Lógica de Negocio implementada en la capa Service).

  -  Precios por Volumen: El cálculo del subtotal en el carrito utiliza el precio correcto (price_fivety_units, price_one_hundred_units, etc.) según la cantidad ingresada, garantizando la precisión transaccional.

