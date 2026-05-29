import os
import logging
import jwt
from urllib.parse import quote, unquote
from fastapi import FastAPI, Request, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import Form, File, UploadFile
from typing import List, Optional
from pathlib import Path
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="AliMarket BFF Gateway", version="2026.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5000")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8000")

with open(BASE_DIR / "public_key.pem", "r") as f:
    PUBLIC_KEY = f.read()

def extraer_datos_de_jwt(token: str):
    if not token:
        return {}
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=['RS256'])
        return payload
    except Exception:
        return {}

# ==========================================
# RUTAS DEL HUB PRINCIPAL (LANDING)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def index_view(request: Request, msg: str = None):
    log_operacion = unquote(msg) if msg else "[SISTEMA] Clúster perimetral AliMarket listo para el despacho."
    return templates.TemplateResponse("index.html", {"request": request, "logs": log_operacion})

# ==========================================
# SECCIÓN: PROVEEDORES INDEPENDIENTES
# ==========================================

@app.get("/proveedor", response_class=HTMLResponse)
async def proveedor_view(request: Request, msg: str = None):
    token = request.cookies.get("access_token_proveedor")
    datos = extraer_datos_de_jwt(token) if token else {}
    mensaje_limpio = unquote(msg) if msg else "[SISTEMA] Conexión establecida de forma segura con la red data-isolated."
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{AUTH_SERVICE_URL}/api/auth/proveedores/count", timeout=3.0)
            count = res.json().get("count", 0) if res.status_code == 200 else 0
    except Exception as e:
        logger.error(f"[BFF] Error al consultar contador de proveedores: {str(e)}")
        count = 0
    if datos.get("role") == "proveedor":
        productos = []
        try:
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                res_prod = await client.get(f"{ORDER_SERVICE_URL}/api/orders/catalog/products/", headers=headers, timeout=3.0)
                if res_prod.status_code == 200:
                    productos = res_prod.json()
        except Exception as e:
            logger.error(f"[BFF] Error al recuperar catálogo para panel: {str(e)}")
            
        return templates.TemplateResponse("proveedor.html", {
            "request": request, "vista": "panel", "productos": productos, "msg": mensaje_limpio, "username": datos.get("sub")
        })
    vista_actual = "registro" if count == 0 else "login"
    return templates.TemplateResponse("proveedor.html", {
        "request": request, "vista": vista_actual, "msg": mensaje_limpio
    })

@app.post("/proveedor/register")
async def proveedor_register(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{AUTH_SERVICE_URL}/api/auth/register", 
                json={
                    "username": username, 
                    "email": email, 
                    "password": password, 
                    "role": "proveedor"
                }, 
                timeout=5.0
            )
        
        if res.status_code == 201:
            log_msg = "[SUCCESS_AUTH] Proveedor maestro creado exitosamente. Inicie sesión ahora."
        else:
            error_detalle = res.json().get("error", "Campos duplicados o parámetros inválidos")
            log_msg = f"[ERROR_AUTH] {error_detalle}"
            
    except Exception as e:
        logger.error(f"[BFF CRITICAL] Error de red hacia auth-service: {str(e)}")
        log_msg = "[ERROR_AUTH] El servicio de autenticación corporativo no responde en la red backend-mesh."
        
    return RedirectResponse(url=f"/proveedor?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/proveedor/login")
