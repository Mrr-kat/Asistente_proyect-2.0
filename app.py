import os
import pvporcupine
"""import pyaudio"""
import struct
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



# ====== CONFIGURACIÓN PARA RENDER ======
import os
import sys
import platform

try:
    import pyaudio
except ImportError:
    pyaudio = None
    print("PyAudio no disponible - continuando sin audio")

# app.py - MODIFICA EL INICIO

# Desactivar PyAudio en Render
SKIP_PYAUDIO = os.getenv('SKIP_PYAUDIO', 'true').lower() == 'true'

# IMPORTAR PyAudio solo si NO estamos en Render
pyaudio = None
pvporcupine = None

if not SKIP_PYAUDIO:
    try:
        import pyaudio
        import pvporcupine
        print("PyAudio y Porcupine cargados (modo desarrollo)")
    except ImportError:
        print("PyAudio no disponible - modo web solo")
else:
    print("Modo Render: PyAudio desactivado")

# Detectar si estamos en Render
IS_RENDER = os.getenv('RENDER', 'false').lower() == 'true' or 'render' in os.getenv('HOSTNAME', '')

def setup_audio_for_render():
    """Configurar audio para entorno Render"""
    print(f"Sistema operativo: {platform.system()}")
    print(f"En Render: {IS_RENDER}")
    
    try:
        if IS_RENDER:
            print("Usando sounddevice como alternativa a PyAudio en Render...")
            import sounddevice as sd
            print(f"SoundDevice disponible. Dispositivos: {len(sd.query_devices())}")
            return "sounddevice"
        else:
            # En desarrollo local, intentar PyAudio
            import pyaudio
            pa = pyaudio.PyAudio()
            print(f"PyAudio disponible en desarrollo. Dispositivos: {pa.get_device_count()}")
            return "pyaudio"
    except ImportError as e:
        print(f"Backend de audio no disponible: {e}")
        return None
    except Exception as e:
        print(f"Error configurando audio: {e}")
        return None

# Inicializar backend de audio
AUDIO_BACKEND = setup_audio_for_render()

# ====== CONFIGURACIÓN DE PORCUPINE (MODIFICADA) ======
def setup_porcupine():
    """Configurar Porcupine según backend disponible"""
    try:
        access_key = "jvi0VvjYVgQMIa+C6UMiC7avc6uWoWPP2guR6F6QQyceIU5bT/s7fQ=="
        
        if AUDIO_BACKEND == "sounddevice":
            # Configuración para sounddevice
            import sounddevice as sd
            import numpy as np
            
            print("Porcupine configurado con sounddevice")
            
            class SoundDeviceStream:
                def __init__(self, sample_rate=16000, frame_length=512):
                    self.sample_rate = sample_rate
                    self.frame_length = frame_length
                    self.stream = sd.InputStream(
                        samplerate=sample_rate,
                        channels=1,
                        dtype='int16',
                        blocksize=frame_length
                    )
                    self.stream.start()
                
                def read(self, frame_length, exception_on_overflow=False):
                    data, _ = self.stream.read(frame_length)
                    return data.flatten().tobytes()
                
                def close(self):
                    self.stream.stop()
                    self.stream.close()
            
            porcupine = pvporcupine.create(access_key=access_key, keywords=["alexa"])
            audio_stream = SoundDeviceStream(
                sample_rate=porcupine.sample_rate,
                frame_length=porcupine.frame_length
            )
            return porcupine, audio_stream
            
        elif AUDIO_BACKEND == "pyaudio":
            # Configuración original con PyAudio
            import pyaudio
            import pvporcupine
            import struct
            
            porcupine = pvporcupine.create(access_key=access_key, keywords=["alexa"])
            pa = pyaudio.PyAudio()
            audio_stream = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length
            )
            return porcupine, audio_stream
            
        else:
            print("⚠️  Backend de audio no disponible. Desactivando reconocimiento por voz.")
            return None, None
            
    except Exception as e:
        print(f"Error configurando Porcupine: {e}")
        return None, None

