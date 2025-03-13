from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import re
import redis
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Configurar conexión a Valkey
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
r = redis.Redis.from_url(redis_url, decode_responses=True)
try:
    r.ping()
    print("✅ Conexión a Redis exitosa")
except redis.ConnectionError:
    print("❌ No se pudo conectar a Redis")
    exit(1)

def calculate_layout(stream_count):
    if stream_count == 0:
        return []
    rows = int(stream_count**0.5)
    cols = rows if rows * rows == stream_count else rows + 1
    return [rows, cols]

def extract_youtube_id(url):
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@socketio.on('connect')
def handle_connect():
    streams = get_all_streams()
    current_layout = calculate_layout(len(streams))
    emit('update', {'streams': streams, 'layout': current_layout})

def get_all_streams():
    streams = []
    try:
        for key in r.scan_iter("stream:*"):
            stream_data = r.hgetall(key)
            # Convertir string a booleano
            streams.append({
                'id': stream_data['id'],
                'url': stream_data['url'],
                'muted': stream_data.get('muted', 'true').lower() == 'true'
            })
    except redis.RedisError as e:
        print(f"Error al obtener streams: {str(e)}")
    return streams

@app.route('/api/streams', methods=['POST'])
def add_stream():
    url = request.json.get('url')
    video_id = extract_youtube_id(url)
    
    if not video_id:
        return jsonify({'error': 'URL de YouTube inválida'}), 400
    
    stream_key = f"stream:{video_id}"
    try:
        # Convertir valores booleanos a strings
        r.hset(stream_key, mapping={
            'id': video_id,
            'url': f'https://youtube.com/embed/{video_id}',
            'muted': 'true'  # Usar string en lugar de bool
        })
    except redis.RedisError as e:
        return jsonify({'error': f'Error en Redis: {str(e)}'}), 500
    
    streams = get_all_streams()
    current_layout = calculate_layout(len(streams))
    socketio.emit('update', {'streams': streams, 'layout': current_layout})
    return jsonify({'message': 'Stream agregado'}), 201

@app.route('/api/streams/<stream_id>', methods=['DELETE'])
def remove_stream(stream_id):
    r.delete(f"stream:{stream_id}")
    
    streams = get_all_streams()
    current_layout = calculate_layout(len(streams))
    socketio.emit('update', {'streams': streams, 'layout': current_layout})
    return jsonify({'message': 'Stream eliminado'}), 200

@app.route('/api/streams/<stream_id>/mute', methods=['POST'])
def toggle_mute(stream_id):
    stream_key = f"stream:{stream_id}"
    current_mute = r.hget(stream_key, 'muted')
    new_mute = 'False' if current_mute == 'True' else 'True'
    r.hset(stream_key, 'muted', new_mute)
    
    streams = get_all_streams()
    socketio.emit('update', {'streams': streams})
    return jsonify({'message': 'Sonido actualizado'}), 200

@app.route('/api/streams', methods=['GET'])
def get_streams():
    return jsonify(get_all_streams()), 200

if __name__ == '__main__':
    socketio.run(app, 
                 host='0.0.0.0', 
                 debug=False,  # Cambiar a False en producción
                 allow_unsafe_werkzeug=True)  # Añadir este parámetro