async def proveedor_login(username: str = Form(...), password: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{AUTH_SERVICE_URL}/api/auth/login", 
                json={"username": username, "password": password},
                timeout=4.0
            )
        if res.status_code == 200:
            data = res.json()
            token = data.get("access_token")
            datos = extraer_datos_de_jwt(token)
            if datos.get("role") != "proveedor":
                log_msg = "[DENEGADO] Esta cuenta no pertenece al escalafón de Proveedores."
                return RedirectResponse(url=f"/proveedor?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)
            response = RedirectResponse(url="/proveedor", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(key="access_token_proveedor", value=token, httponly=True, samesite="strict")
            return response
        else:
            log_msg = "Acceso Denegado Inténtelo otra vez (Credenciales incorrectas)"
            return RedirectResponse(url=f"/proveedor?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"[BFF CRITICAL] Fallo login proveedor: {str(e)}")
        return RedirectResponse(url=f"/proveedor?msg={quote('Error de comunicación con clúster auth.')}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/proveedor/logout")
async def proveedor_logout():
    log_msg = "[SISTEMA] Sesión del Proveedor destruida correctamente de la red aislada."
    response = RedirectResponse(url=f"/proveedor?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token_proveedor")
    return response

@app.post("/catalog/add")
async def add_product(
    request: Request, 
    name: str = Form(...), 
    price: float = Form(...), 
    stock: int = Form(...),
    description: Optional[str] = Form(""),
    offer_price: Optional[float] = Form(None),
    is_offer: Optional[str] = Form("false"),
    img_archivos: List[UploadFile] = File(None) 
):
    token = request.cookies.get("access_token_proveedor")
    datos = extraer_datos_de_jwt(token) if token else {}
    if datos.get("role") != "proveedor":
        return RedirectResponse(url=f"/proveedor?msg={quote('[DENEGADO] Acción restringida.')}", status_code=status.HTTP_303_SEE_OTHER)
    try:
        es_oferta_bool = "true" if is_offer in ["on", "true", "1"] else "false"
        precio_oferta_final = f"{offer_price:.2f}" if (offer_price and es_oferta_bool == "true") else ""

        data_payload = {
            "name": str(name).strip(),
            "price": f"{price:.2f}",
            "stock": str(stock),
            "description": description if description else "Producto corporativo inyectado",
            "is_offer": es_oferta_bool,
            "offer_price": precio_oferta_final
        }
        files_payload = []
        if img_archivos:
            for upload_file in img_archivos:
                if upload_file and getattr(upload_file, "filename", "") != "":
                    file_content = await upload_file.read()
                    if len(file_content) > 0:
                        files_payload.append(
                            ("img_archivos", (upload_file.filename, file_content, upload_file.content_type or "image/jpeg"))
                        )
                    await upload_file.seek(0)
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{ORDER_SERVICE_URL}/api/orders/catalog/products/", 
                headers=headers, data=data_payload, files=files_payload if files_payload else None, timeout=20.0
            )
        if res.status_code == 201:
            log_msg = f"[SUCCESS] Producto registrado con multimedia -> SKU ID: {res.json().get('id')}"
        else:
            log_msg = f"[ERROR] Denegado por el microservicio de catálogo."
    except Exception as e:
        logger.error(f"[BFF MULTIPART CRITICAL EXCEPTION]: {str(e)}", exc_info=True)
        log_msg = f"[ERROR] Fallo crítico de transferencia en el flujo binario."
    return RedirectResponse(url=f"/proveedor?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/catalog/restock/{product_id}")
async def restock_product(request: Request, product_id: int, quantity: str = Form(...)):
    token = request.cookies.get("access_token_proveedor")
    datos = extraer_datos_de_jwt(token) if token else {}
    if datos.get("role") != "proveedor":
        return RedirectResponse(url="/proveedor?msg=[DENEGADO]", status_code=status.HTTP_303_SEE_OTHER)
    try:
        cantidad_unidades = int(quantity)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            res_get = await client.get(f"{ORDER_SERVICE_URL}/api/orders/catalog/products/{product_id}/", headers=headers, timeout=3.0)
            if res_get.status_code == 200:
                current_stock = int(res_get.json().get("stock", 0))
                new_payload = {"stock": current_stock + cantidad_unidades}
                res_patch = await client.patch(f"{ORDER_SERVICE_URL}/api/orders/catalog/products/{product_id}/", headers=headers, json=new_payload, timeout=4.0)
                if res_patch.status_code in [200, 202, 204]:
                    return RedirectResponse(url=f"/proveedor?msg={quote('[SUCCESS] Reabastecimiento propagado en la malla.')}", status_code=status.HTTP_303_SEE_OTHER)
                else:
                    logger.error(f"[BFF PATCH ERROR] Django rechazo con codigo: {res_patch.status_code}")
            else:
                logger.error(f"[BFF GET ERROR] No se encontro el producto ID {product_id}")
    except ValueError:
        logger.error("[BFF RESTOCK ERROR] La cantidad enviada no es un numero entero valido.")
    except Exception as e:
        logger.error(f"[BFF RESTOCK CRITICAL]: {str(e)}")
    return RedirectResponse(url=f"/proveedor?msg={quote('[ERROR] Error de comunicacion con la subred de inventario.')}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/catalog/delete/{product_id}")
async def delete_product(request: Request, product_id: int):
    token = request.cookies.get("access_token_proveedor")
    datos = extraer_datos_de_jwt(token) if token else {}
    if datos.get("role") != "proveedor":
        return RedirectResponse(url="/proveedor?msg=[DENEGADO]", status_code=status.HTTP_303_SEE_OTHER)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            res_del = await client.delete(f"{ORDER_SERVICE_URL}/api/orders/catalog/products/{product_id}/", headers=headers, timeout=4.0)
            if res_del.status_code in [200, 204]:
                return RedirectResponse(url=f"/proveedor?msg={quote('[SUCCESS] SKU revocado y eliminado de PostgreSQL.')}", status_code=status.HTTP_303_SEE_OTHER)
            else:
                logger.error(f"[BFF DELETE ERROR] Django rechazo con codigo: {res_del.status_code}")
    except Exception as e:
        logger.error(f"[BFF DELETE CRITICAL]: {str(e)}")
    return RedirectResponse(url=f"/proveedor?msg={quote('[ERROR] La purga del item fallo en el microservicio.')}", status_code=status.HTTP_303_SEE_OTHER)

# ==========================================
# SECCIÓN: COMPRADORES MUNDIALES
# ==========================================

@app.get("/comprador", response_class=HTMLResponse)
async def comprador_view(request: Request, msg: str = None):
    token = request.cookies.get("access_token_comprador")
    datos = extraer_datos_de_jwt(token) if token else {}
    mensaje_limpio = unquote(msg) if msg else None
    vista_actual = "dashboard" if datos.get("role") == "comprador" else "auth_requerida"
    productos_oferta = []
    productos_regulares = []
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{ORDER_SERVICE_URL}/api/orders/catalog/products/", timeout=3.0)
            if res.status_code == 200:
                catalogo_completo = res.json()
                productos_oferta = [p for p in catalogo_completo if p.get('is_offer') is True]
                productos_regulares = [p for p in catalogo_completo if p.get('is_offer') is not True]
    except Exception as e:
        logger.error(f"[BFF COMPRADOR] Error al traer catálogo público: {str(e)}")
        
    return templates.TemplateResponse("comprador.html", {
        "request": request,
        "vista": vista_actual,
        "productos_oferta": productos_oferta,
        "productos_regulares": productos_regulares,
        "logs": mensaje_limpio if mensaje_limpio else "[SISTEMA] Módulo comprador conectado a la malla de servicios.",
        "session": {"username": datos.get("sub"), "role": datos.get("role")}
    })

@app.post("/comprador/register")
async def comprador_register(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{AUTH_SERVICE_URL}/api/auth/register", 
                json={
                    "username": username, 
                    "email": email, 
                    "password": password, 
                    "role": "comprador"
                }, 
                timeout=5.0
            )
        if res.status_code == 201:
            log_msg = "[SUCCESS] Cuenta creada exitosamente. Proceda a iniciar sesión."
        else:
            error_detalle = res.json().get("error", "Campos duplicados o inválidos")
            log_msg = f"[ERROR] {error_detalle}"
    except Exception as e:
        logger.error(f"[BFF COMPRADOR] Excepción en registro: {str(e)}")
        log_msg = "[ERROR] El clúster de autenticación no responde."
    return RedirectResponse(url=f"/comprador?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/comprador/login")
async def comprador_login(username: str = Form(...), password: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(f"{AUTH_SERVICE_URL}/api/auth/login", json={"username": username, "password": password}, timeout=4.0)
        if res.status_code == 200:
            data = res.json()
            token = data.get("access_token")
            datos = extraer_datos_de_jwt(token)
            if datos.get("role") != "comprador":
                log_msg = "[ERROR] Acceso Denegado: Esta cuenta está registrada como Proveedor."
                return RedirectResponse(url=f"/comprador?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)
            response = RedirectResponse(url="/comprador", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(key="access_token_comprador", value=token, httponly=True, samesite="strict")
            return response
        else:
            log_msg = "[ERROR] Credenciales incorrectas para el Marketplace."
            return RedirectResponse(url=f"/comprador?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        return RedirectResponse(url=f"/comprador?msg={quote('[ERROR] Error de conexión con auth-service.')}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/comprador/checkout")
async def bff_comprador_checkout(request: Request):
    token = request.cookies.get("access_token_comprador")
    datos = extraer_datos_de_jwt(token) if token else {}
    if not token or datos.get("role") != "comprador":
        return Response(content='{"error": "Autenticación inválida o sesión expirada corporativa."}', status_code=401, media_type="application/json")
    try:
        body = await request.json()
        items_recibidos = body.get("items", [])
        user_id = datos.get("sub", 999)
        payload = {"email": f"user_{user_id}@alimarket.corporate", "items": items_recibidos}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            res = await client.post(f"{ORDER_SERVICE_URL}/api/orders/checkout/", headers=headers, json=payload, timeout=5.0)
        return Response(content=res.text, status_code=res.status_code, media_type="application/json")
    except Exception as e:
        logger.error(f"[BFF CHECKOUT CRITICAL]: {str(e)}")
        return Response(content='{"error": "Fallo crítico en la malla de servicios de la pasarela."}', status_code=500, media_type="application/json")

@app.get("/comprador/logout")
async def comprador_logout():
    log_msg = "[SISTEMA] Sesión del Comprador destruida correctamente del Marketplace."
    response = RedirectResponse(url=f"/comprador?msg={quote(log_msg)}", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token_comprador")
    return response

@app.get("/api/products/live")
async def live_catalog():
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{ORDER_SERVICE_URL}/api/orders/catalog/products/", timeout=2.0)
            if res.status_code == 200:
                return res.json()
    except Exception as e:
        logger.error(f"[BFF LIVE CATALOG ERROR]: {str(e)}")
    return []