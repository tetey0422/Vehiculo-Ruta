from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import db, Vehiculo, Ruta
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, FloatField
from wtforms.validators import DataRequired, Length, NumberRange
import secrets
from dotenv import load_dotenv
import os 
import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy import exists, and_

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configuración mejorada
def configure_app():
    # Generar SECRET_KEY segura si no existe
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY no encontrada, generando una temporal")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        "SQLALCHEMY_DATABASE_URI", 
        "sqlite:///transporte.db"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = secret_key
    app.config['WTF_CSRF_ENABLED'] = True

configure_app()

# Inicializar extensiones
db.init_app(app)

# Formularios con validación
class VehiculoForm(FlaskForm):
    placa = StringField('Placa', validators=[
        DataRequired(), 
        Length(min=6, max=8, message="La placa debe tener entre 6 y 8 caracteres")
    ])
    marca = StringField('Marca', validators=[DataRequired(), Length(max=50)])
    modelo = StringField('Modelo', validators=[DataRequired(), Length(max=50)])
    anio = IntegerField('Año', validators=[
        DataRequired(), 
        NumberRange(min=1990, max=2025, message="Año inválido")
    ])
    capacidad = IntegerField('Capacidad', validators=[
        DataRequired(), 
        NumberRange(min=1, max=100, message="Capacidad debe ser entre 1 y 100")
    ])
    estado = SelectField('Estado', choices=[
        ('Disponible', 'Disponible'),
        ('En Ruta', 'En Ruta'),
        ('Mantenimiento', 'Mantenimiento')
    ])

class RutaForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=100)])
    origen = StringField('Origen', validators=[DataRequired(), Length(max=100)])
    destino = StringField('Destino', validators=[DataRequired(), Length(max=100)])
    distancia = FloatField('Distancia (km)', validators=[
        DataRequired(), 
        NumberRange(min=0.1, message="La distancia debe ser mayor a 0")
    ])
    tiempo_estimado = IntegerField('Tiempo Estimado (min)', validators=[
        DataRequired(), 
        NumberRange(min=1, message="El tiempo debe ser mayor a 0")
    ])
    vehiculo_id = SelectField('Vehículo', coerce=int, validate_choice=False)
    estado = SelectField('Estado', choices=[
        ('Programada', 'Programada'),
        ('En curso', 'En curso'),
        ('Completada', 'Completada'),
        ('Cancelada', 'Cancelada')
    ])

# Crear tablas
with app.app_context():
    try:
        db.create_all()
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")

# RUTAS CORREGIDAS
@app.route('/')
def index():
    try:
        # Consultas separadas y más simples
        total_vehiculos = Vehiculo.query.count()
        vehiculos_disponibles = Vehiculo.query.filter_by(estado='Disponible').count()
        total_rutas = Ruta.query.count()
        rutas_activas = Ruta.query.filter_by(estado='En curso').count()
        
        return render_template('index.html', 
                             total_vehiculos=total_vehiculos,
                             total_rutas=total_rutas,
                             vehiculos_disponibles=vehiculos_disponibles,
                             rutas_activas=rutas_activas)
    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        flash('Error cargando el dashboard', 'error')
        return render_template('index.html', 
                             total_vehiculos=0, total_rutas=0,
                             vehiculos_disponibles=0, rutas_activas=0)

@app.route('/vehiculos')
def listar_vehiculos():
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        
        query = Vehiculo.query
        if search:
            query = query.filter(
                (Vehiculo.placa.contains(search)) |
                (Vehiculo.marca.contains(search)) |
                (Vehiculo.modelo.contains(search))
            )
        
        vehiculos = query.paginate(
            page=page, per_page=10, error_out=False
        )
        
        return render_template('vehiculos.html', 
                             vehiculos=vehiculos, search=search)
    except Exception as e:
        logger.error(f"Error listando vehículos: {e}")
        flash('Error cargando vehículos', 'error')
        return redirect(url_for('index'))

@app.route('/rutas')
def listar_rutas():
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        
        query = Ruta.query
        if search:
            query = query.filter(
                (Ruta.nombre.contains(search)) |
                (Ruta.origen.contains(search)) |
                (Ruta.destino.contains(search))
            )
        
        rutas = query.paginate(
            page=page, per_page=10, error_out=False
        )
        
        return render_template('rutas.html', 
                             rutas=rutas, search=search)
    except Exception as e:
        logger.error(f"Error listando rutas: {e}")
        flash('Error cargando rutas', 'error')
        return redirect(url_for('index'))

