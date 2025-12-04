# funciones/comandos.py - VERSIÓN COMPATIBLE CON RENDER
import os
import sys
from datetime import datetime
import urllib.parse
from typing import Optional
from sqlalchemy.orm import Session

# ====== DETECCIÓN DE ENTORNO ======
IS_RENDER = os.getenv('RENDER', 'false').lower() == 'true'

# ====== IMPORT CONDICIONAL DE LIBRERÍAS QUE REQUIEREN GUI ======
GUI_AVAILABLE = False
pyttsx3 = None
pywhatkit = None
wikipedia = None

try:
    # pyttsx3 puede funcionar en Render (sin sonido)
    import pyttsx3
    GUI_AVAILABLE = True
except ImportError:
    print("⚠️  pyttsx3 no disponible")
except Exception as e:
    print(f"⚠️  Error cargando pyttsx3: {e}")

try:
    # pywhatkit solo en local
    if not IS_RENDER:
        import pywhatkit
        GUI_AVAILABLE = GUI_AVAILABLE or True
    else:
        print("⚠️  Modo Render: pywhatkit desactivado")
except ImportError:
    print("⚠️  pywhatkit no instalado")
except Exception as e:
    print(f"⚠️  Error cargando pywhatkit: {e}")

try:
    # wikipedia funciona en cualquier entorno
    import wikipedia
    wikipedia.set_lang("es")
except ImportError:
    print("⚠️  wikipedia no instalado")
except Exception as e:
    print(f"⚠️  Error cargando wikipedia: {e}")

# ====== IMPORT DE MÓDULOS PROPIOS ======
try:
    from funciones.navegador import abrir_en_navegador
except ImportError:
    print("⚠️  funciones.navegador no disponible")
    # Función dummy como respaldo
    def abrir_en_navegador(url: str):
        print(f"[Simulación] Abriendo navegador: {url}")
        return f"URL para abrir: {url}"

from db.models import get_db
from servicios.historial_service import HistorialService

def hablaBOT(texto: str):
    """El asistente responde con voz (si está disponible)."""
    try:
        if pyttsx3 and not IS_RENDER:
            habla = pyttsx3.init()
            voces = habla.getProperty("voices")
            if voces:
                habla.setProperty("voice", voces[0].id)
            habla.say(texto)
            habla.runAndWait()
            print(f"[Voz] {texto}")
        else:
            # En Render, solo imprimir el texto
            print(f"[Texto] {texto}")
    except Exception as e:
        print(f"⚠️  Error en hablaBOT: {e}")
        print(f"[Texto alternativo] {texto}")