# Inicializar Porcupine
porcupine, audio_stream = setup_porcupine()




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
        "usuario": usuario.usuario if usuario else "Invitado"
    })

# Redirigir la raíz al asistente si está autenticado, o al login si no
@app.get("/")
async def raiz(request: Request):
    """Redirigir a la página apropiada"""
    usuario_id = request.cookies.get("usuario_id")
    
    if usuario_id:
        # Usuario autenticado, redirigir al asistente
        return RedirectResponse(url="/asistente", status_code=status.HTTP_303_SEE_OTHER)
    else:
        # No autenticado, redirigir al login
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

# Rutas de autenticación
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
        
        # Crear respuesta con redirección y cookie
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="usuario_id",
            value=str(usuario_db.id),
            httponly=True,
            max_age=86400  # 24 horas
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
        # Validar que las contraseñas coincidan
        if contraseña != confirmar_contraseña:
            return templates.TemplateResponse("login/registro.html", {
                "request": request,
                "error": "Las contraseñas no coinciden"
            })
        
        # Validar longitud mínima de contraseña
        if len(contraseña) < 6:
            return templates.TemplateResponse("login/registro.html", {
                "request": request,
                "error": "La contraseña debe tener al menos 6 caracteres"
            })
        
        # Registrar usuario
        usuario_db = AuthService.registrar_usuario(db, nombre_completo, usuario, correo, contraseña)
        
        # Iniciar sesión automáticamente después del registro
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
        
        # Redirigir al paso 2
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
    db: Session = Depends(get_db)
):
    """Verificar código de recuperación (NO marcar como usado aún)"""
    try:
        # Validar sin marcar como usado
        usuario_id = AuthService.validar_codigo_recuperacion(db, usuario_correo, codigo, marcar_como_utilizado=False)
        
        # Redirigir al paso 3
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

