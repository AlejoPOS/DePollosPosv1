"""
Módulo de seguridad para la aplicación
Incluye protección CSRF, rate limiting, y otras medidas
"""
import hmac
import hashlib
import secrets
import time
from functools import wraps
from flask import session, request, abort, jsonify
from collections import defaultdict
from datetime import datetime, timedelta


# ==============================================
# PROTECCIÓN CSRF
# ==============================================

def generar_csrf_token():
    """Genera un token CSRF único"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validar_csrf_token(token):
    """Valida un token CSRF"""
    if '_csrf_token' not in session:
        return False
    return hmac.compare_digest(session['_csrf_token'], token)


def csrf_protect(f):
    """
    Decorador para proteger rutas con CSRF
    Uso: @csrf_protect
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            token = None
            
            # Buscar token en diferentes lugares
            if request.is_json:
                token = request.json.get('csrf_token')
            else:
                token = request.form.get('csrf_token')
            
            # También buscar en headers
            if not token:
                token = request.headers.get('X-CSRF-Token')
            
            if not token or not validar_csrf_token(token):
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Token CSRF inválido o ausente'
                    }), 403
                abort(403, description="Token CSRF inválido")
        
        return f(*args, **kwargs)
    
    return decorated_function


# ==============================================
# RATE LIMITING
# ==============================================

class RateLimiter:
    """Rate limiter simple basado en memoria"""
    
    def __init__(self):
        self.requests = defaultdict(list)
        self.cleanup_interval = 300  # Limpiar cada 5 minutos
        self.last_cleanup = time.time()
    
    def is_allowed(self, key, max_requests=100, window=3600):
        """
        Verifica si una petición está permitida
        
        Args:
            key: Identificador único (IP, usuario, etc)
            max_requests: Máximo de peticiones permitidas
            window: Ventana de tiempo en segundos (default 1 hora)
        
        Returns:
            bool: True si está permitido, False si excede el límite
        """
        now = time.time()
        
        # Limpiar requests antiguos periódicamente
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_requests()
            self.last_cleanup = now
        
        # Filtrar requests dentro de la ventana
        cutoff = now - window
        self.requests[key] = [
            req_time for req_time in self.requests[key] 
            if req_time > cutoff
        ]
        
        # Verificar límite
        if len(self.requests[key]) >= max_requests:
            return False
        
        # Agregar esta petición
        self.requests[key].append(now)
        return True
    
    def _cleanup_old_requests(self):
        """Limpia requests antiguos de la memoria"""
        cutoff = time.time() - 3600  # 1 hora
        keys_to_delete = []
        
        for key, times in self.requests.items():
            self.requests[key] = [t for t in times if t > cutoff]
            if not self.requests[key]:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.requests[key]


# Instancia global del rate limiter
rate_limiter = RateLimiter()


def rate_limit(max_requests=100, window=3600, key_func=None):
    """
    Decorador para limitar tasa de peticiones
    
    Args:
        max_requests: Número máximo de peticiones
        window: Ventana de tiempo en segundos
        key_func: Función para generar la key (default: IP)
    
    Ejemplo:
        @rate_limit(max_requests=10, window=60)  # 10 req/minuto
        def mi_ruta():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Determinar la key
            if key_func:
                key = key_func()
            else:
                # Usar IP por defecto
                key = request.remote_addr
            
            # Verificar rate limit
            if not rate_limiter.is_allowed(key, max_requests, window):
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Demasiadas peticiones. Intenta más tarde.'
                    }), 429
                abort(429, description="Demasiadas peticiones")
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


# ==============================================
# VALIDACIÓN DE ENTRADA
# ==============================================

def sanitize_string(text, max_length=500):
    """
    Sanitiza una cadena de texto
    - Elimina espacios extras
    - Limita longitud
    - Elimina caracteres potencialmente peligrosos
    """
    if not text:
        return ""
    
    # Convertir a string y eliminar espacios extras
    text = str(text).strip()
    
    # Limitar longitud
    text = text[:max_length]
    
    # Eliminar caracteres nulos y de control
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    return text


def validar_email(email):
    """Valida formato de email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validar_telefono(telefono):
    """Valida formato de teléfono colombiano"""
    import re
    # Acepta: 3001234567, 6012345678, +573001234567
    telefono = telefono.replace(' ', '').replace('-', '')
    pattern = r'^(\+57)?[36]\d{9}$|^[16]\d{6,9}$'
    return re.match(pattern, telefono) is not None