def ejecutar_comando(texto: str, db: Optional[Session] = None, usuario_id: Optional[int] = None) -> str:
    """Ejecuta el comando y registra en el historial"""
    texto_original = texto
    texto = texto.lower()
    respuesta = ""
    
    print(f"[Comando] Usuario {usuario_id}: {texto}")
    
    try:
        # 1. Comando: REPRODUCE (YouTube)
        if "reproduce" in texto:
            musica = texto.replace("reproduce", "").strip()
            respuesta = f"Reproduciendo {musica}"
            
            if pywhatkit and not IS_RENDER and GUI_AVAILABLE:
                hablaBOT(respuesta)
                pywhatkit.playonyt(musica)
            else:
                respuesta += " (modo web - abre manualmente YouTube)"
                hablaBOT(respuesta)
                query = urllib.parse.quote(musica)
                url = f"https://www.youtube.com/results?search_query={query}"
                abrir_en_navegador(url)
            
        # 2. Comando: BUSCA EN YOUTUBE
        elif "busca en y" in texto or "busca en youtube" in texto:
            if "busca en y" in texto:
                musica = texto.replace("busca en y", "").strip()
            else:
                musica = texto.replace("busca en youtube", "").strip()
                
            respuesta = f"Buscando en YouTube: {musica}"
            hablaBOT(respuesta)
            
            query = urllib.parse.quote(musica)
            url = f"https://www.youtube.com/results?search_query={query}"
            resultado = abrir_en_navegador(url)
            
            if "Simulación" in str(resultado):
                respuesta += f" | URL: {url}"
            else:
                respuesta += ". Resultados abiertos en navegador."
            
        # 3. Comando: HORA
        elif "hora" in texto:
            hora = datetime.now().strftime("%H:%M %p")
            respuesta = f"La hora actual es: {hora}"
            hablaBOT(respuesta)
            
        # 4. Comando: BUSCA EN GOOGLE
        elif "busca en" in texto and "youtube" not in texto:
            consulta = texto.replace("busca en", "").replace("google", "").strip()
            respuesta = f"Buscando en Google: {consulta}"
            hablaBOT(respuesta)
            
            query = urllib.parse.quote(consulta)
            url = f"https://www.google.com/search?q={query}"
            resultado = abrir_en_navegador(url)
            
            if "Simulación" in str(resultado):
                respuesta += f" | URL: {url}"
            else:
                hablaBOT("Aquí tienes los resultados en tu navegador.")
                respuesta += ". Resultados abiertos en navegador."
                
        # 5. Comando: DIME (Wikipedia)
        elif "dime" in texto:
            consulta = texto.replace("dime", "").strip()
            respuesta = f"Buscando información sobre: {consulta}"
            hablaBOT(respuesta)
            
            if wikipedia:
                try:
                    resumen = wikipedia.summary(consulta, sentences=2)
                    respuesta_final = f"Según Wikipedia: {resumen}"
                    hablaBOT(respuesta_final)
                    respuesta = respuesta_final
                except wikipedia.exceptions.DisambiguationError as e:
                    respuesta_final = f"Hay varios resultados para '{consulta}'. Opciones: {', '.join(e.options[:3])}"
                    hablaBOT(respuesta_final)
                    respuesta = respuesta_final
                except wikipedia.exceptions.PageError:
                    respuesta_final = f"No encontré información sobre '{consulta}' en Wikipedia."
                    hablaBOT(respuesta_final)
                    respuesta = respuesta_final
                except Exception as e:
                    respuesta_final = f"Error en Wikipedia: {str(e)}"
                    hablaBOT(respuesta_final)
                    respuesta = respuesta_final
            else:
                respuesta_final = f"Wikipedia no disponible. Busca '{consulta}' en Google."
                hablaBOT(respuesta_final)
                respuesta = respuesta_final
                query = urllib.parse.quote(consulta)
                url = f"https://www.google.com/search?q={query}"
                abrir_en_navegador(url)
                
        # 6. Comando: AYUDA
        elif "ayuda" in texto or "qué puedes hacer" in texto:
            respuesta = "📋 Puedo ayudarte con:\n"
            respuesta += "• Reproducir música en YouTube\n"
            respuesta += "• Buscar en YouTube\n"
            respuesta += "• Decir la hora actual\n"
            respuesta += "• Buscar en Google\n"
            respuesta += "• Buscar información en Wikipedia\n"
            respuesta += "• Abrir páginas web\n"
            
            if IS_RENDER:
                respuesta += "\n⚠️  Modo web: algunas funciones se simularán\n"
            
            hablaBOT("Te muestro lo que puedo hacer en pantalla.")
            
        # 7. Comando no reconocido
        else:
            respuesta = f"No entendí: '{texto}'. ¿Puedes reformular? Di 'ayuda' para ver opciones."
            hablaBOT(respuesta)
            
        # Registrar en el historial si tenemos db
        if db is not None and usuario_id is not None:
            comando_ejecutado = determinar_comando_ejecutado(texto)
            try:
                HistorialService.crear_registro(
                    db=db, 
                    comando_usuario=texto_original, 
                    comando_ejecutado=comando_ejecutado, 
                    respuesta_asistente=respuesta,
                    usuario_id=usuario_id
                )
                print(f"✅ Historial guardado para usuario {usuario_id}")
            except Exception as e:
                print(f"⚠️  Error guardando historial: {e}")
        
    except Exception as e:
        respuesta = f"❌ Error ejecutando comando: {str(e)}"
        print(f"❌ Error en ejecutar_comando: {e}")
        hablaBOT("Lo siento, hubo un error al procesar tu comando.")
        
    return respuesta

def determinar_comando_ejecutado(texto: str) -> str:
    """Determinar qué tipo de comando se ejecutó"""
    texto = texto.lower()
    if "reproduce" in texto:
        return "reproduce_musica"
    elif "busca en y" in texto or "busca en youtube" in texto:
        return "busca_youtube"
    elif "hora" in texto:
        return "consulta_hora"
    elif "busca en" in texto and "youtube" not in texto:
        return "busca_google"
    elif "dime" in texto:
        return "busca_wikipedia"
    elif "ayuda" in texto:
        return "mostrar_ayuda"
    else:
        return "comando_no_reconocido"
