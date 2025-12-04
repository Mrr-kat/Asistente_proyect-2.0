# db/models.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import os
import random

# Configuración de la base de datos SQLite
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'asistente_virtual.db')}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String(200), nullable=False)
    usuario = Column(String(100), unique=True, nullable=False, index=True)
    correo = Column(String(150), unique=True, nullable=False)
    contraseña = Column(String(200), nullable=False)
    fecha_registro = Column(DateTime, default=datetime.now)
    activo = Column(Boolean, default=True)
    
    # Relación con el historial
    historial = relationship("HistorialInteraccion", back_populates="usuario")
    recuperaciones = relationship("RecuperacionContraseña", back_populates="usuario")

class RecuperacionContraseña(Base):
    __tablename__ = "recuperaciones_contraseña"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    codigo = Column(String(6), nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.now)
    expiracion = Column(DateTime)
    utilizado = Column(Boolean, default=False)
    
    usuario = relationship("Usuario", back_populates="recuperaciones")

class HistorialInteraccion(Base):
    __tablename__ = "historial_interacciones"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    comando_usuario = Column(String(500), nullable=False)
    comando_ejecutado = Column(String(100), nullable=False)
    respuesta_asistente = Column(Text, nullable=False)
    fecha_hora = Column(DateTime, default=datetime.now)
    activo = Column(Boolean, default=True)
    
    # Relación con el usuario
    usuario = relationship("Usuario", back_populates="historial")
    
    def to_dict(self):
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "comando_usuario": self.comando_usuario,
            "comando_ejecutado": self.comando_ejecutado,
            "respuesta_asistente": self.respuesta_asistente,
            "fecha_hora": self.fecha_hora.strftime("%d/%m/%Y %I:%M%p"),
            "activo": self.activo
        }

# Crear tablas
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()