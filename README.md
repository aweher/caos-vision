# Caos Vision

**Caos Vision** es una aplicacion web que permite crear un **muro de videos** donde se pueden visualizar multiples streams simultaneamente en una grilla dinamica. Soporta **YouTube, Twitch y Vimeo**. Perfecto para monitoreo de eventos, entretenimiento o vigilancia de contenido.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.109+-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Caracteristicas Principales

### Gestion de Streams
- Soporte para **YouTube** (videos, lives, shorts, embeds)
- Soporte para **Twitch** (canales en vivo, VODs)
- Soporte para **Vimeo** (videos)
- Extraccion automatica de metadatos via oEmbed (titulo, thumbnail, autor)
- Grilla responsive que se ajusta automaticamente segun cantidad de streams
- Control individual de sonido (mute/unmute)
- Deteccion de duplicados antes de agregar streams

### Seguridad
- Panel de administracion protegido con autenticacion por sesion
- Proteccion CSRF con patron double-submit cookie
- Rate limiting por IP para prevenir ataques de fuerza bruta
- Sesiones persistentes en Redis con expiracion configurable
- Hashing de passwords con bcrypt + comparacion en tiempo constante
- Headers de seguridad (CSP con nonces, X-Frame-Options, Referrer-Policy, Permissions-Policy)
- Contenedor Docker en modo solo-lectura con usuario no-root

### Tiempo Real
- Actualizaciones instantaneas via WebSockets nativos
- WebSocket separado para viewers (publico) y admins (autenticado)
- Reconexion automatica con backoff exponencial y jitter
- Health check de conexion con ping/pong
- Sincronizacion entre multiples clientes
- Sin necesidad de recargar la pagina

### Arquitectura Dual
- **Viewer** (publico): Muestra la grilla de videos sin autenticacion
- **Admin** (privado): Panel de gestion con autenticacion requerida
- Ambas aplicaciones comparten la misma base de datos Redis/Valkey
- Cada una se ejecuta como un contenedor independiente

### Cloudflare Tunnel Ready
- Configuracion automatica para tunnels
- Deteccion de headers Cloudflare (CF-Ray, CF-Connecting-IP)
- CORS dinamico para origenes configurables
- WebSocket compatible con proxies

## Instalacion Rapida

### Prerrequisitos
- Docker y Docker Compose

### Opcion 1: Script Interactivo (Recomendado)

```bash
git clone https://github.com/aweher/caos-vision.git
cd caos-vision
./run.sh
```

El script te guiara para configurar:
- Credenciales de administrador
- Clave secreta (generada automaticamente)
- Puerto de exposicion
- Configuracion de proxy/tunnel

### Opcion 2: Configuracion Manual

```bash
git clone https://github.com/aweher/caos-vision.git
cd caos-vision

# Copiar y editar configuracion
cp env.example .env
# Editar .env con tus valores

# Iniciar
docker compose up -d
```

### Acceder a la Aplicacion

| URL | Descripcion |
|-----|-------------|
| `http://localhost:64500/` | Visor publico (para TV/browser) |
| `http://localhost:64501/admin` | Panel de administracion |
| `http://localhost:64501/login` | Pagina de login del admin |

> **Nota:** El visor y el admin corren como servicios separados en puertos distintos.  
> El visor escucha en el puerto **64500** y el admin en el puerto **64501**.

## Comandos del Script

```bash
./run.sh              # Wizard completo de configuracion
./run.sh --configure  # Solo configurar (sin iniciar)
./run.sh --start      # Iniciar servicios
./run.sh --dev        # Modo desarrollo con live reload
./run.sh --stop       # Detener servicios
./run.sh --restart    # Reiniciar servicios
./run.sh --logs       # Ver logs en tiempo real
./run.sh --status     # Ver estado de los servicios
./run.sh --help       # Mostrar ayuda
```

## Configuracion

