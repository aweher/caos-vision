# Configuración para Cloudflare Tunnel

Este documento explica cómo configurar **Caos Vision** para funcionar correctamente detrás de un **Cloudflare Tunnel**.

## ¿Qué es Cloudflare Tunnel?

Cloudflare Tunnel permite exponer aplicaciones locales a internet sin abrir puertos en el firewall, proporcionando una URL pública como `https://random-string.trycloudflare.com`.

## Configuración Requerida

### 1. Variables de Entorno

Copia `env.example` a `.env` y configura:

```bash
# Configuración específica para Cloudflare Tunnel
CLOUDFLARE_TUNNEL=true
BEHIND_PROXY=true

# Configuración de cookies (importante para tunnels)
SESSION_COOKIE_SECURE=true

# CORS - dejar vacío para URLs dinámicas
ALLOWED_ORIGINS=

# Credenciales de administrador
ADMIN_USER=tu_usuario_admin
ADMIN_PASS=tu_password_super_seguro
SESSION_SECRET_KEY=una_clave_secreta_muy_larga_y_compleja
```

### 2. Crear Directorio de Logs (Opcional)

```bash
# Crear directorio para logs persistentes
mkdir -p ./logs
chmod 755 ./logs
```

### 3. Iniciar la Aplicación

```bash
# Construir y ejecutar
docker-compose up -d

# Ver logs en tiempo real
docker-compose logs -f caos-vision
```

### 4. Configurar Cloudflare Tunnel

```bash
# Opción 1: Tunnel temporal (desarrollo)
cloudflared tunnel --url http://localhost:64500

# Opción 2: Tunnel permanente (producción)
cloudflared service install
cloudflared tunnel create caos-vision
cloudflared tunnel route dns caos-vision tu-subdominio.tu-dominio.com
cloudflared tunnel run caos-vision
```

## Características Específicas para Cloudflare

### ✅ **Configuración Automática**
- Detección automática de headers de Cloudflare (`CF-Ray`, `CF-Visitor`)
- Configuración dinámica de CORS para URLs arbitrarias
- Headers de seguridad ajustados para el entorno de Cloudflare

### 🔒 **Seguridad Adaptada**
- CSP (Content Security Policy) compatible con Cloudflare
- Cookies configuradas para funcionar a través del proxy
- Rate limiting que considera headers de Cloudflare
- Contenedor en modo solo-lectura para máxima seguridad

### 🌐 **WebSockets**
- Configuración automática de WebSocket para tunnels
- Soporte tanto para WSS como WS según el contexto
- Fallback automático polling si WebSocket falla

### 📊 **Logging Inteligente**
- Logs a consola siempre disponibles
- Logs a archivo solo si el directorio `/app/logs` es escribible
- Rotación automática de logs para evitar llenado de disco

## Solución de Problemas

### ❌ **WebSockets no funcionan**
Verifica que estés usando la URL completa del tunnel y que los logs no muestren errores de CORS.

### ❌ **Sesión no persiste**
Asegúrate de que `SESSION_COOKIE_SECURE=true` esté configurado y que estés accediendo vía HTTPS.

### ❌ **Videos no cargan**
Verifica que YouTube permite embeds desde tu dominio de Cloudflare. Algunos dominios pueden estar bloqueados.

### ❌ **Errores de "Read-only file system"**
Esto es normal - el contenedor está configurado en modo solo-lectura por seguridad. Los logs se escriben en `/app/logs` que está montado como volumen escribible.

### ❌ **Error de cookies: "TypeError: cannot use a string pattern on a bytes-like object"**
Si ves este error al intentar hacer login, es un problema de configuración de cookies. La aplicación ahora configurará automáticamente las cookies según el entorno (Cloudflare vs local).

### 🔍 **Ver logs detallados**
```bash
# Logs de la aplicación
docker-compose logs -f caos-vision

# Logs desde el archivo (si está configurado)
tail -f ./logs/app.log
```

## Configuración de Producción

Para un tunnel permanente en producción:

1. **Crear tunnel con nombre fijo:**
```bash
cloudflared tunnel create caos-vision-prod
```

2. **Configurar DNS:**
```bash
cloudflared tunnel route dns caos-vision-prod caos.tu-dominio.com
```

3. **Actualizar variables:**
```bash
ALLOWED_ORIGINS=https://caos.tu-dominio.com
```

4. **Ejecutar tunnel:**
```bash
cloudflared tunnel run caos-vision-prod
```

## Comandos Útiles

```bash
# Ver status del tunnel
cloudflared tunnel list

# Ver logs en tiempo real
docker-compose logs -f

# Reiniciar solo la aplicación
docker-compose restart caos-vision

# Verificar configuración
docker-compose config

# Verificar logs del contenedor
docker-compose exec caos-vision ls -la /app/logs/

# Acceder al contenedor para debugging
docker-compose exec caos-vision /bin/bash
```

## Arquitectura del Contenedor

### 🔒 **Seguridad**
- Usuario no-root (`appuser`)
- Sistema de archivos de solo-lectura
- Directorios temporales en tmpfs
- Políticas de seguridad estrictas

### 📁 **Estructura de Archivos**
```
/app/                 # Aplicación (solo-lectura)
├── app.py           # Código principal
├── entrypoint.sh    # Script de inicio
├── templates/       # Templates HTML
├── static/         # Archivos estáticos
└── logs/           # Logs (volumen escribible)
```

### 🔄 **Proceso de Inicio**
1. Verificación de conexión Redis
2. Configuración de logging
3. Detección de entorno Cloudflare
4. Inicio de Gunicorn con workers optimizados

## Notas Importantes

- 🔄 **URLs Dinámicas**: Los tunnels temporales cambian de URL en cada restart
- 🍪 **Cookies**: Configuradas como `SameSite=None` para compatibilidad
- 🔐 **HTTPS**: Cloudflare maneja automáticamente el SSL/TLS
- 📡 **Headers**: La aplicación detecta automáticamente si está detrás de Cloudflare
- 🛡️ **Seguridad**: Contenedor optimizado para producción con modo solo-lectura 