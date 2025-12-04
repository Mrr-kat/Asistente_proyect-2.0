# servicios/auth_service.py - VERSIÓN CORREGIDA
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from db.models import Usuario, RecuperacionContraseña
from datetime import datetime, timedelta
import random
import string
from typing import Optional
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuthService:
    
    @staticmethod
    def registrar_usuario(db: Session, nombre_completo: str, usuario: str, correo: str, contraseña: str):
        """Registrar un nuevo usuario"""
        usuario_existente = db.query(Usuario).filter(
            (Usuario.usuario == usuario) | (Usuario.correo == correo)
        ).first()
        
        if usuario_existente:
            if usuario_existente.usuario == usuario:
                raise ValueError("El nombre de usuario ya está en uso")
            else:
                raise ValueError("El correo electrónico ya está registrado")
        
        nuevo_usuario = Usuario(
            nombre_completo=nombre_completo,
            usuario=usuario,
            correo=correo,
            contraseña=contraseña
        )
        
        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)
        
        return nuevo_usuario
    
    @staticmethod
    def autenticar_usuario(db: Session, usuario: str, contraseña: str) -> Optional[Usuario]:
        """Autenticar un usuario"""
        usuario_db = db.query(Usuario).filter(
            Usuario.usuario == usuario,
            Usuario.activo == True
        ).first()
        
        if usuario_db and usuario_db.contraseña == contraseña:
            return usuario_db
        
        return None
    
    @staticmethod
    def generar_codigo_recuperacion(db: Session, usuario_o_correo: str):
        """Generar código de recuperación de contraseña"""
        # Buscar usuario
        usuario = db.query(Usuario).filter(
            (Usuario.usuario == usuario_o_correo) | (Usuario.correo == usuario_o_correo),
            Usuario.activo == True
        ).first()
        
        if not usuario:
            raise ValueError("Usuario no encontrado")
        
        # Invalidar códigos anteriores
        codigos_anteriores = db.query(RecuperacionContraseña).filter(
            RecuperacionContraseña.usuario_id == usuario.id,
            RecuperacionContraseña.utilizado == False,
            RecuperacionContraseña.expiracion > datetime.now()
        ).all()
        
        for codigo_ant in codigos_anteriores:
            codigo_ant.utilizado = True
        
        # Generar código de 6 dígitos (más seguro)
        codigo = ''.join(random.choices(string.digits, k=6))
        
        # Crear registro
        recuperacion = RecuperacionContraseña(
            usuario_id=usuario.id,
            codigo=codigo,
            expiracion=datetime.now() + timedelta(minutes=15)  # 15 minutos
        )
        
        db.add(recuperacion)
        db.commit()
        
        # Enviar correo
        try:
            AuthService._enviar_correo_gmail(usuario.correo, usuario.usuario, codigo)
            logger.info(f"✅ Correo enviado a {usuario.correo}")
            return {
                "usuario": usuario.usuario,
                "correo": usuario.correo,
                "codigo": None,  # No mostrar en producción
                "enviado": True,
                "mensaje": "Correo enviado exitosamente"
            }
        except Exception as e:
            logger.error(f"❌ Error enviando correo: {e}")
            # En desarrollo, mostrar el código
            return {
                "usuario": usuario.usuario,
                "correo": usuario.correo,
                "codigo": codigo,  # Mostrar en desarrollo
                "enviado": False,
                "mensaje": f"Error: {str(e)}. Código para pruebas: {codigo}"
            }
    
    @staticmethod
    def _enviar_correo_gmail(destinatario: str, usuario: str, codigo: str):
        """Enviar correo usando Gmail SMTP"""
        
        # Obtener credenciales de variables de entorno
        remitente = os.getenv("CORRE_USU")
        password = os.getenv("CORREO_CON")
        
        # Verificar credenciales
        if not remitente or not password:
            logger.error("❌ Credenciales de correo no configuradas")
            raise ValueError("Configura CORREO_USU y CORREO_CON en variables de entorno")
        
        # Crear mensaje HTML
        mensaje = MIMEMultipart("alternative")
        mensaje["From"] = f"Asistente Virtual <{remitente}>"
        mensaje["To"] = destinatario
        mensaje["Subject"] = "🔑 Código de recuperación - Asistente Virtual"
        
        # Versión HTML
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <div style="text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0;">🔐 Recuperación de Contraseña</h1>
                </div>
                
                <div style="padding: 30px;">
                    <h2>Hola {usuario},</h2>
                    <p>Has solicitado recuperar tu contraseña para el <strong>Asistente Virtual</strong>.</p>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; text-align: center; margin: 30px 0;">
                        <p style="margin: 0 0 10px 0; color: #666;">Tu código de verificación es:</p>
                        <h1 style="font-size: 36px; letter-spacing: 5px; color: #667eea; margin: 0;">
                            {codigo}
                        </h1>
                        <p style="margin: 10px 0 0 0; color: #666;">(válido por 15 minutos)</p>
                    </div>
                    
                    <p>📝 <strong>Instrucciones:</strong></p>
                    <ol>
                        <li>Ingresa este código en el formulario de recuperación</li>
                        <li>Crea una nueva contraseña</li>
                        <li>Inicia sesión con tus nuevas credenciales</li>
                    </ol>
                    
                    <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0; color: #856404;">
                            ⚠️ <strong>Importante:</strong> Si no solicitaste este código, ignora este mensaje.
                        </p>
                    </div>
                    
                    <p>¿Necesitas ayuda? Contacta al soporte técnico.</p>
                    
                    <hr style="border: none; height: 1px; background: #eee; margin: 30px 0;">
                    
                    <p style="text-align: center; color: #999; font-size: 12px;">
                        Este es un correo automático, por favor no responder.<br>
                        &copy; {datetime.now().year} Asistente Virtual
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Versión texto plano
        texto = f"""
        Recuperación de contraseña - Asistente Virtual
        
        Hola {usuario},
        
        Has solicitado recuperar tu contraseña.
        
        Tu código de verificación es: {codigo}
        
        Este código expirará en 15 minutos.
        
        Ingresa este código en el formulario de recuperación para crear una nueva contraseña.
        
        Si no solicitaste este código, ignora este mensaje.
        
        Saludos,
        Equipo del Asistente Virtual
        """
        
        # Adjuntar ambas versiones
        parte_texto = MIMEText(texto, "plain")
        parte_html = MIMEText(html, "html")
        
        mensaje.attach(parte_texto)
        mensaje.attach(parte_html)
        
        # Configuración SMTP para Gmail
        try:
            # Método 1: Con contexto SSL (recomendado)
            context = ssl.create_default_context()
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(remitente, password)
                server.sendmail(remitente, destinatario, mensaje.as_string())
                logger.info(f"✅ Correo enviado vía SSL a {destinatario}")
                
        except Exception as e1:
            logger.warning(f"Intento SSL falló, probando TLS: {e1}")
            
            # Método 2: Con TLS (fallback)
            try:
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.starttls()
                    server.login(remitente, password)
                    server.sendmail(remitente, destinatario, mensaje.as_string())
                    logger.info(f"✅ Correo enviado vía TLS a {destinatario}")
                    
            except Exception as e2:
                logger.error(f"Error TLS: {e2}")
                raise Exception(f"No se pudo enviar el correo. Verifica: 1) Contraseña de aplicación, 2) Verificación en 2 pasos desactivada, 3) Acceso de apps menos seguras")
    
    @staticmethod
    def _enviar_correo_desarrollo(destinatario: str, usuario: str, codigo: str):
        """Modo desarrollo - muestra código en consola"""
        print("\n" + "="*70)
        print("📧 [MODO DESARROLLO] CORREO DE RECUPERACIÓN")
        print("="*70)
        print(f"Destinatario: {destinatario}")
        print(f"Usuario: {usuario}")
        print(f"Código: {codigo}")
        print(f"Válido hasta: {(datetime.now() + timedelta(minutes=15)).strftime('%H:%M')}")
        print("="*70 + "\n")
    
    @staticmethod
    def validar_codigo_recuperacion(db: Session, usuario_o_correo: str, codigo: str, marcar_como_utilizado: bool = True):
        """Validar código de recuperación"""
        usuario = db.query(Usuario).filter(
            (Usuario.usuario == usuario_o_correo) | (Usuario.correo == usuario_o_correo),
            Usuario.activo == True
        ).first()
        
        if not usuario:
            raise ValueError("Usuario no encontrado")
        
        # Buscar código válido
        recuperacion = db.query(RecuperacionContraseña).filter(
            RecuperacionContraseña.usuario_id == usuario.id,
            RecuperacionContraseña.codigo == codigo,
            RecuperacionContraseña.expiracion > datetime.now(),
            RecuperacionContraseña.utilizado == False
        ).first()
        
        if not recuperacion:
            # Verificar si ya fue usado
            usado = db.query(RecuperacionContraseña).filter(
                RecuperacionContraseña.usuario_id == usuario.id,
                RecuperacionContraseña.codigo == codigo,
                RecuperacionContraseña.utilizado == True
            ).first()
            
            if usado:
                raise ValueError("Este código ya fue utilizado")
            else:
                raise ValueError("Código inválido o expirado")
        
        # Marcar como utilizado si se indica
        if marcar_como_utilizado:
            recuperacion.utilizado = True
            db.commit()
        
        return usuario.id
    
    @staticmethod
    def cambiar_contraseña(db: Session, usuario_id: int, nueva_contraseña: str, codigo_recuperacion: str = None):
        """Cambiar contraseña de usuario"""
        usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
        
        if not usuario:
            raise ValueError("Usuario no encontrado")
        
        # Validar longitud mínima
        if len(nueva_contraseña) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        
        # Si es por recuperación, validar código
        if codigo_recuperacion:
            recuperacion = db.query(RecuperacionContraseña).filter(
                RecuperacionContraseña.usuario_id == usuario_id,
                RecuperacionContraseña.codigo == codigo_recuperacion,
                RecuperacionContraseña.expiracion > datetime.now()
            ).first()
            
            if not recuperacion:
                raise ValueError("Código de recuperación no válido o expirado")
            
            if not recuperacion.utilizado:
                recuperacion.utilizado = True
                db.commit()
        
        usuario.contraseña = nueva_contraseña
        db.commit()
        
        logger.info(f"✅ Contraseña cambiada para usuario ID: {usuario_id}")
        return True
    
    @staticmethod
    def obtener_usuario_por_id(db: Session, usuario_id: int):
        """Obtener usuario por ID"""
        return db.query(Usuario).filter(Usuario.id == usuario_id).first()