### Variables de Entorno

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `DEBUG` | `false` | Habilita modo debug y docs de API (`/api/docs`) |
| `SECRET_KEY` | `change-me-in-production` | Clave secreta para firmas y tokens |
| `REDIS_URL` | `redis://localhost:6379/0` | URL de conexion a Redis/Valkey |
| `ADMIN_USER` | `admin` | Nombre de usuario del administrador |
| `ADMIN_PASS` | `admin` | Password del administrador |
| `SESSION_EXPIRE_SECONDS` | `3600` | Tiempo de expiracion de sesion (segundos) |
| `ALLOWED_ORIGINS` | `*` | Origenes CORS permitidos (separados por coma) |
| `RATE_LIMIT_ATTEMPTS` | `5` | Intentos de login antes de bloqueo |
| `RATE_LIMIT_WINDOW` | `300` | Ventana de rate limit (segundos) |
| `CLOUDFLARE_TUNNEL` | `false` | Habilitar soporte para Cloudflare Tunnel |
| `BEHIND_PROXY` | `false` | Indica si esta detras de un reverse proxy |
| `VIEWER_URL` | _(vacio)_ | URL del visor (mostrada en la pagina de login del admin) |
| `HOST` | `0.0.0.0` | Host de escucha |
| `PORT` | `8000` | Puerto interno del contenedor |
| `WORKERS` | `4` | Cantidad de workers de Uvicorn |

## Uso con Cloudflare Tunnel

### Tunnel Temporal (Desarrollo)
```bash
./run.sh --start
cloudflared tunnel --url http://localhost:64500
```

### Tunnel Permanente (Produccion)
```bash
cloudflared tunnel create caos-vision-prod
cloudflared tunnel route dns caos-vision-prod caos.tu-dominio.com
cloudflared tunnel run caos-vision-prod
```

Ver [CLOUDFLARE_SETUP.md](CLOUDFLARE_SETUP.md) para documentacion completa.

## Guia de Uso

### Como Administrador

1. Acceder a `http://localhost:64501/login` e iniciar sesion
2. Pegar URL de video en el campo de texto
3. Click en "Add Stream"

**URLs soportadas:**
- YouTube: `youtube.com/watch?v=...`, `youtu.be/...`, `youtube.com/live/...`, `youtube.com/shorts/...`, `youtube.com/embed/...`
- Twitch: `twitch.tv/canal`, `twitch.tv/videos/123`
- Vimeo: `vimeo.com/123456`, `player.vimeo.com/video/123456`

### Como Viewer

1. Abrir la URL del visor (`http://localhost:64500/`)
2. Los videos se muestran automaticamente en una grilla adaptativa
3. Los cambios del admin se reflejan en tiempo real via WebSocket
4. Sin necesidad de autenticacion

## Arquitectura

### Stack Tecnologico
- **Backend**: Python 3.11, FastAPI 0.109+, Pydantic v2, WebSockets nativos
- **Frontend**: HTML5, JavaScript vanilla, CSS3, Jinja2 templates
- **Base de datos**: Valkey 7 (compatible con Redis)
- **Web Server**: Uvicorn con workers
- **Contenedor**: Docker multi-stage, multi-arquitectura (amd64/arm64)
- **Seguridad**: bcrypt, itsdangerous, CSP con nonces

