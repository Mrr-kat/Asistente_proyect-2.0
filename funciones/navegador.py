import psutil
import webbrowser
import os

def abrir_en_navegador(url: str):
    # Diccionario con navegadores comunes y sus posibles rutas de instalación
    navegadores = {
        "opera.exe": [
            r"C:\Users\%USERNAME%\AppData\Local\Programs\Opera GX\launcher.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Programs\Opera\launcher.exe"
        ],
        "chrome.exe": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ],
        "firefox.exe": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
        ],
        "brave.exe": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"
        ]
    }

    # Buscar procesos en ejecución
    for proc in psutil.process_iter(attrs=['name']):
        nombre = proc.info['name'].lower()
        if nombre in navegadores:
            for ruta in navegadores[nombre]:
                ruta_exp = os.path.expandvars(ruta)  # Expande %USERNAME%
                if os.path.exists(ruta_exp):  # Verifica si existe
                    nav = webbrowser.BackgroundBrowser(ruta_exp)
                    webbrowser.register(nombre, None, nav)
                    webbrowser.get(nombre).open_new_tab(url)
                    return

    # Si no encontró ninguno abierto, usar predeterminado
    webbrowser.open(url)
