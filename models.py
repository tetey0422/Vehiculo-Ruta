from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.orm import validates

# Inicializamos SQLAlchemy
db = SQLAlchemy()

class Vehiculo(db.Model):
    __tablename__ = 'vehiculos'
    
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(20), nullable=False, unique=True, index=True)
    marca = db.Column(db.String(50), nullable=False, index=True)
    modelo = db.Column(db.String(50), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    capacidad = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(20), default='Disponible', index=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con rutas (one-to-many)
    rutas = db.relationship('Ruta', backref='vehiculo_asignado', lazy=True, cascade='all, delete-orphan')
    
    # Validaciones
    @validates('placa')
    def validate_placa(self, key, value):
        if not value or len(value) < 6 or len(value) > 8:
            raise ValueError("La placa debe tener entre 6 y 8 caracteres")
        return value.upper().strip()
    
    @validates('anio')
    def validate_anio(self, key, value):
        if value < 1990 or value > 2025:
            raise ValueError("Año inválido")
        return value
    
    @validates('capacidad')
    def validate_capacidad(self, key, value):
        if value <= 0 or value > 100:
            raise ValueError("Capacidad debe ser entre 1 y 100")
        return value
    
    @validates('estado')
    def validate_estado(self, key, value):
        estados_validos = ['Disponible', 'En Ruta', 'Mantenimiento']
        if value not in estados_validos:
            raise ValueError(f"Estado debe ser uno de: {', '.join(estados_validos)}")
        return value
    
    # Métodos útiles
    @property
    def tiene_rutas_activas(self):
        """Verifica si el vehículo tiene rutas en curso"""
        return any(ruta.estado == 'En curso' for ruta in self.rutas)
    
    @property
    def nombre_completo(self):
        """Devuelve el nombre completo del vehículo"""
        return f"{self.marca} {self.modelo} ({self.placa})"
    
    @property
    def edad(self):
        """Calcula la edad del vehículo"""
        return datetime.now().year - self.anio
    
    def puede_ser_asignado(self):
        """Verifica si el vehículo puede ser asignado a una nueva ruta"""
        return self.estado == 'Disponible' and not self.tiene_rutas_activas
    
    def cambiar_estado(self, nuevo_estado, validar_logica=True):
        """Cambia el estado del vehículo con validaciones de lógica de negocio"""
        if validar_logica:
            if nuevo_estado == 'Disponible' and self.tiene_rutas_activas:
                raise ValueError("No se puede marcar como disponible un vehículo con rutas activas")
            
            if nuevo_estado == 'En Ruta' and not self.tiene_rutas_activas:
                raise ValueError("No se puede marcar en ruta un vehículo sin rutas activas")
        
        self.estado = nuevo_estado
        return self

    def __repr__(self):
        return f'<Vehiculo {self.placa} - {self.marca} {self.modelo} ({self.estado})>'

class Ruta(db.Model):
    __tablename__ = 'rutas'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    origen = db.Column(db.String(100), nullable=False, index=True)
    destino = db.Column(db.String(100), nullable=False, index=True)
    distancia = db.Column(db.Float, nullable=False)
    tiempo_estimado = db.Column(db.Integer, nullable=False)  # en minutos
    vehiculo_id = db.Column(db.Integer, db.ForeignKey('vehiculos.id'), nullable=True, index=True)
    estado = db.Column(db.String(20), default='Programada', index=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fecha_inicio = db.Column(db.DateTime, nullable=True)
    fecha_fin = db.Column(db.DateTime, nullable=True)
    
    # Validaciones
    @validates('distancia')
    def validate_distancia(self, key, value):
        if value <= 0:
            raise ValueError("La distancia debe ser mayor a 0")
        return value
    
    @validates('tiempo_estimado')
    def validate_tiempo_estimado(self, key, value):
        if value <= 0:
            raise ValueError("El tiempo estimado debe ser mayor a 0")
        return value
    
    @validates('estado')
    def validate_estado(self, key, value):
        estados_validos = ['Programada', 'En curso', 'Completada', 'Cancelada']
        if value not in estados_validos:
            raise ValueError(f"Estado debe ser uno de: {', '.join(estados_validos)}")
        return value
    
    # Métodos útiles
    @property
    def duracion_real(self):
        """Calcula la duración real si la ruta ha terminado"""
        if self.fecha_inicio and self.fecha_fin:
            delta = self.fecha_fin - self.fecha_inicio
            return int(delta.total_seconds() / 60)  # en minutos
        return None
    
    @property
    def velocidad_promedio(self):
        """Calcula la velocidad promedio si la ruta ha terminado"""
        duracion = self.duracion_real
        if duracion:
            return round(self.distancia / (duracion / 60), 2)  # km/h
        return None
    
    @property
    def descripcion_completa(self):
        """Devuelve una descripción completa de la ruta"""
        vehiculo_info = f" - {self.vehiculo_asignado.placa}" if self.vehiculo_asignado else ""
        return f"{self.nombre}: {self.origen} → {self.destino}{vehiculo_info}"
    
    def iniciar_ruta(self):
        """Inicia la ruta cambiando su estado y el del vehículo"""
        if self.estado != 'Programada':
            raise ValueError("Solo se pueden iniciar rutas programadas")
        
        if self.vehiculo_asignado and self.vehiculo_asignado.estado != 'Disponible':
            raise ValueError("El vehículo asignado no está disponible")
        
        self.estado = 'En curso'
        self.fecha_inicio = datetime.utcnow()
        
        if self.vehiculo_asignado:
            self.vehiculo_asignado.estado = 'En Ruta'
        
        return self
    
    def completar_ruta(self):
        """Completa la ruta y libera el vehículo"""
        if self.estado != 'En curso':
            raise ValueError("Solo se pueden completar rutas en curso")
        
        self.estado = 'Completada'
        self.fecha_fin = datetime.utcnow()
        
        if self.vehiculo_asignado:
            self.vehiculo_asignado.estado = 'Disponible'
        
        return self
    
    def cancelar_ruta(self, razon=None):
        """Cancela la ruta y libera el vehículo"""
        self.estado = 'Cancelada'
        
        if self.vehiculo_asignado and self.vehiculo_asignado.estado == 'En Ruta':
            self.vehiculo_asignado.estado = 'Disponible'
        
        return self

    def __repr__(self):
        return f'<Ruta {self.nombre}: {self.origen} → {self.destino} ({self.estado})>'

# Event Listeners para mantener consistencia de datos
@event.listens_for(Ruta, 'before_update')
def ruta_before_update(mapper, connection, target):
    """Mantiene consistencia cuando se actualiza una ruta"""
    # Si la ruta pasa a 'En curso', asegurar que el vehículo esté 'En Ruta'
    if target.estado == 'En curso' and target.vehiculo_asignado:
        target.vehiculo_asignado.estado = 'En Ruta'
    
    # Si la ruta se completa o cancela, liberar el vehículo
    elif target.estado in ['Completada', 'Cancelada'] and target.vehiculo_asignado:
        # Verificar que no tenga otras rutas activas
        rutas_activas = db.session.query(Ruta).filter(
            Ruta.vehiculo_id == target.vehiculo_id,
            Ruta.estado == 'En curso',
            Ruta.id != target.id
        ).count()
        
        if rutas_activas == 0:
            target.vehiculo_asignado.estado = 'Disponible'

@event.listens_for(Ruta, 'before_delete')
def ruta_before_delete(mapper, connection, target):
    """Libera el vehículo cuando se elimina una ruta"""
    if target.vehiculo_asignado and target.estado == 'En curso':
        # Verificar que no tenga otras rutas activas
        rutas_activas = db.session.query(Ruta).filter(
            Ruta.vehiculo_id == target.vehiculo_id,
            Ruta.estado == 'En curso',
            Ruta.id != target.id
        ).count()
        
        if rutas_activas == 0:
            target.vehiculo_asignado.estado = 'Disponible'