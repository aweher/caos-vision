#!/usr/bin/env python3
"""Smoke test E2E para caos-vision (viewer + admin).

Asume los servicios corriendo (p. ej. docker compose -f docker-compose.dev.yaml up).
Toda la configuración llega por variables de entorno:

  VIEWER_URL  (default: http://localhost:64500)
  ADMIN_URL   (default: http://localhost:64501)
  ADMIN_USER  (default: admin)
  ADMIN_PASS  (default: admin)

Uso:   python3 test_session.py
Exit:  0 si todos los checks pasan, 1 en caso contrario.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import requests

VIEWER_URL = (os.environ.get("VIEWER_URL") or "http://localhost:64500").rstrip("/")
ADMIN_URL = (os.environ.get("ADMIN_URL") or "http://localhost:64501").rstrip("/")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin")

TEST_STREAM_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
YOUTUBE_EMBED_PREFIX = "https://www.youtube-nocookie.com/embed/"
REQUEST_TIMEOUT = 15  # segundos

results: list[tuple[str, str, str]] = []  # (nombre, PASS/FAIL/SKIP, detalle)


def report(name: str, ok: bool | None, detail: str = "") -> bool:
    """Registra e imprime el resultado de un check. ok=None marca SKIP (no falla)."""
    status = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
    results.append((name, status, detail))
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line, flush=True)
    return ok is True


def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except ValueError:
        return None


# --- Checks ---


def check_viewer_health() -> bool:
    r = requests.get(f"{VIEWER_URL}/api/v1/health", timeout=REQUEST_TIMEOUT)
    data = safe_json(r) or {}
    ok = r.status_code == 200 and data.get("status") == "ok"
    return report("1. Viewer health", ok, f"status={r.status_code}")


def check_admin_health() -> bool:
    r = requests.get(f"{ADMIN_URL}/api/v1/health", timeout=REQUEST_TIMEOUT)
    ok_basic = r.status_code == 200 and (safe_json(r) or {}).get("status") == "ok"

    r2 = requests.get(f"{ADMIN_URL}/api/v1/health/ready", timeout=REQUEST_TIMEOUT)
    data2 = safe_json(r2) or {}
    ok_ready = r2.status_code == 200 and data2.get("redis") == "connected"

    ok = ok_basic and ok_ready
    detail = f"health={r.status_code}, ready={r2.status_code} redis={data2.get('redis')}"
    return report("2. Admin health + ready", ok, detail)


def check_admin_redirects() -> bool:
    session = requests.Session()
    r = session.get(f"{ADMIN_URL}/admin", allow_redirects=False, timeout=REQUEST_TIMEOUT)
    location = r.headers.get("Location", "")
    ok = r.status_code == 302 and location.endswith("/login")
    return report("3. /admin sin sesión redirige a /login", ok,
                  f"status={r.status_code} location={location!r}")


def check_login(session: requests.Session) -> bool:
    # GET /login: establece la cookie csrf_token (double-submit cookie pattern)
    r = session.get(f"{ADMIN_URL}/login", timeout=REQUEST_TIMEOUT)
    csrf = session.cookies.get("csrf_token")
    if r.status_code != 200 or not csrf:
        return report("4. Login API (CSRF + credenciales)", False,
                      f"GET /login status={r.status_code}, cookie csrf_token={'ok' if csrf else 'ausente'}")

    # Credenciales incorrectas → 401
    bad = session.post(
        f"{ADMIN_URL}/api/v1/auth/login",
        json={"username": ADMIN_USER, "password": "clave-claramente-incorrecta"},
        headers={"X-CSRF-Token": csrf},
        timeout=REQUEST_TIMEOUT,
    )
    if bad.status_code != 401:
        return report("4. Login API (CSRF + credenciales)", False,
                      f"credenciales malas: esperaba 401, obtuvo {bad.status_code}")

    # Credenciales correctas → 200 + redirect_url /admin
    good = session.post(
        f"{ADMIN_URL}/api/v1/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"X-CSRF-Token": csrf},
        timeout=REQUEST_TIMEOUT,
    )
    data = safe_json(good) or {}
    ok = good.status_code == 200 and data.get("redirect_url") == "/admin"
    return report("4. Login API (CSRF + credenciales)", ok,
                  f"bad={bad.status_code}, login={good.status_code} redirect_url={data.get('redirect_url')!r}")


def check_streams_list(session: requests.Session) -> bool:
    r = session.get(f"{ADMIN_URL}/api/v1/streams", timeout=REQUEST_TIMEOUT)
    data = safe_json(r) or {}
    ok = (r.status_code == 200
          and isinstance(data.get("streams"), list)
          and isinstance(data.get("layout"), list)
          and isinstance(data.get("total"), int))
    return report("5. GET /api/v1/streams autenticado", ok, f"status={r.status_code}")


def _cleanup_test_streams(session: requests.Session) -> None:
    """Borra streams de corridas anteriores que hayan quedado colgados."""
    r = session.get(f"{ADMIN_URL}/api/v1/streams", timeout=REQUEST_TIMEOUT)
    for s in (safe_json(r) or {}).get("streams", []):
        if s.get("url") == TEST_STREAM_URL:
            session.delete(f"{ADMIN_URL}/api/v1/streams/{s['id']}", timeout=REQUEST_TIMEOUT)


def check_create_stream(session: requests.Session) -> str | None:
    _cleanup_test_streams(session)

    r = session.post(f"{ADMIN_URL}/api/v1/streams",
                     json={"url": TEST_STREAM_URL}, timeout=REQUEST_TIMEOUT)
    data = safe_json(r) or {}
    problems = []
    if r.status_code != 201:
        problems.append(f"status={r.status_code}")
    if data.get("platform") != "youtube":
        problems.append(f"platform={data.get('platform')!r}")
    if data.get("muted") is not True:
        problems.append(f"muted={data.get('muted')!r}")
    if not str(data.get("embed_url", "")).startswith(YOUTUBE_EMBED_PREFIX):
        problems.append(f"embed_url={data.get('embed_url')!r}")
    if not data.get("id"):
        problems.append("id vacío")

    stream_id = data.get("id")

    # Mismo POST de nuevo → 409 duplicado
    dup = session.post(f"{ADMIN_URL}/api/v1/streams",
                       json={"url": TEST_STREAM_URL}, timeout=REQUEST_TIMEOUT)
    if dup.status_code != 409:
        problems.append(f"duplicado: esperaba 409, obtuvo {dup.status_code}")

    ok = not problems
    report("6. POST stream (201 + validación) y duplicado (409)", ok,
           "; ".join(problems) if problems else f"id={stream_id}, duplicado={dup.status_code}")
    return stream_id if ok else None


def check_mute_toggle(session: requests.Session, stream_id: str) -> bool:
    r1 = session.post(f"{ADMIN_URL}/api/v1/streams/{stream_id}/mute", timeout=REQUEST_TIMEOUT)
    m1 = (safe_json(r1) or {}).get("muted")
    r2 = session.post(f"{ADMIN_URL}/api/v1/streams/{stream_id}/mute", timeout=REQUEST_TIMEOUT)
    m2 = (safe_json(r2) or {}).get("muted")
    ok = r1.status_code == 200 and m1 is False and r2.status_code == 200 and m2 is True
    return report("7. Toggle mute (true → false → true)", ok,
                  f"status={r1.status_code}/{r2.status_code} muted={m1} → {m2}")


def check_viewer_sync(stream_id: str) -> bool:
    r = requests.get(f"{VIEWER_URL}/api/v1/streams", timeout=REQUEST_TIMEOUT)
    streams = (safe_json(r) or {}).get("streams", [])
    found = any(s.get("id") == stream_id for s in streams)
    ok = r.status_code == 200 and found
    return report("8. Stream visible en viewer (sync Redis)", ok,
                  f"status={r.status_code} stream={'encontrado' if found else 'ausente'}")


def check_viewer_websocket(stream_id: str) -> bool:
    try:
        import websockets
    except ImportError:
        return report("WS. /ws/viewer stream_update inicial (opcional)", None,
                      "librería 'websockets' no instalada")

    ws_url = VIEWER_URL
    if ws_url.startswith("https://"):
        ws_url = "wss://" + ws_url[len("https://"):]
    elif ws_url.startswith("http://"):
        ws_url = "ws://" + ws_url[len("http://"):]
    ws_url += "/ws/viewer"

    async def _recv_initial() -> dict:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            return json.loads(await asyncio.wait_for(ws.recv(), timeout=15))

    try:
        msg = asyncio.run(_recv_initial())
    except Exception as exc:
        return report("WS. /ws/viewer stream_update inicial (opcional)", False, repr(exc))

    ok = (msg.get("type") == "stream_update"
          and any(s.get("id") == stream_id for s in msg.get("streams", [])))
    detail = f"type={msg.get('type')!r}"
    if msg.get("type") == "stream_update":
        detail += f" stream={'encontrado' if any(s.get('id') == stream_id for s in msg.get('streams', [])) else 'ausente'}"
    return report("WS. /ws/viewer stream_update inicial (opcional)", ok, detail)


def check_delete_stream(session: requests.Session, stream_id: str) -> bool:
    r = session.delete(f"{ADMIN_URL}/api/v1/streams/{stream_id}", timeout=REQUEST_TIMEOUT)
    listed = requests.get(f"{ADMIN_URL}/api/v1/streams", timeout=REQUEST_TIMEOUT)
    still_there = any(s.get("id") == stream_id
                      for s in (safe_json(listed) or {}).get("streams", []))
    ok = r.status_code == 204 and not still_there
    return report("9. DELETE stream (204 + ya no listado)", ok,
                  f"status={r.status_code} restante={still_there}")


def check_logout(session: requests.Session) -> bool:
    r = session.post(f"{ADMIN_URL}/api/v1/auth/logout", timeout=REQUEST_TIMEOUT)
    me = session.get(f"{ADMIN_URL}/api/v1/auth/me", timeout=REQUEST_TIMEOUT)
    authenticated = (safe_json(me) or {}).get("authenticated")
    ok = r.status_code in (200, 204) and me.status_code == 200 and authenticated is False
    return report("10. Logout + /auth/me desautenticado", ok,
                  f"logout={r.status_code} me={me.status_code} authenticated={authenticated}")


# --- Main ---


def main() -> int:
    print(f"Viewer:  {VIEWER_URL}")
    print(f"Admin:   {ADMIN_URL}")
    print(f"Usuario: {ADMIN_USER}")
    print(flush=True)

    admin = requests.Session()

    steps = [
        check_viewer_health,
        check_admin_health,
        check_admin_redirects,
        lambda: check_login(admin),
        lambda: check_streams_list(admin),
    ]

    try:
        for step in steps:
            if not step():
                break
        else:
            stream_id = check_create_stream(admin)
            if stream_id:
                checks_tail = [
                    lambda: check_mute_toggle(admin, stream_id),
                    lambda: check_viewer_sync(stream_id),
                    lambda: check_viewer_websocket(stream_id),
                    lambda: check_delete_stream(admin, stream_id),
                    lambda: check_logout(admin),
                ]
                for check in checks_tail:
                    if not check():
                        break
    except (requests.ConnectionError, requests.Timeout) as exc:
        url = exc.request.url if exc.request else "servicio desconocido"
        print(f"\n[FATAL] Sin conexión con {url}: {exc}")
        print("¿Están corriendo los contenedores? "
              "(docker compose -f docker-compose.dev.yaml up -d)")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"\n[FATAL] Error inesperado: {exc!r}")
        return 1

    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    skipped = sum(1 for _, s, _ in results if s == "SKIP")

    print(f"\n=== RESUMEN ===\nPASS: {passed}  FAIL: {failed}  SKIP: {skipped}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
