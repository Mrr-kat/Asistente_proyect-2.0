import os
import sys
import platform
import threading
import asyncio
from fastapi import FastAPI, Request, UploadFile, Depends, Form, HTTPException, status, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import socketio
from pydub import AudioSegment
import speech_recognition as sr
from sqlalchemy.orm import Session
from datetime import datetime
from db.models import get_db, HistorialInteraccion, Usuario
from servicios.historial_service import HistorialService
from servicios.auth_service import AuthService
from funciones.comandos import ejecutar_comando


# Al inicio de app.py (después de los imports)
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv("key/key.env")  # Ruta relativa

# Verificar que las variables estén cargadas
if not os.getenv("CORREO_USU") or not os.getenv("CORREO_CON"):
    print("⚠️  Advertencia: Variables de correo no configuradas")
    print("   Usa: CORREO_USU=tu_email@gmail.com")
    print("   Usa: CORREO_CON=contraseña_app_16_caracteres")
else:
    print("✅ Variables de correo configuradas")


# ====== DETECCIÓN DE ENTORNO ======
IS_RENDER = os.getenv('RENDER', 'false').lower() == 'true'

print("=" * 50)
print(f"Sistema: {platform.system()}")
print(f"Python: {sys.version}")
print(f"En Render: {IS_RENDER}")
print("=" * 50)

# Configuración de FastAPI
app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Montar carpeta de templates y estáticos
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Middleware para verificar autenticación
@app.middleware("http")
async def verificar_autenticacion(request: Request, call_next):
    # Rutas públicas que no requieren autenticación
    rutas_publicas = ["/login", "/registro", "/recuperacion", "/static", "/favicon.ico"]
    
    if any(request.url.path.startswith(ruta) for ruta in rutas_publicas):
        return await call_next(request)
    
    # Verificar si el usuario está autenticado
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        # Verificar que el usuario existe
        db = next(get_db())
        usuario = AuthService.obtener_usuario_por_id(db, int(usuario_id))
        if not usuario:
            response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
            response.delete_cookie("usuario_id")
            return response
    except:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("usuario_id")
        return response
    
    # Agregar usuario_id al estado de la solicitud
    request.state.usuario_id = int(usuario_id)
    return await call_next(request)

# Página principal (requiere autenticación)
@app.get("/asistente", response_class=HTMLResponse)
async def asistente(request: Request, db: Session = Depends(get_db)):
    """Página principal del asistente virtual"""
    usuario_id = request.state.usuario_id
    usuario = AuthService.obtener_usuario_por_id(db, usuario_id)
    
    return templates.TemplateResponse("./Asistente/M.0.1.html", {
        "request": request,
        "usuario": usuario.usuario if usuario else "Invitado",
        "modo_render": IS_RENDER
    })

