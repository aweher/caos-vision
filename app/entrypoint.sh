#!/bin/bash

# Función para logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Iniciando Caos Vision..."

# Crear directorio de logs si no existe y es posible
if [ -w "/app" ]; then
    mkdir -p /app/logs
    log "Directorio de logs creado/verificado"
elif [ -d "/app/logs" ]; then
    log "Directorio de logs ya existe (montado como volumen)"
else
    log "⚠️ No se puede crear directorio de logs, usando solo consola"
fi

# Verificar conexión a Redis
log "Verificando conexión a Redis..."
python3 -c "
import redis
import os
import sys
try:
    r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
    r.ping()
    print('✅ Conexión a Redis exitosa')
except Exception as e:
    print(f'❌ Error conectando a Redis: {e}')
    sys.exit(1)
"

# Configurar variables para Cloudflare Tunnel
if [ "$CLOUDFLARE_TUNNEL" = "true" ]; then
    log "Configurando para Cloudflare Tunnel..."
    # No sobrescribir SESSION_COOKIE_SAMESITE aquí para evitar conflictos
    export SESSION_COOKIE_SECURE="true"
    log "Variables de Cloudflare Tunnel configuradas"
fi

# Verificar configuración del contenedor
if [ -w "/app" ]; then
    log "Contenedor en modo lectura-escritura"
else
    log "Contenedor en modo solo-lectura (recomendado para producción)"
fi

# Ejecutar aplicación
if [ "$1" = "--production" ] || [ "$FLASK_ENV" = "production" ]; then
    log "Iniciando en modo producción con Gunicorn..."
    # En producción usamos Gunicorn, no el script Python directamente
    exec gunicorn app:app \
        -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
        -w 4 \
        -b 0.0.0.0:5000 \
        --log-level info \
        --access-logfile - \
        --error-logfile - \
        --capture-output \
        --timeout 30 \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --forwarded-allow-ips "*" \
        --proxy-allow-from "*"
else
    log "Iniciando en modo desarrollo..."
    exec python app.py
fi