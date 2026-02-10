# Configuracion para Cloudflare Tunnel

Este documento explica como configurar **Caos Vision** para funcionar correctamente detras de un **Cloudflare Tunnel**.

## Que es Cloudflare Tunnel?

Cloudflare Tunnel permite exponer aplicaciones locales a internet sin abrir puertos en el firewall, proporcionando una URL publica segura con SSL/TLS automatico.

## Arquitectura con Cloudflare

Caos Vision utiliza dos servicios separados que pueden exponerse a traves de tunnels independientes:

```
Internet
    │
    ▼
Cloudflare Edge (SSL/TLS)
    │
    ├──► cloudflared tunnel (viewer)
    │        │
    │        ▼
    │    localhost:64500  ──► Docker: caos-viewer (FastAPI/Uvicorn)
    │                                    │
    │                                    ▼
    │                              Docker: valkey (Redis)
    │                                    ▲
    └──► cloudflared tunnel (admin)      │
             │                           │
             ▼                           │
         localhost:64501  ──► Docker: caos-admin (FastAPI/Uvicorn)
```

> **Nota:** Si solo necesitas exponer el visor publicamente, puedes crear un tunnel unicamente para el puerto 64500. El admin puede quedarse accesible solo en la red local.

## Configuracion con run.sh

### 1. Ejecutar el wizard

```bash
./run.sh
```

Cuando el script pregunte:
- **Is this behind a reverse proxy?** -> `y`
- **Are you using Cloudflare Tunnel?** -> `y`
- **Allowed origins** -> `*` (o tus dominios especificos separados por coma)

### 2. Iniciar la aplicacion

```bash
./run.sh --start
```

### 3. Crear el tunnel

**Tunnel temporal (desarrollo):**
```bash
# Exponer solo el viewer
cloudflared tunnel --url http://localhost:64500

# O exponer el admin (en otro terminal)
cloudflared tunnel --url http://localhost:64501
```

**Tunnel permanente (produccion):**
```bash
# Crear tunnels
cloudflared tunnel create caos-vision-viewer
cloudflared tunnel create caos-vision-admin

# Configurar DNS
cloudflared tunnel route dns caos-vision-viewer caos.tu-dominio.com
cloudflared tunnel route dns caos-vision-admin admin-caos.tu-dominio.com

# Ejecutar (ver seccion de configuracion de produccion mas abajo)
```

## Configuracion Manual

Si prefieres configurar manualmente, edita `.env`:

```bash
# Habilitar deteccion de Cloudflare
CLOUDFLARE_TUNNEL=true
BEHIND_PROXY=true

# CORS - dejar * para URLs dinamicas o especificar dominios
ALLOWED_ORIGINS=*

# Credenciales
ADMIN_USER=tu_usuario
ADMIN_PASS=tu_password_seguro
SECRET_KEY=clave_secreta_minimo_32_caracteres

# URL del viewer (mostrada en la pagina de login del admin)
VIEWER_URL=https://caos.tu-dominio.com
```

## Caracteristicas para Cloudflare

### Deteccion Automatica
La aplicacion detecta automaticamente cuando esta detras de Cloudflare verificando la presencia del header `CF-Ray`:
- **CSP**: Se ajusta `frame-ancestors` para permitir el comportamiento correcto
- **X-Frame-Options**: Cambia de `DENY` a `SAMEORIGIN`
- **IP del cliente**: Se extrae de `CF-Connecting-IP` en lugar de la IP directa

### Seguridad
- Content Security Policy con nonces para scripts, compatible con Cloudflare
- Cookies de sesion configuradas con `secure=true` (funciona con HTTPS de Cloudflare)
- Rate limiting considera la IP real del cliente via headers de Cloudflare
- Proteccion CSRF con patron double-submit cookie
- Contenedor Docker en modo solo-lectura con usuario no-root

### WebSockets
- Configuracion automatica WSS/WS segun protocolo detectado por el cliente
- Soporte completo a traves del proxy de Cloudflare
- Reconexion automatica con backoff exponencial y jitter
- Health check con ping/pong (timeout configurable)
- WebSocket viewer (publico) y admin (autenticado) en endpoints separados

### Extraccion de IP del Cliente
La aplicacion extrae la IP real del cliente en este orden de prioridad:
1. `CF-Connecting-IP` (header de Cloudflare)
2. `X-Real-IP` (reverse proxy generico)
3. `X-Forwarded-For` (primer IP de la cadena)
4. IP directa del socket (fallback)

## Solucion de Problemas

### WebSockets no funcionan

Verificar logs:
```bash
docker compose logs -f caos-viewer | grep -i websocket
docker compose logs -f caos-admin | grep -i websocket
```