# Redirigir la raíz al asistente si está autenticado, o al login si no
@app.get("/")
async def raiz(request: Request):
    """Redirigir a la página apropiada"""
    usuario_id = request.cookies.get("usuario_id")
    
    if usuario_id:
        return RedirectResponse(url="/asistente", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

# Rutas de autenticación (se mantienen igual que antes)
@app.get("/login", response_class=HTMLResponse)
async def mostrar_login(request: Request, error: str = None, success: str = None):
    return templates.TemplateResponse("login/inicio_sesion.html", {
        "request": request,
        "error": error,
        "success": success
    })

@app.post("/login")
async def iniciar_sesion(
    request: Request,
    usuario: str = Form(...),
    contraseña: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        usuario_db = AuthService.autenticar_usuario(db, usuario, contraseña)
        
        if not usuario_db:
            return templates.TemplateResponse("login/inicio_sesion.html", {
                "request": request,
                "error": "Usuario o contraseña incorrectos"
            })
        
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="usuario_id",
            value=str(usuario_db.id),
            httponly=True,
            max_age=86400
        )
        return response
        
    except Exception as e:
        return templates.TemplateResponse("login/inicio_sesion.html", {
            "request": request,
            "error": f"Error al iniciar sesión: {str(e)}"
        })

@app.get("/registro", response_class=HTMLResponse)
async def mostrar_registro(request: Request, error: str = None, success: str = None):
    return templates.TemplateResponse("login/registro.html", {
        "request": request,
        "error": error,
        "success": success
    })

@app.post("/registro")
async def registrar_usuario(
    request: Request,
    nombre_completo: str = Form(...),
    usuario: str = Form(...),
    correo: str = Form(...),
    contraseña: str = Form(...),
    confirmar_contraseña: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        if contraseña != confirmar_contraseña:
            return templates.TemplateResponse("login/registro.html", {
                "request": request,
                "error": "Las contraseñas no coinciden"
            })
        
        if len(contraseña) < 6:
            return templates.TemplateResponse("login/registro.html", {
                "request": request,
                "error": "La contraseña debe tener al menos 6 caracteres"
            })
        
        usuario_db = AuthService.registrar_usuario(db, nombre_completo, usuario, correo, contraseña)
        
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="usuario_id",
            value=str(usuario_db.id),
            httponly=True,
            max_age=86400
        )
        return response
        
    except ValueError as e:
        return templates.TemplateResponse("login/registro.html", {
            "request": request,
            "error": str(e)
        })
    except Exception as e:
        return templates.TemplateResponse("login/registro.html", {
            "request": request,
            "error": f"Error al registrar usuario: {str(e)}"
        })

@app.get("/recuperacion", response_class=HTMLResponse)
async def mostrar_recuperacion(
    request: Request, 
    error: str = None, 
    success: str = None, 
    info: str = None,
    usuario: str = None,
    step: int = 1
):
    return templates.TemplateResponse("login/recuperacion.html", {
        "request": request,
        "error": error,
        "success": success,
        "info": info,
        "usuario": usuario,
        "step": step
    })

@app.post("/recuperacion/solicitar")
async def solicitar_recuperacion(
    request: Request,
    usuario_correo: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        resultado = AuthService.generar_codigo_recuperacion(db, usuario_correo)
        
        return RedirectResponse(
            url=f"/recuperacion?usuario={usuario_correo}&step=2&info=Código enviado a {resultado['correo']}",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except ValueError as e:
        return templates.TemplateResponse("login/recuperacion.html", {
            "request": request,
            "error": str(e)
        })
    except Exception as e:
        return templates.TemplateResponse("login/recuperacion.html", {
            "request": request,
            "error": f"Error al solicitar recuperación: {str(e)}"
        })

@app.post("/recuperacion/verificar")
async def verificar_codigo_recuperacion(
    request: Request,
    usuario_correo: str = Form(...),
    codigo: str = Form(...),
    marcar_como_utilizado: bool = Form(False),
    db: Session = Depends(get_db)
):
    try:
        usuario_id = AuthService.validar_codigo_recuperacion(
            db, usuario_correo, codigo, marcar_como_utilizado=marcar_como_utilizado
        )
        
        return RedirectResponse(
            url=f"/recuperacion?usuario={usuario_correo}&codigo={codigo}&step=3",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except ValueError as e:
        return templates.TemplateResponse("login/recuperacion.html", {
            "request": request,
            "error": str(e),
            "usuario": usuario_correo,
            "step": 2
        })
    except Exception as e:
        return templates.TemplateResponse("login/recuperacion.html", {
            "request": request,
            "error": f"Error al verificar código: {str(e)}",
            "usuario": usuario_correo,
            "step": 2
        })

@app.post("/recuperacion/cambiar")
async def cambiar_contraseña_recuperacion(
    request: Request,
    usuario_correo: str = Form(...),
    codigo: str = Form(...),
    nueva_contraseña: str = Form(...),
    confirmar_nueva_contraseña: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        if nueva_contraseña != confirmar_nueva_contraseña:
            return templates.TemplateResponse("login/recuperacion.html", {
                "request": request,
                "error": "Las contraseñas no coinciden",
                "usuario": usuario_correo,
                "codigo": codigo,
                "step": 3
            })
        
        if len(nueva_contraseña) < 6:
            return templates.TemplateResponse("login/recuperacion.html", {
                "request": request,
                "error": "La contraseña debe tener al menos 6 caracteres",
                "usuario": usuario_correo,
                "codigo": codigo,
                "step": 3
            })
        
        usuario_id = AuthService.validar_codigo_recuperacion(
            db, usuario_correo, codigo, marcar_como_utilizado=False
        )
        
        AuthService.cambiar_contraseña(db, usuario_id, nueva_contraseña, codigo)
        
        return RedirectResponse(
            url="/login?success=Contraseña cambiada exitosamente. Ahora puedes iniciar sesión.",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except ValueError as e:
        return templates.TemplateResponse("login/recuperacion.html", {
            "request": request,
            "error": str(e),
            "usuario": usuario_correo,
            "codigo": codigo,
            "step": 3
        })
    except Exception as e:
        return templates.TemplateResponse("login/recuperacion.html", {
            "request": request,
            "error": f"Error al cambiar contraseña: {str(e)}",
            "usuario": usuario_correo,
            "codigo": codigo,
            "step": 3
        })

@app.get("/logout")
async def cerrar_sesion():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("usuario_id")
    return response

# Ruta para procesar audio - SIN PyAudio, solo grabación web
@app.post("/audio")
async def audio(audio: UploadFile, request: Request, db: Session = Depends(get_db)):
    try:
        if not audio:
            return JSONResponse({"error": "No se envió ningún archivo de audio."}, status_code=400)

        usuario_id = request.state.usuario_id
        
        webm_path = os.path.join("static", "temp", "audio.webm")
        wav_path = os.path.join("static", "temp", "audio.wav")

        # Crear directorio temporal si no existe
        os.makedirs(os.path.dirname(webm_path), exist_ok=True)
        
        # Guardar archivo
        with open(webm_path, "wb") as f:
            f.write(await audio.read())

        # Convertir de webm a wav
        try:
            audio_segment = AudioSegment.from_file(webm_path, format="webm")
            audio_segment.export(wav_path, format="wav")
        except Exception as e:
            return JSONResponse({"error": f"Error al convertir el audio: {str(e)}"}, status_code=500)

        # Transcribir usando SpeechRecognition (no requiere PyAudio)
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        # Limpiar temporales
        try:
            os.remove(webm_path)
            os.remove(wav_path)
        except:
            pass
            
        text = recognizer.recognize_google(audio_data, language="es-ES")
        
        # Ejecutar comando
        def ejecutar_comando_con_db():
            from db.models import get_db
            from funciones.comandos import ejecutar_comando
            db_local = next(get_db())
            try:
                ejecutar_comando(text, db_local, usuario_id)
            except Exception as e:
                print(f"Error ejecutando comando en thread: {e}")
            finally:
                db_local.close()
        
        threading.Thread(target=ejecutar_comando_con_db).start()

        return JSONResponse({"text": text}, status_code=200)

    except sr.UnknownValueError:
        return JSONResponse({"error": "No se pudo entender el audio."}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# Rutas para el historial
@app.get("/historial")
async def obtener_historial(
    request: Request,
    db: Session = Depends(get_db), 
    buscar: str = None
):
    usuario_id = request.state.usuario_id
    
    if buscar:
        registros = HistorialService.buscar_por_texto(db, buscar, usuario_id)
    else:
        registros = HistorialService.obtener_todos(db, usuario_id)
    
    return {"registros": [r.to_dict() for r in registros]}

@app.put("/historial/{registro_id}")
async def actualizar_registro(
    registro_id: int, 
    datos: dict, 
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_id = request.state.usuario_id
    registro = HistorialService.actualizar_registro(
        db, registro_id, 
        datos.get("comando_usuario"), 
        datos.get("respuesta_asistente"),
        usuario_id
    )
    if registro:
        return {"mensaje": "Registro actualizado", "registro": registro.to_dict()}
    return {"error": "Registro no encontrado"}

@app.delete("/historial/{registro_id}")
async def eliminar_registro(
    registro_id: int, 
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_id = request.state.usuario_id
    if HistorialService.eliminar_registro(db, registro_id, usuario_id):
        return {"mensaje": "Registro eliminado"}
    return {"error": "Registro no encontrado"}

@app.post("/historial/reportes/pdf")
async def generar_reporte_pdf(request: Request, db: Session = Depends(get_db)):
    usuario_id = request.state.usuario_id
    usuario = AuthService.obtener_usuario_por_id(db, usuario_id)
    
    ruta_archivo = os.path.join("static", "reportes", f"historial_{usuario.usuario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
    
    archivo_generado = HistorialService.generar_reporte_pdf(db, ruta_archivo, usuario_id)
    
    return {"mensaje": "Reporte PDF generado", "archivo": archivo_generado}

# SocketIO app mount
app_mount = socketio.ASGIApp(sio, app)

# Eventos de SocketIO (solo para grabación web)
@sio.on("iniciar_grabacion_web")
async def iniciar_grabacion_web(sid, data=None):
    print("Grabación web iniciada desde cliente")
    await sio.emit("grabacion_iniciada", {"message": "Listo para grabar"})

@sio.on("detener_grabacion")
async def detener_grabacion_web(sid, data=None):
    print("Grabación web detenida")
    await sio.emit("grabacion_detenida", {"message": "Grabación detenida"})

# Información del sistema
@app.get("/info")
async def info_sistema():
    return {
        "sistema": platform.system(),
        "python_version": sys.version,
        "en_render": IS_RENDER,
        "modo_audio": "solo_web"
    }

# Main
if __name__ == "__main__":
    print("🚀 Iniciando aplicación en modo web...")
    print("✅ Reconocimiento por voz disponible solo a través de grabación web")
    print("❌ Escucha pasiva desactivada (no compatible con Render)")
    
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app_mount, host="0.0.0.0", port=port)