@app.post("/recuperacion/verificar")
async def verificar_codigo_recuperacion(
    request: Request,
    usuario_correo: str = Form(...),
    codigo: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        usuario_id = AuthService.validar_codigo_recuperacion(db, usuario_correo, codigo)
        
        # Redirigir al paso 3
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
    """Cambiar contraseña después de verificación"""
    try:
        # Validar que las contraseñas coincidan
        if nueva_contraseña != confirmar_nueva_contraseña:
            return templates.TemplateResponse("login/recuperacion.html", {
                "request": request,
                "error": "Las contraseñas no coinciden",
                "usuario": usuario_correo,
                "codigo": codigo,
                "step": 3
            })
        
        # Validar longitud mínima
        if len(nueva_contraseña) < 6:
            return templates.TemplateResponse("login/recuperacion.html", {
                "request": request,
                "error": "La contraseña debe tener al menos 6 caracteres",
                "usuario": usuario_correo,
                "codigo": codigo,
                "step": 3
            })
        
        # Validar el código sin marcarlo como usado
        usuario_id = AuthService.validar_codigo_recuperacion(db, usuario_correo, codigo, marcar_como_utilizado=False)
        
        # Cambiar contraseña y marcar código como usado
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

# Ruta para procesar audio (actualizada para usar usuario_id)
@app.post("/audio")
async def audio(audio: UploadFile, request: Request, db: Session = Depends(get_db)):
    try:
        if not audio:
            return JSONResponse({"error": "No se envió ningún archivo de audio."}, status_code=400)

        usuario_id = request.state.usuario_id
        
        webm_path = os.path.join("static", "temp", "audio.webm")
        wav_path = os.path.join("static", "temp", "audio.wav")

        # Guardar archivo
        with open(webm_path, "wb") as f:
            f.write(await audio.read())

        # Convertir de webm a wav
        try:
            audio_segment = AudioSegment.from_file(webm_path, format="webm")
            audio_segment.export(wav_path, format="wav")
        except Exception as e:
            return JSONResponse({"error": f"Error al convertir el audio: {str(e)}"}, status_code=500)

        # Transcribir
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        # Limpiar temporales
        os.remove(webm_path)
        os.remove(wav_path)
        text = recognizer.recognize_google(audio_data, language="es-ES")
        
        # Ejecutar comando en un thread separado, pero necesitamos crear nueva sesión
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

# Rutas para el historial (actualizadas para usar usuario_id)
@app.get("/historial")
async def obtener_historial(
    request: Request,
    db: Session = Depends(get_db), 
    buscar: str = None
):
    """Obtener todo el historial o buscar por texto"""
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
    """Actualizar un registro del historial"""
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
    """Eliminar un registro (eliminación lógica)"""
    usuario_id = request.state.usuario_id
    if HistorialService.eliminar_registro(db, registro_id, usuario_id):
        return {"mensaje": "Registro eliminado"}
    return {"error": "Registro no encontrado"}

@app.post("/historial/reportes/pdf")
async def generar_reporte_pdf(request: Request, db: Session = Depends(get_db)):
    """Generar reporte en formato PDF"""
    usuario_id = request.state.usuario_id
    usuario = AuthService.obtener_usuario_por_id(db, usuario_id)
    
    ruta_archivo = os.path.join("static", "reportes", f"historial_{usuario.usuario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
    
    archivo_generado = HistorialService.generar_reporte_pdf(db, ruta_archivo, usuario_id)
    
    return {"mensaje": "Reporte PDF generado", "archivo": archivo_generado}


#///////////////////

app_mount = socketio.ASGIApp(sio, app)
"""
# Configuración de Porcupine
access_key = "jvi0VvjYVgQMIa+C6UMiC7avc6uWoWPP2guR6F6QQyceIU5bT/s7fQ=="
porcupine = pvporcupine.create(access_key=access_key, keywords=["alexa"])

# Configuración de PyAudio
pa = pyaudio.PyAudio()
audio_stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)
"""
grabando = False
detener = False

# Función para iniciar grabación
async def iniciar_grabacion():
    global grabando
    print("Iniciando grabación...")
    grabando = True
    await sio.emit("iniciar_grabacion", {"message": "Grabación iniciada"})

# Evento de detener grabación desde cliente
@sio.on("detener_grabacion")
async def detener_grabacion(sid, data=None):
    global grabando
    print("Grabación detenida owo.")
    grabando = False
    await sio.emit("detener_grabacion", {"message": "Grabación detenida por silencio"})

# Escucha pasiva de palabra clave
def escucha_pasiva():
    """Escucha pasiva - desactivada en Render"""
    global grabando, detener
    
    if porcupine is None or audio_stream is None:
        print("⚠️  Reconocimiento por voz desactivado en Render")
        print("✅ Modo web funcionando correctamente")
        return  # Salir temprano
    
    try:
        while not detener:
            if AUDIO_BACKEND == "sounddevice":
                # Leer audio con sounddevice
                import numpy as np
                pcm = audio_stream.read(porcupine.frame_length)
                pcm_array = np.frombuffer(pcm, dtype=np.int16)
                result = porcupine.process(pcm_array)
                
            elif AUDIO_BACKEND == "pyaudio":
                # Leer audio con PyAudio
                pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
                result = porcupine.process(pcm)
            else:
                # Sin audio, salir del loop
                break
            
            if result >= 0 and not grabando:
                print("¡Palabra clave detectada!")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(iniciar_grabacion())
                
    except KeyboardInterrupt:
        print("\nInterrumpido manualmente.")
    except Exception as e:
        print(f"Error en escucha pasiva: {e}")
    finally:
        liberar_recursos()

# Liberar recursos
def liberar_recursos():
    global detener
    detener = True
    audio_stream.stop_stream()
    audio_stream.close()
    pa.terminate()
    porcupine.delete()
    print("Recursos liberados. Saliendo del programa...")

# Main
# app.py (antes M.0.1.py)
# Cambia esta línea al FINAL del archivo:
if __name__ == "__main__":
    threading.Thread(target=escucha_pasiva, daemon=True).start()
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app_mount, host="0.0.0.0", port=port)