### Estructura del Proyecto
```
caos-vision/
├── app/
│   ├── __init__.py
│   ├── admin_main.py              # Entry point del Admin (FastAPI app)
│   ├── viewer_main.py             # Entry point del Viewer (FastAPI app)
│   ├── config.py                  # Configuracion (Pydantic Settings)
│   ├── api/
│   │   ├── deps.py                # Inyeccion de dependencias
│   │   ├── websocket.py           # WebSocket endpoints + ConnectionManager
│   │   └── v1/
│   │       ├── router.py          # Router agregador (legacy)
│   │       ├── admin_router.py    # Router del admin (auth + streams + health)
│   │       ├── viewer_router.py   # Router del viewer (streams read-only + health)
│   │       ├── auth.py            # Endpoints de autenticacion (login/logout/me)
│   │       ├── streams.py         # CRUD de streams
│   │       └── health.py          # Health checks y readiness probe
│   ├── core/
│   │   ├── security.py            # Hashing, sesiones, CSRF, IP extraction
│   │   ├── middleware.py          # Security headers (CSP), CORS
│   │   └── exceptions.py          # Excepciones custom y handlers
│   ├── models/
│   │   ├── stream.py              # Modelos de streams (plataformas, CRUD)
│   │   ├── auth.py                # Modelos de autenticacion (login, sesion)
│   │   └── websocket.py           # Modelos de mensajes WebSocket
│   ├── services/
│   │   ├── redis_service.py       # Operaciones Redis (streams, sesiones, rate limit)
│   │   ├── session_service.py     # Gestion de sesiones y autenticacion
│   │   ├── stream_service.py      # Logica de negocio de streams
│   │   └── platform_extractors/
│   │       ├── __init__.py        # Registry de extractores
│   │       ├── base.py            # Interfaz abstracta
│   │       ├── youtube.py         # Extractor YouTube (oEmbed)
│   │       ├── twitch.py          # Extractor Twitch
│   │       └── vimeo.py           # Extractor Vimeo (oEmbed)
│   ├── templates/
│   │   ├── base.html              # Template base Jinja2
│   │   ├── login.html             # Pagina de login
│   │   ├── admin.html             # Panel de administracion
│   │   └── viewer.html            # Visor publico de streams
│   └── static/
│       ├── css/
│       │   ├── common.css         # Estilos compartidos
│       │   ├── admin.css          # Estilos del admin
│       │   └── viewer.css         # Estilos del viewer
│       └── js/
│           ├── websocket-client.js  # Cliente WebSocket con reconnect
│           ├── admin.js             # Logica del admin
│           └── viewer.js            # Logica del viewer
├── docker-compose.yaml            # Produccion (viewer + admin + valkey)
├── docker-compose.dev.yaml        # Desarrollo con live reload
├── Dockerfile                     # Multi-stage build
├── run.sh                         # Script interactivo de setup/deploy
├── env.example                    # Ejemplo de variables de entorno
└── LICENSE                        # MIT License
```

### Servicios Docker

| Servicio | Puerto | Descripcion |
|----------|--------|-------------|
| `caos-viewer` | 64500:8000 | Visor publico (4 workers) |
| `caos-admin` | 64501:8000 | Panel de administracion (2 workers) |
| `valkey` | _(interno)_ | Base de datos Valkey 7 (compatible Redis) |

### Flujo de Datos
```
                    ┌──────────────────┐
                    │   Admin (64501)  │
                    │   FastAPI app    │
                    │  ┌────────────┐  │
Admin Browser ───►  │  │  Auth API  │  │ ──► Redis/Valkey
                    │  │ Stream API │  │        │
                    │  │ WebSocket  │  │        │
                    │  └────────────┘  │        │
                    └──────────────────┘        │
                                                │
                    ┌──────────────────┐        │
                    │  Viewer (64500)  │        │
                    │   FastAPI app    │        │
                    │  ┌────────────┐  │        │
TV / Browser ────►  │  │Streams API │  │ ──► Redis/Valkey
                    │  │ WebSocket  │  │  (datos compartidos)
                    │  └────────────┘  │
                    └──────────────────┘
```

### WebSocket Messages

| Tipo | Direccion | Descripcion |
|------|-----------|-------------|
| `stream_update` | Server -> Client | Lista completa de streams + layout |
| `stream_added` | Server -> Client | Notificacion de stream agregado |
| `stream_removed` | Server -> Client | Notificacion de stream eliminado |
| `stream_muted` | Server -> Client | Cambio de estado mute |
| `force_refresh` | Server -> Viewers | Forzar recarga de viewers |
| `request_refresh` | Admin -> Server | Solicitar actualizacion |
| `force_viewer_refresh` | Admin -> Server | Forzar refresh de viewers |
| `ping` / `pong` | Bidireccional | Keepalive |

## API REST

### Admin API (puerto 64501)

