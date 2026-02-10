# Contribuyendo a Caos Vision

Gracias por tu interes en contribuir a **Caos Vision**.

## Formas de Contribuir

### Reportar Bugs
- Usa los [GitHub Issues](https://github.com/aweher/caos-vision/issues)
- Incluye pasos para reproducir el problema
- Especifica tu entorno (OS, Docker version, browser)
- Adjunta logs relevantes (`./run.sh --logs`)

### Sugerir Features
- Abre un Issue describiendo la funcionalidad
- Explica el problema que resuelve
- Considera alternativas

### Contribuir Codigo
- Fork el repositorio
- Crea una rama para tu feature/fix
- Sigue las convenciones de codigo
- Actualiza documentacion si es necesario

## Configuracion de Desarrollo

### Prerrequisitos
- Python 3.11+
- Docker & Docker Compose
- Git

### Setup con Docker (Recomendado)

```bash
# 1. Fork y clonar
git clone https://github.com/TU_USUARIO/caos-vision.git
cd caos-vision

# 2. Iniciar en modo desarrollo (hot reload)
./run.sh --dev
```

Esto levanta tres servicios:
- **caos-viewer** en `http://localhost:64500` (visor publico)
- **caos-admin** en `http://localhost:64501` (panel de administracion)
- **valkey** (base de datos Redis-compatible)

El codigo fuente se monta como volumen, por lo que los cambios se reflejan automaticamente.

### Setup Local (Sin Docker para la app)

```bash
# 1. Fork y clonar
git clone https://github.com/TU_USUARIO/caos-vision.git
cd caos-vision

# 2. Configurar entorno Python
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r app/requirements.txt

# 3. Iniciar Valkey/Redis
docker run -d -p 6379:6379 valkey/valkey:7-alpine

# 4. Variables de entorno
export ADMIN_USER=admin
export ADMIN_PASS=admin
export SECRET_KEY=development-secret-key-min-32-chars
export REDIS_URL=redis://localhost:6379/0
export DEBUG=true

# 5. Ejecutar Viewer (terminal 1)
cd app
uvicorn viewer_main:app --reload --port 8000

# 6. Ejecutar Admin (terminal 2)
cd app
uvicorn admin_main:app --reload --port 8001
```

> **Nota:** La aplicacion tiene dos entry points separados: `viewer_main:app` (visor publico) y `admin_main:app` (panel de admin). Ambos comparten la misma base de datos Redis.

## Estructura del Proyecto

```
caos-vision/
├── app/
│   ├── __init__.py
│   ├── admin_main.py              # Entry point Admin (FastAPI app)
│   ├── viewer_main.py             # Entry point Viewer (FastAPI app)
│   ├── config.py                  # Configuracion (Pydantic Settings)
│   ├── api/
│   │   ├── deps.py                # Inyeccion de dependencias (auth, redis, servicios)
│   │   ├── websocket.py           # WebSocket endpoints + ConnectionManager
│   │   └── v1/
│   │       ├── router.py          # Router agregador (legacy)
│   │       ├── admin_router.py    # Router del admin (auth + streams + health)
│   │       ├── viewer_router.py   # Router del viewer (streams read-only + health)
│   │       ├── auth.py            # Endpoints de autenticacion (login/logout/me)
│   │       ├── streams.py         # CRUD de streams (con broadcast WebSocket)
│   │       └── health.py          # Health checks y readiness probe
│   ├── core/
│   │   ├── security.py            # Hashing (bcrypt), sesiones, CSRF, IP extraction
│   │   ├── middleware.py          # Security headers (CSP con nonces), CORS
│   │   └── exceptions.py          # Excepciones custom y handlers globales
│   ├── models/
│   │   ├── stream.py              # Modelos de streams (plataformas, request/response)
│   │   ├── auth.py                # Modelos de auth (login, sesion, logout)
│   │   └── websocket.py           # Modelos tipados de mensajes WebSocket
│   ├── services/
│   │   ├── redis_service.py       # Operaciones Redis (streams, sesiones, rate limit)
│   │   ├── session_service.py     # Autenticacion y gestion de sesiones
│   │   ├── stream_service.py      # Logica de negocio (add, delete, mute, layout)
│   │   └── platform_extractors/
│   │       ├── __init__.py        # Registry de extractores
│   │       ├── base.py            # Interfaz abstracta (BasePlatformExtractor)
│   │       ├── youtube.py         # Extractor YouTube (oEmbed API)
│   │       ├── twitch.py          # Extractor Twitch (channels + VODs)
│   │       └── vimeo.py           # Extractor Vimeo (oEmbed API)
│   ├── templates/                 # HTML Jinja2 (base, login, admin, viewer)
│   └── static/
│       ├── css/                   # Estilos (common, admin, viewer)
│       └── js/                    # Scripts (websocket-client, admin, viewer)
├── Dockerfile                     # Multi-stage build (Python 3.11-slim)
├── docker-compose.yaml            # Produccion (viewer + admin + valkey)
├── docker-compose.dev.yaml        # Desarrollo (hot reload, volumes)
├── run.sh                         # Script interactivo de setup/deploy
├── env.example                    # Ejemplo de variables de entorno
└── LICENSE                        # MIT License
```

## Convenciones de Codigo

### Python
```python
# Usar type hints en todos los parametros y retornos
# Docstrings para funciones publicas
# PEP 8
# Pydantic v2 para modelos de datos
# async/await para operaciones I/O

async def get_stream(stream_id: str) -> StreamResponse:
    """Obtiene un stream por su ID.

    Args:
        stream_id: ID unico del stream

    Returns:
        StreamResponse con los datos del stream

    Raises:
        StreamNotFoundError: Si el stream no existe
    """
    pass
```

### JavaScript
```javascript
// Usar camelCase para variables y funciones
// Clases con PascalCase
// Funciones async/await
// Manejo de errores explicito

async function addStream(url) {
    try {
        const response = await fetch('/api/v1/streams', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        if (!response.ok) throw new Error('Failed to add stream');
        return await response.json();
    } catch (error) {
        console.error('Error adding stream:', error);
        throw error;
    }
}
```

### CSS
```css
/* Usar variables CSS para colores y valores repetidos */
/* Mobile-first approach */
/* BEM para nombres de clases */

.stream-wrapper {
    /* estilos */
}

.stream-wrapper--fullscreen {
    /* modificador */
}
```

## Proceso de Pull Request

### 1. Crear rama
```bash
git checkout main
git pull origin main
git checkout -b feature/nueva-funcionalidad
# o
git checkout -b fix/descripcion-del-bug
```

### 2. Desarrollo
Commits pequenos y descriptivos usando [Conventional Commits](https://www.conventionalcommits.org/):
```bash
git commit -m "feat: add twitch vod support"
git commit -m "fix: resolve websocket reconnection issue"
git commit -m "docs: update API documentation"
git commit -m "refactor: split main.py into admin and viewer apps"
```

### 3. Testing

```bash
# Con Docker (recomendado)
./run.sh --dev

# Probar manualmente:
# - Login/logout en http://localhost:64501/login
# - Agregar/eliminar streams de cada plataforma (YouTube, Twitch, Vimeo)
# - WebSocket: verificar actualizaciones en tiempo real en el viewer
# - Abrir el viewer en http://localhost:64500 y confirmar sincronizacion
# - Rate limiting: intentar multiples logins fallidos
# - Responsive design en diferentes tamaños de pantalla
```

### 4. Pull Request
- Titulo descriptivo
- Descripcion de cambios
- Screenshots si hay cambios UI
- Referenciar issues relacionados

## Agregar Nueva Plataforma

Para agregar soporte para una nueva plataforma de streaming:

### 1. Agregar al enum en `app/models/stream.py`:
```python
class StreamPlatform(str, Enum):
    YOUTUBE = "youtube"
    TWITCH = "twitch"
    VIMEO = "vimeo"
    NEWPLATFORM = "newplatform"  # Nuevo
```

### 2. Crear extractor en `app/services/platform_extractors/`:
```python
# app/services/platform_extractors/newplatform.py
from typing import Optional

from models.stream import StreamMetadata, StreamPlatform
from services.platform_extractors.base import BasePlatformExtractor


class NewPlatformExtractor(BasePlatformExtractor):
    platform = StreamPlatform.NEWPLATFORM

    def can_handle(self, url: str) -> bool:
        return "newplatform.com" in url.lower()

    def extract_id(self, url: str) -> Optional[str]:
        # Implementar extraccion de ID con regex
        pass

    def get_embed_url(self, video_id: str, host: str = "localhost") -> str:
        return f"https://embed.newplatform.com/{video_id}"

    async def get_metadata(self, video_id: str) -> StreamMetadata:
        # Implementar obtencion de metadatos (oEmbed, API, etc.)
        return StreamMetadata(title=f"NewPlatform Video {video_id}")
```

### 3. Registrar en `app/services/platform_extractors/__init__.py`:
```python
from services.platform_extractors.newplatform import NewPlatformExtractor

class PlatformExtractorRegistry:
    def __init__(self) -> None:
        self.extractors = [
            YouTubeExtractor(),
            TwitchExtractor(),
            VimeoExtractor(),
            NewPlatformExtractor(),  # Nuevo
        ]
```

### 4. Actualizar CSP en `app/core/middleware.py`:
Si la plataforma requiere cargar iframes o imagenes desde dominios nuevos, agregar a las directivas CSP:
```python
# frame-src: agregar dominio del embed
"frame-src 'self' https://www.youtube.com ... https://embed.newplatform.com"

# img-src: agregar dominio de thumbnails
"img-src 'self' data: ... https://thumbnails.newplatform.com"
```

### 5. Agregar estilos CSS para el badge de plataforma:
```css
.badge-newplatform {
    background-color: #ff0000;
    color: white;
}
```

## Debugging

### Logs
```bash
# Logs de todos los servicios
./run.sh --logs

# Logs individuales
docker compose logs -f caos-admin
docker compose logs -f caos-viewer
docker compose logs -f valkey

# Debug mode (habilita /api/docs y logs verbose)
# Configurar DEBUG=true en .env o docker-compose
```

### Redis/Valkey
```bash
# Conectar al CLI de Valkey
docker compose exec valkey valkey-cli

# Comandos utiles:
# Ver todas las keys
KEYS caos:*

# Ver streams almacenados
HGETALL caos:streams

# Ver sesiones activas
KEYS caos:session:*

# Ver rate limits activos
KEYS caos:ratelimit:*
```

### Herramientas Recomendadas
- **VS Code / PyCharm** con extension Python
- **Browser DevTools** para frontend y WebSockets (tab Network > WS)
- **Redis Insight** o **RedisInsight** para inspeccionar datos graficamente

## Preguntas

- Abrir un [Discussion](https://github.com/aweher/caos-vision/discussions)
- Enviar email a ariel@weher.net