@app.route('/nuevo_vehiculo', methods=['GET', 'POST'])
def nuevo_vehiculo():
    form = VehiculoForm()
    
    if form.validate_on_submit():
        try:
            # Verificar placa duplicada
            placa_upper = form.placa.data.upper().strip()
            if Vehiculo.query.filter_by(placa=placa_upper).first():
                flash('Ya existe un vehículo con esa placa', 'error')
                return render_template('nuevo_vehiculo.html', form=form)
            
            vehiculo = Vehiculo(
                placa=placa_upper,
                marca=form.marca.data.strip(),
                modelo=form.modelo.data.strip(),
                anio=form.anio.data,
                capacidad=form.capacidad.data,
                estado=form.estado.data
            )
            
            db.session.add(vehiculo)
            db.session.commit()
            
            flash('Vehículo creado exitosamente', 'success')
            return redirect(url_for('listar_vehiculos'))
            
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Error de integridad: {e}")
            flash('Error: La placa ya existe', 'error')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando vehículo: {e}")
            flash('Error creando vehículo', 'error')
    else:
        # Mostrar errores de validación
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en {field}: {error}", 'error')
    
    return render_template('nuevo_vehiculo.html', form=form)

@app.route('/nueva_ruta', methods=['GET', 'POST'])
def nueva_ruta():
    form = RutaForm()
    
    # Poblar choices de vehículos disponibles
    vehiculos_disponibles = Vehiculo.query.filter_by(estado='Disponible').all()
    form.vehiculo_id.choices = [(0, 'Sin asignar')] + [
        (v.id, f"{v.placa} - {v.marca} {v.modelo}") 
        for v in vehiculos_disponibles
    ]
    
    if form.validate_on_submit():
        try:
            vehiculo = None
            # Validar lógica de negocio
            if form.vehiculo_id.data and form.vehiculo_id.data != 0:
                vehiculo = Vehiculo.query.get(form.vehiculo_id.data)
                if not vehiculo:
                    flash('El vehículo seleccionado no existe', 'error')
                    return render_template('nueva_ruta.html', form=form)
                    
                if vehiculo.estado != 'Disponible':
                    flash('El vehículo seleccionado no está disponible', 'error')
                    return render_template('nueva_ruta.html', form=form)
            
            ruta = Ruta(
                nombre=form.nombre.data.strip(),
                origen=form.origen.data.strip(),
                destino=form.destino.data.strip(),
                distancia=form.distancia.data,
                tiempo_estimado=form.tiempo_estimado.data,
                vehiculo_id=form.vehiculo_id.data if form.vehiculo_id.data != 0 else None,
                estado=form.estado.data
            )
            
            db.session.add(ruta)
            
            # Si la ruta está "En curso", cambiar estado del vehículo
            if vehiculo and form.estado.data == 'En curso':
                vehiculo.estado = 'En Ruta'
            
            db.session.commit()
            
            flash('Ruta creada exitosamente', 'success')
            return redirect(url_for('listar_rutas'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando ruta: {e}")
            flash(f'Error creando ruta: {str(e)}', 'error')
    else:
        # Mostrar errores de validación
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en {field}: {error}", 'error')
    
    return render_template('nueva_ruta.html', form=form)

@app.route('/vehiculo/<int:id>')
def detalle_vehiculo(id):
    try:
        vehiculo = Vehiculo.query.get_or_404(id)
        return render_template('detalle_vehiculo.html', vehiculo=vehiculo)
    except Exception as e:
        logger.error(f"Error obteniendo detalle vehículo {id}: {e}")
        flash('Error cargando detalle del vehículo', 'error')
        return redirect(url_for('listar_vehiculos'))

@app.route('/ruta/<int:id>')
def detalle_ruta(id):
    try:
        ruta = Ruta.query.get_or_404(id)
        return render_template('detalle_ruta.html', ruta=ruta)
    except Exception as e:
        logger.error(f"Error obteniendo detalle ruta {id}: {e}")
        flash('Error cargando detalle de la ruta', 'error')
        return redirect(url_for('listar_rutas'))

@app.route('/editar_ruta/<int:id>', methods=['GET', 'POST'])
def editar_ruta(id):
    form = RutaForm()
    ruta = Ruta.query.get_or_404(id)
    
    # Poblar choices de vehículos disponibles + el vehículo actual
    vehiculos_disponibles = Vehiculo.query.filter_by(estado='Disponible').all()
    choices = [(0, 'Sin asignar')]
    
    # Agregar vehículo actual si existe
    if ruta.vehiculo_asignado:
        choices.append((ruta.vehiculo_asignado.id, f"{ruta.vehiculo_asignado.placa} - {ruta.vehiculo_asignado.marca} {ruta.vehiculo_asignado.modelo} (Actual)"))
    
    # Agregar vehículos disponibles
    for v in vehiculos_disponibles:
        if not ruta.vehiculo_asignado or v.id != ruta.vehiculo_asignado.id:
            choices.append((v.id, f"{v.placa} - {v.marca} {v.modelo}"))
    
    form.vehiculo_id.choices = choices
    
    if form.validate_on_submit():
        try:
            # Validar lógica de negocio
            nuevo_vehiculo = None
            if form.vehiculo_id.data and form.vehiculo_id.data != 0:
                nuevo_vehiculo = Vehiculo.query.get(form.vehiculo_id.data)
                if not nuevo_vehiculo:
                    flash('El vehículo seleccionado no existe', 'error')
                    return render_template('editar_ruta.html', form=form, ruta=ruta)
                    
                if nuevo_vehiculo.estado not in ['Disponible', 'En Ruta']:
                    flash('El vehículo seleccionado no está disponible', 'error')
                    return render_template('editar_ruta.html', form=form, ruta=ruta)
            
            # Liberar vehículo anterior si cambió
            if ruta.vehiculo_asignado and (not nuevo_vehiculo or nuevo_vehiculo.id != ruta.vehiculo_asignado.id):
                if ruta.estado == 'En curso':
                    ruta.vehiculo_asignado.estado = 'Disponible'
            
            # Actualizar datos de la ruta
            ruta.nombre = form.nombre.data.strip()
            ruta.origen = form.origen.data.strip()
            ruta.destino = form.destino.data.strip()
            ruta.distancia = form.distancia.data
            ruta.tiempo_estimado = form.tiempo_estimado.data
            ruta.vehiculo_id = form.vehiculo_id.data if form.vehiculo_id.data != 0 else None
            ruta.estado = form.estado.data
            
            # Actualizar estado del nuevo vehículo si es necesario
            if nuevo_vehiculo and form.estado.data == 'En curso':
                nuevo_vehiculo.estado = 'En Ruta'
            
            db.session.commit()
            flash('Ruta actualizada exitosamente', 'success')
            return redirect(url_for('listar_rutas'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando ruta: {e}")
            flash(f'Error actualizando ruta: {str(e)}', 'error')
    else:
        # Pre-llenar el formulario con datos actuales
        form.nombre.data = ruta.nombre
        form.origen.data = ruta.origen
        form.destino.data = ruta.destino
        form.distancia.data = ruta.distancia
        form.tiempo_estimado.data = ruta.tiempo_estimado
        form.vehiculo_id.data = ruta.vehiculo_id if ruta.vehiculo_id else 0
        form.estado.data = ruta.estado
        
        # Mostrar errores de validación
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en {field}: {error}", 'error')
    
    return render_template('editar_ruta.html', form=form, ruta=ruta)

@app.route('/eliminar_ruta/<int:id>', methods=['POST'])
def eliminar_ruta(id):
    try:
        ruta = Ruta.query.get_or_404(id)
        
        # Liberar vehículo si está asignado
        if ruta.vehiculo_asignado and ruta.estado == 'En curso':
            ruta.vehiculo_asignado.estado = 'Disponible'
        
        db.session.delete(ruta)
        db.session.commit()
        
        flash(f'Ruta "{ruta.nombre}" eliminada exitosamente', 'success')
        return redirect(url_for('listar_rutas'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error eliminando ruta {id}: {e}")
        flash('Error eliminando ruta', 'error')
        return redirect(url_for('listar_rutas'))

@app.route('/editar_vehiculo/<int:id>', methods=['GET', 'POST'])
def editar_vehiculo(id):
    form = VehiculoForm()
    vehiculo = Vehiculo.query.get_or_404(id)
    
    if form.validate_on_submit():
        try:
            # Verificar placa duplicada (excepto el actual)
            placa_upper = form.placa.data.upper().strip()
            vehiculo_existente = Vehiculo.query.filter_by(placa=placa_upper).first()
            if vehiculo_existente and vehiculo_existente.id != vehiculo.id:
                flash('Ya existe otro vehículo con esa placa', 'error')
                return render_template('editar_vehiculo.html', form=form, vehiculo=vehiculo)
            
            # Validar cambio de estado
            if form.estado.data != vehiculo.estado:
                if form.estado.data == 'Disponible' and vehiculo.tiene_rutas_activas:
                    flash('No se puede marcar como disponible un vehículo con rutas activas', 'error')
                    return render_template('editar_vehiculo.html', form=form, vehiculo=vehiculo)
            
            # Actualizar datos
            vehiculo.placa = placa_upper
            vehiculo.marca = form.marca.data.strip()
            vehiculo.modelo = form.modelo.data.strip()
            vehiculo.anio = form.anio.data
            vehiculo.capacidad = form.capacidad.data
            vehiculo.estado = form.estado.data
            
            db.session.commit()
            flash('Vehículo actualizado exitosamente', 'success')
            return redirect(url_for('listar_vehiculos'))
            
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Error de integridad: {e}")
            flash('Error: La placa ya existe', 'error')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando vehículo: {e}")
            flash('Error actualizando vehículo', 'error')
    else:
        # Pre-llenar el formulario con datos actuales
        form.placa.data = vehiculo.placa
        form.marca.data = vehiculo.marca
        form.modelo.data = vehiculo.modelo
        form.anio.data = vehiculo.anio
        form.capacidad.data = vehiculo.capacidad
        form.estado.data = vehiculo.estado
        
        # Mostrar errores de validación
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en {field}: {error}", 'error')
    
    return render_template('editar_vehiculo.html', form=form, vehiculo=vehiculo)

@app.route('/eliminar_vehiculo/<int:id>', methods=['POST'])
def eliminar_vehiculo(id):
    try:
        vehiculo = Vehiculo.query.get_or_404(id)
        
        # Verificar que no tenga rutas activas
        if vehiculo.tiene_rutas_activas:
            flash('No se puede eliminar un vehículo con rutas activas', 'error')
            return redirect(url_for('listar_vehiculos'))
        
        # Verificar que no tenga rutas asociadas (programadas, completadas, etc.)
        if vehiculo.rutas:
            flash('No se puede eliminar un vehículo que tiene rutas asociadas', 'error')
            return redirect(url_for('listar_vehiculos'))
        
        db.session.delete(vehiculo)
        db.session.commit()
        
        flash(f'Vehículo "{vehiculo.placa}" eliminado exitosamente', 'success')
        return redirect(url_for('listar_vehiculos'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error eliminando vehículo {id}: {e}")
        flash('Error eliminando vehículo', 'error')
        return redirect(url_for('listar_vehiculos'))

# Función para validar estados consistentes
def validar_estados_consistentes():
    """Valida que los estados de vehículos y rutas sean consistentes"""
    try:
        # Vehículos que deberían estar "En Ruta" pero no lo están
        vehiculos_con_rutas_activas = db.session.query(Vehiculo).join(Ruta).filter(
            Ruta.estado == 'En curso',
            Vehiculo.estado != 'En Ruta'
        ).all()
        
        for vehiculo in vehiculos_con_rutas_activas:
            logger.info(f"Corrigiendo estado de vehículo {vehiculo.placa}: {vehiculo.estado} -> En Ruta")
            vehiculo.estado = 'En Ruta'
        
        # Vehículos "En Ruta" sin rutas activas
        vehiculos_en_ruta = Vehiculo.query.filter_by(estado='En Ruta').all()
        for vehiculo in vehiculos_en_ruta:
            rutas_activas = Ruta.query.filter_by(
                vehiculo_id=vehiculo.id, 
                estado='En curso'
            ).count()
            
            if rutas_activas == 0:
                logger.info(f"Corrigiendo estado de vehículo {vehiculo.placa}: En Ruta -> Disponible")
                vehiculo.estado = 'Disponible'
        
        db.session.commit()
        logger.info("Estados validados y corregidos")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error validando estados: {e}")

@app.route('/validar_estados', methods=['POST'])
def validar_estados():
    try:
        validar_estados_consistentes()
        flash('Estados validados y corregidos', 'info')
    except Exception as e:
        flash(f'Error validando estados: {str(e)}', 'error')
    return redirect(url_for('index'))

# Manejo de errores
@app.errorhandler(404)
def not_found(error):
    return f"<h1>404 - Página no encontrada</h1><p>La página que buscas no existe.</p>", 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Error interno: {error}")
    return f"<h1>500 - Error interno del servidor</h1><p>Ha ocurrido un error interno.</p>", 500

# Ruta de prueba simple
@app.route('/test')
def test():
    return {"status": "OK", "message": "La aplicación está funcionando"}

if __name__ == "__main__":
    with app.app_context():
        try:
            db.create_all()
            logger.info("Tablas creadas exitosamente")
            validar_estados_consistentes()
        except Exception as e:
            logger.error(f"Error en inicialización: {e}")
    
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)