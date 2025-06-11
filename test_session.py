#!/usr/bin/env python3
"""
Script de prueba para verificar que el sistema de sesiones funciona correctamente
"""

import requests
import sys

def test_login(base_url="http://localhost:64500"):
    """Probar la funcionalidad de login"""
    print("🧪 Probando sistema de sesiones...")
    
    # Crear sesión para mantener cookies
    session = requests.Session()
    
    try:
        # 1. Probar acceso sin login (debe redirigir)
        print("1. Probando acceso sin autenticación...")
        response = session.get(f"{base_url}/admin", allow_redirects=False)
        if response.status_code == 302:
            print("✅ Redirección sin autenticación funciona")
        else:
            print(f"❌ Error: Esperaba redirección 302, obtuvo {response.status_code}")
            return False
        
        # 2. Probar login con credenciales incorrectas
        print("2. Probando login con credenciales incorrectas...")
        login_data = {"username": "wrong", "password": "wrong"}
        response = session.post(f"{base_url}/login", data=login_data)
        if "Credenciales inválidas" in response.text:
            print("✅ Rechazo de credenciales incorrectas funciona")
        else:
            print("❌ Error: No se rechazaron credenciales incorrectas")
            return False
        
        # 3. Probar login con credenciales correctas
        print("3. Probando login con credenciales correctas...")
        login_data = {"username": "admin", "password": "mi_password_seguro"}
        response = session.post(f"{base_url}/login", data=login_data, allow_redirects=False)
        if response.status_code == 302:
            print("✅ Login exitoso - redirección detectada")
        else:
            print(f"❌ Error en login: {response.status_code}")
            print(f"Response text: {response.text[:200]}...")
            return False
        
        # 4. Probar acceso a área protegida después del login
        print("4. Probando acceso a área protegida...")
        response = session.get(f"{base_url}/admin")
        if response.status_code == 200 and "Panel de Administración" in response.text:
            print("✅ Acceso a área protegida funciona")
        else:
            print(f"❌ Error accediendo área protegida: {response.status_code}")
            return False
        
        # 5. Probar API
        print("5. Probando acceso a API...")
        response = session.get(f"{base_url}/api/streams")
        if response.status_code == 200:
            print("✅ Acceso a API funciona")
        else:
            print(f"❌ Error accediendo API: {response.status_code}")
            return False
        
        print("✅ Todas las pruebas pasaron exitosamente!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se puede conectar al servidor. ¿Está ejecutándose?")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    success = test_login()
    sys.exit(0 if success else 1) 