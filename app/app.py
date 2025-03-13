import os
import re
import hashlib
from base64 import b64encode
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_session import Session
from flask_socketio import SocketIO, emit
import redis

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv('SESSION_SECRET_KEY', 'dev-secret-key'),
    SESSION_TYPE='redis',
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_REDIS=redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0')),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# Configurar Redis
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
r = redis.Redis.from_url(redis_url, decode_responses=True)
Session(app)
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   engineio_logger=False,
                   async_mode='gevent',
                   cookie='auth_token',
                   manage_session=False)

# Configuración de seguridad
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASS_HASH = hashlib.sha256(
    os.getenv('ADMIN_PASS', 'admin123').encode()
).hexdigest()

# Decorador de autenticación
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if username == ADMIN_USER and password_hash == ADMIN_PASS_HASH:
            session['authenticated'] = True
            session.permanent = True
            return redirect(url_for('admin'))
        
        return render_template('login.html', error='Credenciales inválidas')
    return render_template('login.html')

@app.route('/logout')
def logout():
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
    r.delete(f"stream:{stream_id}")
    update_clients()
    return jsonify({'message': 'Stream eliminado'}), 200

@app.route('/api/streams/<stream_id>/mute', methods=['POST'])
@login_required
def toggle_mute(stream_id):
    stream_key = f"stream:{stream_id}"
    current_mute = r.hget(stream_key, 'muted') or 'true'
    new_mute = 'false' if current_mute == 'true' else 'true'
    r.hset(stream_key, 'muted', new_mute)
    update_clients()
    return jsonify({'message': 'Sonido actualizado'}), 200

# Funciones auxiliares
def get_all_streams():
    streams = []
    for key in r.scan_iter("stream:*"):
        stream_data = r.hgetall(key)
        streams.append({
            'id': stream_data['id'],
            'url': stream_data['url'],
            'muted': stream_data.get('muted', 'true') == 'true'
        })
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

def add_stream():
    url = request.json.get('url')
    video_id = extract_youtube_id(url)
    
    if not video_id:
        return jsonify({'error': 'URL inválida'}), 400
    
    stream_key = f"stream:{video_id}"
    if not r.exists(stream_key):
        r.hset(stream_key, mapping={
            'id': video_id,
            'url': f'https://youtube.com/embed/{video_id}',
            'muted': 'true'
        })
    print(f"[DEBUG] Stream agregado: {video_id}")
    update_clients()
    return jsonify({'message': 'Stream agregado'}), 201

def update_clients():
    streams = get_all_streams()
    print(f"[DEBUG] Emitiendo update para {len(streams)} streams")
    layout = calculate_layout(len(streams))
    socketio.emit('update', {'streams': streams, 'layout': layout})

@app.context_processor
def inject_nonce():
    return {'csp_nonce': b64encode(os.urandom(16)).decode('utf-8')}

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
    if session.get('authenticated'):
        emit('update', {'streams': get_all_streams(), 'layout': calculate_layout(len(get_all_streams()))})

@app.before_request
def check_auth():
    public_routes = ['/', '/login', '/static/styles.css']
    if not request.path.startswith(tuple(public_routes)) and not session.get('authenticated'):
        if request.path.startswith('/api'):
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect(url_for('login'))

@app.after_request
def add_security_headers(response):
    csp_nonce = b64encode(os.urandom(16)).decode('utf-8')
    csp_policy = (
        f"default-src 'none';"
        f"script-src 'self' https://cdn.socket.io 'nonce-{csp_nonce}';"
        "connect-src 'self' ws://localhost:5000;"
        "style-src 'self' 'unsafe-inline';"
        "img-src 'self' data: https://i.ytimg.com;"
        "frame-src https://www.youtube.com;"
        "font-src 'self';"
        "form-action 'self';"
        "base-uri 'self';"
        "object-src 'none';"
        "frame-ancestors 'none';"
    )
    response.headers['Content-Security-Policy'] = csp_policy
    return response

if __name__ == '__main__':
    try:
        r.ping()
        print("✅ Conexión a Redis exitosa")
        socketio.run(app, 
                   host='0.0.0.0', 
                   debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
                   allow_unsafe_werkzeug=True)
    except redis.ConnectionError:
        print("❌ Error de conexión con Redis")
        exit(1)