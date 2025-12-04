# funciones/comandos.py
import pyttsx3
import pywhatkit
from datetime import datetime
from googlesearch import search
from funciones.navegador import abrir_en_navegador
import urllib
import wikipedia
from db.models import get_db
from servicios.historial_service import HistorialService
from typing import Optional
from sqlalchemy.orm import Session

wikipedia.set_lang("es")

def hablaBOT(texto: str):
    """El asistente responde con voz."""
    try:
        habla = pyttsx3.init()
        voces = habla.getProperty("voices")
        habla.setProperty("voice", voces[0].id)
        habla.say(texto)
        habla.runAndWait()
    except Exception as e:
        print(f"Error en hablaBOT: {e}")

def ejecutar_comando(texto: str, db: Optional[Session] = None, usuario_id: Optional[int] = None) -> str:
    """Ejecuta el comando y registra en el historial si se proporciona db y usuario_id"""
    texto = texto.lower()
    respuesta = ""
    
    try:
        if "reproduce" in texto:
            musica = texto.replace("reproduce", "").strip()
            respuesta = f"Reproduciendo {musica}"
            hablaBOT(respuesta)
            pywhatkit.playonyt(musica)
            
        elif "busca en y" in texto or "busca en youtube" in texto:
            if "busca en y" in texto:
                musica = texto.replace("busca en y", "").strip()
            else:
                musica = texto.replace("busca en youtube", "").strip()
            respuesta = f"buscando en youtube {musica}"
            hablaBOT(respuesta)
            query = urllib.parse.quote(musica)
            url = f"https://www.youtube.com/results?search_query={query}"
            abrir_en_navegador(url)

        elif "hora" in texto:
            hora = datetime.now().strftime("%H:%M %p")
            respuesta = f"La hora actual es: {hora}"
            hablaBOT(respuesta)

        elif "busca en" in texto and "youtube" not in texto:
            consulta = texto.replace("busca en", "").replace("google", "").strip()
            respuesta = f"Buscando {consulta} en Google"
            hablaBOT(respuesta)
            query = urllib.parse.quote(consulta)
            url = f"https://www.google.com/search?q={query}"
            abrir_en_navegador(url)
            hablaBOT("Aquí tienes los resultados en tu navegador.")
            respuesta = f"{respuesta}. Resultados abiertos en el navegador."

        elif "dime" in texto:
            consulta = texto.replace("dime", "").strip()
            respuesta = f"Buscando {consulta}"
            hablaBOT(respuesta)
            try:
                resumen = wikipedia.summary(consulta, sentences=2)
                respuesta_final = f"Según Wikipedia, {resumen}"
                hablaBOT(respuesta_final)
                respuesta = respuesta_final
            except wikipedia.exceptions.DisambiguationError as e:
                respuesta_final = f"Hay varios resultados posibles para {consulta}. Por ejemplo: {', '.join(e.options[:3])}"
                hablaBOT(respuesta_final)
                respuesta = respuesta_final
            except wikipedia.exceptions.PageError:
                respuesta_final = f"No encontré resultados para {consulta}."
                hablaBOT(respuesta_final)
                respuesta = respuesta_final
            except Exception as e:
                error_texto = f"Ocurrió un error: {str(e)}"
                hablaBOT(error_texto)
                respuesta = error_texto
        else:
            respuesta = "No entendí el comando"
            hablaBOT(respuesta)
            
        # Registrar en el historial si tenemos db
        if db is not None:
            comando_ejecutado = determinar_comando_ejecutado(texto)
            try:
                HistorialService.crear_registro(
                    db=db, 
                    comando_usuario=texto, 
                    comando_ejecutado=comando_ejecutado, 
                    respuesta_asistente=respuesta,
                    usuario_id=usuario_id
                )
                print(f"Historial guardado para usuario_id: {usuario_id}")
            except Exception as e:
                print(f"Error guardando historial: {e}")
        
    except Exception as e:
        respuesta = f"Error ejecutando comando: {str(e)}"
        print(f"Error en ejecutar_comando: {e}")
        
    return respuesta

def determinar_comando_ejecutado(texto: str) -> str:
    """Determinar qué tipo de comando se ejecutó"""
    texto = texto.lower()
    if "reproduce" in texto:
        return "reproduce"
    elif "busca en y" in texto or "busca en youtube" in texto:
        return "busca en youtube"
    elif "hora" in texto:
        return "hora"
    elif "busca en" in texto and "youtube" not in texto:
        return "busca en google"
    elif "dime" in texto:
        return "busca en wikipedia"
    else:
        return "comando no reconocido"