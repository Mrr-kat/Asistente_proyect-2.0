#!/usr/bin/env bash
# build.sh optimizado para Render

echo "=== Starting build process ==="

# 1. Actualizar sistema
apt-get update -qq

# 2. Instalar dependencias del sistema para audio
echo "Installing system dependencies for audio..."
apt-get install -y --no-install-recommends \
    portaudio19-dev \
    python3-dev \
    build-essential \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    libavcodec-extra

# 3. Actualizar pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# 4. Instalar dependencias Python
echo "Installing Python dependencies..."
pip install -r requirements.txt --no-cache-dir

# 5. Crear directorios necesarios
echo "Creating necessary directories..."
mkdir -p static/temp static/reportes static/audios
mkdir -p templates/Asistente templates/login
touch static/temp/.gitkeep static/reportes/.gitkeep static/audios/.gitkeep

# 6. Verificar instalación
echo "=== Verification ==="
python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
python -c "import sqlalchemy; print(f'SQLAlchemy: {sqlalchemy.__version__}')"
python -c "import speech_recognition; print('SpeechRecognition OK')"

echo "=== Build completed successfully ==="
