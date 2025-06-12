import os
import re
import hashlib
from base64 import b64encode
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
# Comentar Flask-Session temporalmente para usar sesiones nativas
# from flask_session import Session
from flask_socketio import SocketIO, emit
import redis
import logging
from logging.handlers import RotatingFileHandler
import time
import json
import requests

app = Flask(__name__)

# Configurar logging de forma más robusta
log_handlers = [logging.StreamHandler()]  # Siempre log a consola

# Intentar configurar log a archivo si el directorio existe y es escribible
try:
    log_dir = '/app/logs'
    if os.path.exists(log_dir) and os.access(log_dir, os.W_OK):
        log_handlers.append(
            RotatingFileHandler(
                os.path.join(log_dir, 'app.log'), 
                maxBytes=100000, 
                backupCount=3
            )
        )
        print(f"✅ Logging configurado en {log_dir}/app.log")
    else:
        print("⚠️ Directorio de logs no disponible, usando solo consola")
except Exception as e:
    print(f"⚠️ No se pudo configurar logging a archivo: {e}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# Configuración simplificada para evitar problemas con Flask-Session
app.config.update(
    SECRET_KEY=os.getenv('SESSION_SECRET_KEY', 'dev-secret-key'),
    # Usar sesiones nativas de Flask temporalmente
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',  # Usar Lax para evitar problemas
    PERMANENT_SESSION_LIFETIME=3600  # 1 hora
)

# Configurar Redis
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
r = redis.Redis.from_url(redis_url, decode_responses=True)

# Comentar inicialización de Flask-Session
# Session(app)

# Log de configuración
logger.info(f"Configuración de cookies: SESSION_COOKIE_SECURE={app.config['SESSION_COOKIE_SECURE']}, SESSION_COOKIE_SAMESITE={app.config['SESSION_COOKIE_SAMESITE']}")

# Configurar CORS de forma segura
# Para Cloudflare Tunnel, permitir orígenes dinámicos basados en headers
def get_allowed_origins():
    """Obtener orígenes permitidos dinámicamente para Cloudflare Tunnel"""
    env_origins = os.getenv('ALLOWED_ORIGINS', '')
    origins = []
    
    if env_origins:
        origins.extend(env_origins.split(','))
    
    # Para desarrollo local
    origins.extend(['http://localhost:5000', 'http://127.0.0.1:5000'])
    
    # Para Cloudflare Tunnel - detectar automáticamente
    # Cloudflare usa headers específicos
    return origins

allowed_origins = get_allowed_origins()
socketio = SocketIO(app, 
                   cors_allowed_origins="*",  # Cloudflare Tunnel requiere esto
                   engineio_logger=False,
                   async_mode='gevent',
                   cookie='auth_token',
                   manage_session=False)

# Configuración de seguridad
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASS_HASH = hashlib.sha256(
    os.getenv('ADMIN_PASS', 'admin123').encode()
).hexdigest()

# Rate limiting simple en memoria (en producción usar Redis)
login_attempts = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 300  # 5 minutos

# Funciones para manejar sesiones con Redis
def save_session_to_redis(session_id, data, expiry=3600):
    """Guardar datos de sesión en Redis"""
    try:
        r.setex(f"session:{session_id}", expiry, json.dumps(data))
        return True
    except Exception as e:
        logger.error(f"Error guardando sesión en Redis: {e}")
        return False

def load_session_from_redis(session_id):
    """Cargar datos de sesión desde Redis"""
    try:
        data = r.get(f"session:{session_id}")
        if data:
            return json.loads(data)
        return {}
    except Exception as e:
        logger.error(f"Error cargando sesión desde Redis: {e}")
        return {}

def delete_session_from_redis(session_id):
    """Eliminar sesión de Redis"""
    try:
        r.delete(f"session:{session_id}")
        return True
    except Exception as e:
        logger.error(f"Error eliminando sesión de Redis: {e}")
        return False

# Decorador de autenticación mejorado
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar si hay session ID
        if 'session_id' not in session:
            return redirect(url_for('login', next=request.url))
        
        # Verificar sesión en Redis
        session_data = load_session_from_redis(session['session_id'])
        if not session_data.get('authenticated'):
            session.clear()
            return redirect(url_for('login', next=request.url))
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        
        # Rate limiting
        current_time = int(time.time())
        if client_ip in login_attempts:
            attempts, last_attempt = login_attempts[client_ip]
            if attempts >= MAX_LOGIN_ATTEMPTS and current_time - last_attempt < LOCKOUT_TIME:
                remaining_time = LOCKOUT_TIME - (current_time - last_attempt)
                return render_template('login.html', 
                    error=f'Demasiados intentos. Intenta en {remaining_time//60} minutos')
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validaciones básicas
        if not username or not password:
            return render_template('login.html', error='Usuario y contraseña requeridos')
        
        if len(username) > 50 or len(password) > 100:
            return render_template('login.html', error='Credenciales inválidas')
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if username == ADMIN_USER and password_hash == ADMIN_PASS_HASH:
            # Crear session ID único
            session_id = hashlib.sha256(f"{username}{current_time}{os.urandom(16)}".encode()).hexdigest()
            
            # Guardar en sesión de Flask (simple)
            session['session_id'] = session_id
            session.permanent = True
            
            # Guardar datos de sesión en Redis
            session_data = {
                'authenticated': True,
                'username': username,
                'login_time': current_time
            }
            save_session_to_redis(session_id, session_data)
            
            # Limpiar intentos fallidos
            login_attempts.pop(client_ip, None)
            logger.info(f"Login exitoso para usuario: {username}")
            return redirect(url_for('admin'))
        
        # Registrar intento fallido
        if client_ip in login_attempts:
            attempts, _ = login_attempts[client_ip]
            login_attempts[client_ip] = (attempts + 1, current_time)
        else:
            login_attempts[client_ip] = (1, current_time)
        
        logger.warning(f"Intento de login fallido para usuario: {username} desde IP: {client_ip}")
        return render_template('login.html', error='Credenciales inválidas')
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'session_id' in session:
        delete_session_from_redis(session['session_id'])
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

# API Endpoints
@app.route('/api/streams', methods=['GET', 'POST'])
@login_required
def handle_streams():
    if request.method == 'GET':
        return jsonify(get_all_streams()), 200
    elif request.method == 'POST':
        return add_stream()

@app.route('/api/streams/<stream_id>', methods=['DELETE'])
@login_required
def remove_stream(stream_id):
    # Validar stream_id
    if not stream_id or not isinstance(stream_id, str) or len(stream_id) != 11:
        return jsonify({'error': 'ID de stream inválido'}), 400
    
    try:
        stream_key = f"stream:{stream_id}"
        if r.exists(stream_key):
            r.delete(stream_key)
            update_clients()
            return jsonify({'message': 'Stream eliminado'}), 200
        else:
            return jsonify({'error': 'Stream no encontrado'}), 404
    except redis.RedisError as e:
        logger.error(f"Error Redis al eliminar stream {stream_id}: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/streams/<stream_id>/mute', methods=['POST'])
@login_required
def toggle_mute(stream_id):
    # Validar stream_id
    if not stream_id or not isinstance(stream_id, str) or len(stream_id) != 11:
        return jsonify({'error': 'ID de stream inválido'}), 400
    
    try:
        stream_key = f"stream:{stream_id}"
        if not r.exists(stream_key):
            return jsonify({'error': 'Stream no encontrado'}), 404
            
        current_mute = r.hget(stream_key, 'muted') or 'true'
        new_mute = 'false' if current_mute == 'true' else 'true'
        r.hset(stream_key, 'muted', new_mute)
        update_clients()
        return jsonify({'message': 'Sonido actualizado', 'muted': new_mute == 'true'}), 200
    except redis.RedisError as e:
        logger.error(f"Error Redis al cambiar mute {stream_id}: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

# Funciones auxiliares
def get_all_streams():
    streams = []
    try:
        for key in r.scan_iter("stream:*"):
            try:
                stream_data = r.hgetall(key)
                if stream_data and 'id' in stream_data and 'url' in stream_data:
                    streams.append({
                        'id': stream_data['id'],
                        'url': stream_data['url'],
                        'title': stream_data.get('title', f"Video {stream_data['id']}"),
                        'muted': stream_data.get('muted', 'true') == 'true'
                    })
            except Exception as e:
                logger.warning(f"Error procesando stream {key}: {e}")
                continue
    except redis.RedisError as e:
        logger.error(f"Error Redis obteniendo streams: {e}")
    return streams

def calculate_layout(stream_count):
    if stream_count == 0:
        return [0, 0]
    sqrt = int(stream_count ** 0.5)
    return [sqrt + (1 if sqrt * sqrt < stream_count else 0), sqrt]

def extract_youtube_id(url):
    patterns = [
        r'(?:v=|be\/|embed\/|shorts\/)([a-zA-Z0-9_-]{11})',
        r'\/live\/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_title(video_id):
    """Obtener el título de un video de YouTube usando la API oEmbed"""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(oembed_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('title', f'Video {video_id}')
    except Exception as e:
        logger.warning(f"Error obteniendo título para video {video_id}: {e}")
    
    return f'Video {video_id}'

def add_stream():
    # Validación de entrada mejorada
    if not request.json:
        return jsonify({'error': 'JSON inválido'}), 400
    
    url = request.json.get('url')
    if not url or not isinstance(url, str):
        return jsonify({'error': 'URL requerida y debe ser string'}), 400
    
    # Sanitizar URL
    url = url.strip()
    if len(url) > 500:  # Prevenir URLs excesivamente largas
        return jsonify({'error': 'URL demasiado larga'}), 400
    
    video_id = extract_youtube_id(url)
    
    if not video_id:
        return jsonify({'error': 'URL de YouTube inválida'}), 400
    
    try:
        stream_key = f"stream:{video_id}"
        if not r.exists(stream_key):
            # Obtener título del video
            title = get_youtube_title(video_id)
            
            r.hset(stream_key, mapping={
                'id': video_id,
                'url': f'https://youtube.com/embed/{video_id}',
                'title': title,
                'muted': 'true'
            })
            logger.info(f"Stream agregado: {video_id} - {title}")
        else:
            # Si el stream ya existe pero no tiene título, agregarlo
            if not r.hget(stream_key, 'title'):
                title = get_youtube_title(video_id)
                r.hset(stream_key, 'title', title)
                logger.info(f"Título agregado a stream existente: {video_id} - {title}")
        
        update_clients()
        return jsonify({'message': 'Stream agregado'}), 201
    except redis.RedisError as e:
        logger.error(f"Error Redis al agregar stream: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

def update_clients():
    try:
        streams = get_all_streams()
        logger.info(f"Emitiendo update para {len(streams)} streams")
        layout = calculate_layout(len(streams))
        socketio.emit('update', {'streams': streams, 'layout': layout})
    except Exception as e:
        logger.error(f"Error actualizando clientes: {e}")

@app.context_processor
def inject_nonce():
    return {'csp_nonce': b64encode(os.urandom(16)).decode('utf-8')}

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
    # Verificar autenticación para WebSocket
    if 'session_id' in session:
        session_data = load_session_from_redis(session['session_id'])
        if session_data.get('authenticated'):
            emit('update', {'streams': get_all_streams(), 'layout': calculate_layout(len(get_all_streams()))})
        else:
            logger.warning("Intento de conexión WebSocket sin autenticación válida")
    else:
        logger.warning("Intento de conexión WebSocket sin session_id")

@app.before_request
def handle_cloudflare_headers():
    """Manejar headers específicos de Cloudflare"""
    # Cloudflare pasa el protocolo original
    if request.headers.get('CF-Visitor'):
        try:
            cf_visitor = json.loads(request.headers.get('CF-Visitor', '{}'))
            if cf_visitor.get('scheme') == 'https':
                request.environ['wsgi.url_scheme'] = 'https'
        except:
            pass
    
    # Detectar si estamos detrás de Cloudflare
    if request.headers.get('CF-Ray'):
        request.environ['behind_cloudflare'] = True

@app.before_request
def check_auth():
    public_routes = ['/', '/login', '/static/styles.css']
    if not request.path.startswith(tuple(public_routes)):
        # Verificar autenticación
        authenticated = False
        if 'session_id' in session:
            session_data = load_session_from_redis(session['session_id'])
            authenticated = session_data.get('authenticated', False)
        
        if not authenticated:
            if request.path.startswith('/api'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login'))

@app.after_request
def add_security_headers(response):
    # Detectar si estamos detrás de Cloudflare
    behind_cloudflare = request.environ.get('behind_cloudflare', False)
    is_secure = request.is_secure or behind_cloudflare or request.headers.get('X-Forwarded-Proto') == 'https'
    
    # Configurar CSP dinámicamente para Cloudflare Tunnel
    if behind_cloudflare:
        # Para Cloudflare Tunnel, ser más permisivo con WebSockets
        ws_connect = "connect-src 'self' wss: ws:;"
    else:
        # Configuración local/tradicional
        ws_protocol = 'wss' if is_secure else 'ws'
        host = request.host
        ws_connect = f"connect-src 'self' {ws_protocol}://{host};"
    
    csp_policy = (
        f"default-src 'none';"
        f"script-src 'self' https://cdn.socket.io https://analytics.arreg.la 'unsafe-inline';"  # Added Matomo domain
        f"{ws_connect}"
        "style-src 'self' 'unsafe-inline';"
        "img-src 'self' data: https://i.ytimg.com;"
        "frame-src 'self' https://www.youtube.com https://youtube.com https://www.youtube-nocookie.com;"
        "font-src 'self';"
        "form-action 'self';"
        "base-uri 'self';"
        "object-src 'none';"
        "frame-ancestors 'none';"
        "connect-src 'self' https://analytics.arreg.la;"  # Added Matomo domain for analytics
    )
    
    # Headers básicos de seguridad
    security_headers = {
        'Content-Security-Policy': csp_policy,
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }
    
    # Ajustar headers según el entorno
    if behind_cloudflare:
        # Cloudflare maneja algunos headers automáticamente
        security_headers['X-Frame-Options'] = 'SAMEORIGIN'  # Más flexible para Cloudflare
    else:
        security_headers['X-Frame-Options'] = 'DENY'
    
    response.headers.update(security_headers)
    return response

if __name__ == '__main__':
    try:
        r.ping()
        logger.info("✅ Conexión a Redis exitosa")
        socketio.run(app, 
                   host='0.0.0.0', 
                   debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
                   allow_unsafe_werkzeug=True)
    except redis.ConnectionError:
        logger.info("❌ Error de conexión con Redis")
        exit(1)