def validar_nit_colombia(nit):
    """Valida formato de NIT colombiano"""
    import re
    # Eliminar puntos y guiones
    nit_limpio = nit.replace('.', '').replace('-', '').strip()
    # Debe tener entre 8 y 10 dígitos
    return re.match(r'^\d{8,10}$', nit_limpio) is not None


# ==============================================
# HEADERS DE SEGURIDAD
# ==============================================

def configurar_headers_seguridad(app):
    """
    Configura headers de seguridad en todas las respuestas
    """
    @app.after_request
    def set_security_headers(response):
        # Prevenir clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Prevenir MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Habilitar protección XSS del navegador
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Content Security Policy básico
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;"
        )
        
        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy
        response.headers['Permissions-Policy'] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=()"
        )
        
        return response


# ==============================================
# LOGGING DE SEGURIDAD
# ==============================================

class SecurityLogger:
    """Logger para eventos de seguridad"""
    
    def __init__(self):
        self.events = []
    
    def log_event(self, event_type, user=None, ip=None, details=None):
        """
        Registra un evento de seguridad
        
        Args:
            event_type: Tipo de evento (login_failed, csrf_violation, etc)
            user: Usuario involucrado
            ip: IP origen
            details: Detalles adicionales
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'user': user,
            'ip': ip or request.remote_addr if request else None,
            'details': details
        }
        
        self.events.append(event)
        
        # En producción, esto debería ir a un sistema de logs real
        print(f"[SECURITY] {event_type} - User: {user} - IP: {event['ip']}")
        
        # Mantener solo los últimos 1000 eventos en memoria
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
    
    def get_recent_events(self, limit=100):
        """Obtiene eventos recientes"""
        return self.events[-limit:]


# Instancia global del logger
security_logger = SecurityLogger()


# ==============================================
# VALIDACIÓN DE SESIÓN
# ==============================================

def verificar_sesion_activa():
    """
    Verifica que la sesión sea válida y no haya expirado
    """
    if 'user' not in session:
        return False
    
    # Verificar tiempo de inactividad (30 minutos)
    if 'last_activity' in session:
        last_activity = datetime.fromisoformat(session['last_activity'])
        if datetime.now() - last_activity > timedelta(minutes=30):
            session.clear()
            return False
    
    # Actualizar última actividad
    session['last_activity'] = datetime.now().isoformat()
    
    return True


def require_auth(f):
    """
    Decorador que requiere autenticación
    Uso: @require_auth
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not verificar_sesion_activa():
            if request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Sesión expirada o inválida'
                }), 401
            from flask import redirect, url_for
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    
    return decorated_function


def require_role(*roles):
    """
    Decorador que requiere un rol específico
    Uso: @require_role('admin', 'cajero')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not verificar_sesion_activa():
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Sesión expirada'
                    }), 401
                from flask import redirect, url_for
                return redirect(url_for('login'))
            
            user_role = session.get('rol')
            if user_role not in roles:
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Permisos insuficientes'
                    }), 403
                abort(403, description="Permisos insuficientes")
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


# ==============================================
# FUNCIONES DE UTILIDAD
# ==============================================

def generar_secret_key_segura():
    """Genera una SECRET_KEY segura"""
    return secrets.token_hex(32)


def hash_password_secure(password):
    """
    Hash seguro de contraseña usando werkzeug
    """
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verificar_password_secure(hashed, password):
    """
    Verifica contraseña de forma segura
    """
    from werkzeug.security import check_password_hash
    return check_password_hash(hashed, password)


def validar_fuerza_password(password):
    """
    Valida que la contraseña cumpla requisitos mínimos
    
    Returns:
        tuple: (es_valida, mensaje)
    """
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres"
    
    if not any(c.isupper() for c in password):
        return False, "La contraseña debe tener al menos una mayúscula"
    
    if not any(c.islower() for c in password):
        return False, "La contraseña debe tener al menos una minúscula"
    
    if not any(c.isdigit() for c in password):
        return False, "La contraseña debe tener al menos un número"
    
    return True, "Contraseña válida"
