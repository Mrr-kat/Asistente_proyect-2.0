# servicios/historial_service.py
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from sqlalchemy.orm import Session
from db.models import HistorialInteraccion
from datetime import datetime
from typing import List, Optional

class HistorialService:
    
    @staticmethod
    def crear_registro(db: Session, comando_usuario: str, comando_ejecutado: str, 
                      respuesta_asistente: str, usuario_id: Optional[int] = None):
        """Crear un nuevo registro en el historial"""
        registro = HistorialInteraccion(
            comando_usuario=comando_usuario,
            comando_ejecutado=comando_ejecutado,
            respuesta_asistente=respuesta_asistente,
            usuario_id=usuario_id
        )
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return registro
    
    @staticmethod
    def obtener_todos(db: Session, usuario_id: Optional[int] = None, solo_activos: bool = True):
        """Obtener todos los registros del historial"""
        query = db.query(HistorialInteraccion)
        
        if usuario_id is not None:
            query = query.filter(HistorialInteraccion.usuario_id == usuario_id)
        
        if solo_activos:
            query = query.filter(HistorialInteraccion.activo == True)
        
        return query.order_by(HistorialInteraccion.fecha_hora.desc()).all()
    
    @staticmethod
    def buscar_por_texto(db: Session, texto: str, usuario_id: Optional[int] = None, solo_activos: bool = True):
        """Buscar registros por texto en el comando del usuario"""
        query = db.query(HistorialInteraccion).filter(
            HistorialInteraccion.comando_usuario.ilike(f"%{texto}%")
        )
        
        if usuario_id is not None:
            query = query.filter(HistorialInteraccion.usuario_id == usuario_id)
        
        if solo_activos:
            query = query.filter(HistorialInteraccion.activo == True)
        
        return query.order_by(HistorialInteraccion.fecha_hora.desc()).all()
    
    @staticmethod
    def obtener_por_id(db: Session, registro_id: int, usuario_id: Optional[int] = None):
        """Obtener un registro específico por ID"""
        query = db.query(HistorialInteraccion).filter(HistorialInteraccion.id == registro_id)
        
        if usuario_id is not None:
            query = query.filter(HistorialInteraccion.usuario_id == usuario_id)
        
        return query.first()
    
    @staticmethod
    def actualizar_registro(db: Session, registro_id: int, comando_usuario: str = None, 
                           respuesta_asistente: str = None, usuario_id: Optional[int] = None):
        """Actualizar un registro existente"""
        registro = HistorialService.obtener_por_id(db, registro_id, usuario_id)
        if registro:
            if comando_usuario is not None:
                registro.comando_usuario = comando_usuario
            if respuesta_asistente is not None:
                registro.respuesta_asistente = respuesta_asistente
            db.commit()
            db.refresh(registro)
        return registro
    
    @staticmethod
    def eliminar_registro(db: Session, registro_id: int, usuario_id: Optional[int] = None):
        """Eliminación lógica de un registro (cambia estado activo a False)"""
        registro = HistorialService.obtener_por_id(db, registro_id, usuario_id)
        if registro:
            registro.activo = False
            db.commit()
            return True
        return False
    
    @staticmethod
    def restaurar_registro(db: Session, registro_id: int, usuario_id: Optional[int] = None):
        """Restaurar un registro eliminado (cambia estado activo a True)"""
        registro = HistorialService.obtener_por_id(db, registro_id, usuario_id)
        if registro:
            registro.activo = True
            db.commit()
            return True
        return False
    
    @staticmethod
    def eliminar_permanentemente(db: Session, registro_id: int, usuario_id: Optional[int] = None):
        """Eliminación física de un registro"""
        registro = HistorialService.obtener_por_id(db, registro_id, usuario_id)
        if registro:
            db.delete(registro)
            db.commit()
            return True
        return False
    
    @staticmethod
    def obtener_estadisticas(db: Session, usuario_id: Optional[int] = None):
        """Obtener estadísticas del historial"""
        query = db.query(HistorialInteraccion)
        
        if usuario_id is not None:
            query = query.filter(HistorialInteraccion.usuario_id == usuario_id)
        
        total_registros = query.count()
        
        query_activos = query.filter(HistorialInteraccion.activo == True)
        registros_activos = query_activos.count()
        
        # Comandos más utilizados
        if usuario_id is not None:
            comandos_populares = query_activos.with_entities(
                HistorialInteraccion.comando_ejecutado,
                db.func.count(HistorialInteraccion.id).label('cantidad')
            ).group_by(
                HistorialInteraccion.comando_ejecutado
            ).order_by(db.func.count(HistorialInteraccion.id).desc()).limit(5).all()
        else:
            comandos_populares = []
        
        return {
            "total_registros": total_registros,
            "registros_activos": registros_activos,
            "comandos_populares": [{"comando": c[0], "cantidad": c[1]} for c in comandos_populares]
        }
    
    @staticmethod
    def generar_reporte_pdf(db: Session, ruta_archivo: str, usuario_id: Optional[int] = None):
        """Generar reporte en formato PDF"""
        registros = HistorialService.obtener_todos(db, usuario_id, solo_activos=True)
        
        # Crear el documento PDF
        doc = SimpleDocTemplate(ruta_archivo, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        titulo = "Reporte de Historial Personal"
        if usuario_id is None:
            titulo = "Reporte de Historial - Asistente Virtual"
        
        title = Paragraph(titulo, styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 0.3*inch))
        
        # Fecha de generación
        fecha_gen = Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %I:%M %p')}", styles['Normal'])
        elements.append(fecha_gen)
        elements.append(Spacer(1, 0.2*inch))
        
        # Preparar datos para la tabla
        data = [['Fecha', 'Comando Usuario', 'Respuesta Asistente']]
        
        for registro in registros:
            # Limitar el texto para que quepa en el PDF
            comando = registro.comando_usuario[:80] + "..." if len(registro.comando_usuario) > 80 else registro.comando_usuario
            respuesta = registro.respuesta_asistente[:80] + "..." if len(registro.respuesta_asistente) > 80 else registro.respuesta_asistente
            
            data.append([
                registro.fecha_hora.strftime("%d/%m/%Y %I:%M%p"),
                comando,
                respuesta
            ])
        
        # Crear tabla
        table = Table(data, colWidths=[1.5*inch, 3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(table)
        
        # Construir PDF
        doc.build(elements)
        return ruta_archivo