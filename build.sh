#!/usr/bin/env bash
# build.sh optimizado para Render - Versión 2.0

set -e  # Detener en caso de error

echo "========================================="
echo "        CONSTRUYENDO EN RENDER          "
echo "========================================="

# 1. ACTUALIZAR SISTEMA E INSTALAR DEPENDENCIAS
echo "[1/6] Actualizando sistema e instalando dependencias..."
apt-get update -qq

# Instalar dependencias del sistema PARA AUDIO
apt-get install -y --no-install-recommends \
    python3-dev \
    build-essential \
    ffmpeg \
    libavcodec-extra \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    libasound2-dev \
    libjack-jackd2-dev \
    libsndfile1-dev \
    libflac-dev \
    libogg-dev \
    libvorbis-dev \
    libmp3lame-dev \
    libopus-dev

# 2. LIMPIAR CACHE PARA AHORRAR ESPACIO
echo "[2/6] Limpiando cache de apt..."
apt-get clean
rm -rf /var/lib/apt/lists/*

# 3. ACTUALIZAR PIP Y HERRAMIENTAS
echo "[3/6] Actualizando pip y herramientas..."
pip install --upgrade pip setuptools wheel

# 4. INSTALAR DEPENDENCIAS PYTHON
echo "[4/6] Instalando dependencias Python..."
pip install -r requirements.txt --no-cache-dir

# 5. INSTALAR PyAudio DESDE WHEEL PRECOMPILADO (si es posible)
echo "[5/6] Intentando instalar PyAudio alternativo..."
# Intentar instalar desde wheel precompilado
pip install PyAudio==0.2.14 2>/dev/null || echo "PyAudio no disponible - usando sounddevice"

# 6. CREAR DIRECTORIOS Y ARCHIVOS NECESARIOS
echo "[6/6] Configurando estructura de directorios..."
mkdir -p static/temp static/reportes static/audios
mkdir -p templates/Asistente templates/login
mkdir -p db funciones servicios key

# Crear archivos .gitkeep para mantener estructura
touch static/temp/.gitkeep static/reportes/.gitkeep static/audios/.gitkeep
touch templates/Asistente/.gitkeep templates/login/.gitkeep
touch db/.gitkeep funciones/.gitkeep servicios/.gitkeep key/.gitkeep

# 7. VERIFICAR INSTALACIÓN
echo "========================================="
echo "         VERIFICANDO INSTALACIÓN         "
echo "========================================="

python3 -c "
import sys
print(f'Python: {sys.version}')

try:
    import fastapi
    print('✅ FastAPI instalado')
except ImportError:
    print('❌ FastAPI NO instalado')

try:
    import sqlalchemy
    print(f'✅ SQLAlchemy: {sqlalchemy.__version__}')
except ImportError:
    print('❌ SQLAlchemy NO instalado')

try:
    import speech_recognition
    print('✅ SpeechRecognition instalado')
except ImportError:
    print('❌ SpeechRecognition NO instalado')

try:
    import sounddevice
    print('✅ sounddevice instalado (alternativa a PyAudio)')
except ImportError:
    print('⚠️  sounddevice NO instalado')

try:
    import pvporcupine
    print('✅ Porcupine instalado')
except ImportError:
    print('⚠️  Porcupine NO instalado')

print('=========================================')
print('Construcción completada exitosamente!')
print('=========================================')
"

# 8. PERMISOS DE EJECUCIÓN
chmod +x build.sh