Causas comunes:
- Cloudflare no tiene WebSockets habilitado (verificar en dashboard > Network)
- El plan gratuito de Cloudflare soporta WebSockets
- Timeout de conexion: Cloudflare cierra conexiones inactivas despues de 100 segundos (la app envia pings cada 25 segundos para prevenir esto)

### Sesion no persiste

Verificar:
1. `CLOUDFLARE_TUNNEL=true` esta configurado en `.env`
2. Se accede via HTTPS (Cloudflare maneja SSL automaticamente)
3. Redis/Valkey esta funcionando:
```bash
docker compose exec valkey valkey-cli ping
```
4. Las cookies no estan siendo bloqueadas por el navegador (verificar DevTools > Application > Cookies)

### Videos no cargan

- Verificar que la plataforma permite embeds desde tu dominio
- YouTube puede bloquear ciertos dominios de Cloudflare con URLs temporales
- Twitch requiere que el dominio parent este configurado correctamente (se configura automaticamente basado en el header `Host`)
- Verificar los headers CSP en DevTools > Network > Response Headers

### Error de CSRF en login

Si hay errores 403 al intentar login:
- Verificar que `CLOUDFLARE_TUNNEL=true` y `BEHIND_PROXY=true` estan configurados
- Las cookies CSRF necesitan funcionar correctamente a traves del proxy
- Verificar que no haya cache agresivo en Cloudflare para las rutas de la API

### Error de cookies

Si las cookies de sesion no se establecen:
- Asegurarse de acceder via HTTPS (las cookies tienen `secure=true` en produccion)
- Verificar que `SameSite` no este causando problemas con el dominio
- En `DEBUG=true`, las cookies se envian sin `secure` para desarrollo local

## Configuracion de Produccion

### 1. Crear tunnels permanentes
```bash
cloudflared tunnel create caos-vision-viewer
cloudflared tunnel create caos-vision-admin
```

### 2. Configurar DNS
```bash
cloudflared tunnel route dns caos-vision-viewer caos.tu-dominio.com
cloudflared tunnel route dns caos-vision-admin admin-caos.tu-dominio.com
```

### 3. Actualizar configuracion

Editar `.env`:
```bash
CLOUDFLARE_TUNNEL=true
BEHIND_PROXY=true
ALLOWED_ORIGINS=https://caos.tu-dominio.com,https://admin-caos.tu-dominio.com
VIEWER_URL=https://caos.tu-dominio.com
```

### 4. Crear archivo de configuracion de cloudflared

```yaml
# ~/.cloudflared/config.yml
tunnel: caos-vision-viewer
credentials-file: ~/.cloudflared/VIEWER_TUNNEL_ID.json

ingress:
  - hostname: caos.tu-dominio.com
    service: http://localhost:64500
  - hostname: admin-caos.tu-dominio.com
    service: http://localhost:64501
  - service: http_status:404
```

> **Alternativa:** Si prefieres usar un solo dominio, puedes usar un unico tunnel con rutas diferentes. Sin embargo, dado que viewer y admin son aplicaciones separadas en puertos distintos, la configuracion con dos hostnames es mas clara.

### 5. Ejecutar como servicio del sistema
```bash
cloudflared service install
```

## Comandos Utiles

```bash
# Ver status del tunnel
cloudflared tunnel list

# Ver info de un tunnel especifico
cloudflared tunnel info caos-vision-viewer

# Ver logs de la aplicacion
./run.sh --logs

# Logs individuales
docker compose logs -f caos-viewer
docker compose logs -f caos-admin

# Reiniciar aplicacion
./run.sh --restart

# Ver configuracion Docker resultante
docker compose config

# Verificar Redis/Valkey
docker compose exec valkey valkey-cli ping

# Ver datos almacenados
docker compose exec valkey valkey-cli HGETALL caos:streams

# Health check del viewer
curl http://localhost:64500/api/v1/health/ready

# Health check del admin
curl http://localhost:64501/api/v1/health/ready
```

## Notas Importantes

- **URLs Dinamicas**: Los tunnels temporales (`cloudflared tunnel --url`) cambian de URL en cada reinicio. Para produccion, usar tunnels permanentes.
- **HTTPS**: Cloudflare maneja automaticamente SSL/TLS. Las cookies de sesion se configuran con `secure=true` automaticamente cuando `DEBUG=false`.
- **Headers**: La aplicacion detecta automaticamente el entorno Cloudflare via el header `CF-Ray`.
- **Seguridad**: Los contenedores estan optimizados para produccion con modo solo-lectura (`read_only: true`), usuario no-root, y `no-new-privileges`.
- **Plataformas**: YouTube, Twitch y Vimeo funcionan correctamente a traves del tunnel. Para Twitch, el dominio parent se extrae del header `Host` automaticamente.
- **Dos servicios**: Recuerda que viewer (64500) y admin (64501) son aplicaciones independientes. Puedes exponer solo el viewer publicamente y mantener el admin en la red local.
