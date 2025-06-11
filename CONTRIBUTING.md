# 🤝 Contribuyendo a Caos Vision

¡Gracias por tu interés en contribuir a **Caos Vision**! Este documento te ayudará a empezar de la mejor manera.

## 🎯 Formas de Contribuir

### 🐛 Reportar Bugs
- Usa el [template de bug report](https://github.com/aweher/caos-vision/issues/new?template=bug_report.md)
- Incluye pasos para reproducir el problema
- Especifica tu entorno (OS, Docker version, etc.)
- Adjunta logs relevantes

### 💡 Sugerir Features
- Usa el [template de feature request](https://github.com/aweher/caos-vision/issues/new?template=feature_request.md)
- Explica el problema que resuelve
- Describe la solución propuesta
- Considera alternativas

### 🔧 Contribuir Código
- Fork el repositorio
- Crea una rama para tu feature/fix
- Sigue las convenciones de código
- Escribe tests si es aplicable
- Actualiza documentación

## 🚀 Configuración de Desarrollo

### Prerrequisitos
```bash
# Requerido
- Python 3.11+
- Docker & Docker Compose
- Git

# Recomendado
- VS Code con extensiones Python
- Redis Insight para debugging
- Cloudflared para testing tunnels
```

### Setup Local
```bash
# 1. Fork y clonar
git clone https://github.com/aweher/caos-vision.git
cd caos-vision

# 2. Configurar entorno Python
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r app/requirements.txt
pip install -r requirements-dev.txt  # Si existe

# 3. Configurar variables de entorno
cp env.example .env
# Editar .env con valores de desarrollo

# 4. Iniciar servicios
docker-compose -f docker-compose.dev.yml up -d redis

# 5. Ejecutar aplicación
cd app
python app.py
```

## 📋 Convenciones de Código

### Python
```python
# Usar PEP 8
# Nombres descriptivos
# Docstrings para funciones públicas
def get_youtube_video_id(url: str) -> Optional[str]:
    """
    Extrae el ID de video de una URL de YouTube.
    
    Args:
        url: URL de YouTube en cualquier formato
        
    Returns:
        ID del video o None si no es válida
    """
    pass
```

### JavaScript
```javascript
// Usar camelCase
// Funciones async/await
// Manejo de errores explícito
async function addStream(url) {
    try {
        // lógica aquí
    } catch (error) {
        console.error('Error adding stream:', error);
        showError('Error al agregar stream');
    }
}
```

### CSS
```css
/* Usar variables CSS */
/* Mobile-first approach */
/* Nombres de clases descriptivos */
.stream-container {
    /* estilos aquí */
}

.stream-container--loading {
    /* modificador */
}
```

## 🧪 Testing

### Tests Unitarios
```bash
# Ejecutar tests
python -m pytest tests/

# Con coverage
python -m pytest --cov=app tests/

# Test específico
python -m pytest tests/test_auth.py::test_login
```

### Tests de Integración
```bash
# Test completo del sistema
python test_session.py

# Test con Cloudflare Tunnel
python test_session.py --url https://tu-tunnel.trycloudflare.com
```

### Tests Manuales
- [ ] Login/logout funciona
- [ ] Agregar/eliminar streams
- [ ] WebSocket actualizaciones
- [ ] Responsive design
- [ ] Cross-browser compatibility

## 📝 Proceso de Pull Request

### 1. Preparación
```bash
# Crear rama desde main
git checkout main
git pull origin main
git checkout -b feature/nueva-funcionalidad

# O para bug fix
git checkout -b fix/descripcion-del-bug
```

### 2. Desarrollo
- Hacer commits pequeños y descriptivos
- Seguir [Conventional Commits](https://www.conventionalcommits.org/)
```bash
git commit -m "feat: add stream search functionality"
git commit -m "fix: resolve websocket connection issues"
git commit -m "docs: update API documentation"
```

### 3. Testing
```bash
# Asegurar que todos los tests pasan
python -m pytest
python test_session.py

# Verificar que la aplicación inicia correctamente
docker-compose up -d
```

### 4. Pull Request
- Título descriptivo
- Descripción detallada de cambios
- Screenshots si hay cambios UI
- Referenciar issues relacionados

## 🎨 Guías de Estilo

### Commits
```
<tipo>(<scope>): <descripción>

feat(auth): add rate limiting to login
fix(websocket): resolve connection drops
docs(readme): update installation guide
style(css): improve responsive design
refactor(api): simplify stream management
test(auth): add login validation tests
chore(docker): update base image
```

### Ramas
```
feature/nombre-funcionalidad
fix/descripcion-bug
hotfix/problema-critico
docs/actualizacion-documentacion
refactor/mejora-codigo
```

## 🔍 Code Review

### Como Autor
- [ ] Tests pasan localmente
- [ ] Código sigue convenciones
- [ ] Documentación actualizada
- [ ] Sin conflictos con main
- [ ] Descripción clara del PR

### Como Reviewer
- [ ] Funcionalidad cumple requisitos
- [ ] Código es legible y mantenible
- [ ] Tests adecuados incluidos
- [ ] No introduce vulnerabilidades
- [ ] Performance es aceptable

## 🐛 Debugging

### Logs Útiles
```bash
# Logs de aplicación
docker-compose logs -f caos-vision

# Logs de Redis
docker-compose logs -f valkey

# Debug Python
export FLASK_DEBUG=1
python app.py
```

### Herramientas Recomendadas
- **VS Code Debugger**: Para Python
- **Browser DevTools**: Para frontend
- **Redis Insight**: Para inspeccionar datos
- **Docker Desktop**: Para contenedores

## 📚 Recursos

### Documentación
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SocketIO Documentation](https://python-socketio.readthedocs.io/)
- [Redis Documentation](https://redis.io/documentation)
- [Docker Documentation](https://docs.docker.com/)

## 🎖️ Reconocimientos

Los contribuidores son reconocidos en:
- README principal
- Página de créditos en la aplicación
- Releases notes

## ❓ Preguntas

¿Tienes dudas? No dudes en:
- Abrir un [Discussion](https://github.com/aweher/caos-vision/discussions)
- Preguntar en Discord
- Enviar un email

---

**¡Gracias por hacer que Caos Vision sea mejor! 🎉** 