| Metodo | Endpoint | Descripcion | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/auth/login` | Login (con CSRF) | No |
| POST | `/api/v1/auth/logout` | Logout | Si |
| GET | `/api/v1/auth/me` | Info de sesion actual | No |
| GET | `/api/v1/streams` | Listar streams | No |
| POST | `/api/v1/streams` | Agregar stream | Si |
| DELETE | `/api/v1/streams/{id}` | Eliminar stream | Si |
| POST | `/api/v1/streams/{id}/mute` | Toggle mute | Si |
| GET | `/api/v1/health` | Health check basico | No |
| GET | `/api/v1/health/ready` | Readiness probe (verifica Redis) | No |

### Viewer API (puerto 64500)

| Metodo | Endpoint | Descripcion | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/streams` | Listar streams (read-only) | No |
| GET | `/api/v1/health` | Health check basico | No |
| GET | `/api/v1/health/ready` | Readiness probe (verifica Redis) | No |

### WebSocket Endpoints

| Endpoint | Descripcion | Auth |
|----------|-------------|------|
| `ws://host:64500/ws/viewer` | WebSocket para viewers | No |
| `ws://host:64501/ws/admin` | WebSocket para admins | Si (cookie) |

## Solucion de Problemas

### WebSockets no funcionan
```bash
./run.sh --logs
# Verificar errores de conexion en los logs de ambos servicios
docker compose logs caos-viewer | grep -i websocket
docker compose logs caos-admin | grep -i websocket
```

### Sesion no persiste
```bash
# Verificar Redis/Valkey
docker compose exec valkey valkey-cli ping
# Verificar que SECRET_KEY sea consistente entre reinicios
```

### Videos no cargan
- Verificar que la URL sea valida y la plataforma este soportada
- Algunos videos tienen restricciones de embed
- Twitch requiere configurar el dominio parent correcto (se configura automaticamente)
- Verificar CSP en los headers de respuesta

### Error de CSRF en login
- Asegurarse de que las cookies no esten bloqueadas por el navegador
- Si se usa proxy, verificar que `BEHIND_PROXY=true` y `CLOUDFLARE_TUNNEL=true` esten configurados

### Logs utiles
```bash
./run.sh --logs                        # Todos los logs en tiempo real
docker compose logs -f caos-viewer     # Solo logs del viewer
docker compose logs -f caos-admin      # Solo logs del admin
docker compose logs -f valkey          # Solo logs de Valkey
```

## Desarrollo Local

### Con Docker (Recomendado)

```bash
git clone https://github.com/aweher/caos-vision.git
cd caos-vision

# Modo desarrollo con live reload
./run.sh --dev
```

Esto levanta ambas aplicaciones con `--reload` habilitado y el codigo fuente montado como volumen.

### Sin Docker

```bash
# Clonar repositorio
git clone https://github.com/aweher/caos-vision.git
cd caos-vision

# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r app/requirements.txt

# Iniciar Valkey/Redis
docker run -d -p 6379:6379 valkey/valkey:7-alpine

# Configurar variables de entorno
export ADMIN_USER=admin
export ADMIN_PASS=admin
export SECRET_KEY=development-secret-key-min-32-chars
export REDIS_URL=redis://localhost:6379/0
export DEBUG=true

# Ejecutar Viewer (terminal 1)
cd app
uvicorn viewer_main:app --reload --port 8000

# Ejecutar Admin (terminal 2)
cd app
uvicorn admin_main:app --reload --port 8001
```

## Casos de Uso

- **Gaming & Streaming**: Monitorear multiples streamers simultaneamente
- **Entretenimiento**: Walls de videos musicales, canales de noticias
- **Empresarial**: Monitoreo de marca, eventos multi-camara
- **Investigacion**: Analisis de tendencias de contenido
- **NOC/Operaciones**: Monitoreo de streams de camaras o dashboards

## Licencia

Este proyecto esta bajo la Licencia MIT. Ver [LICENSE](LICENSE).

## Soporte

- Issues: [GitHub Issues](https://github.com/aweher/caos-vision/issues)
- Email: ariel@weher.net
