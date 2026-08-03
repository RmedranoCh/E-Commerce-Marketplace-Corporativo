import time
import threading
from functools import wraps
from flask import request, jsonify


class RateLimiter:
    """Limitador simple en memoria (por IP). Para despliegues reales con varios
    workers, sustituir por una implementación con respaldo en Redis."""

    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def limit(self, max_hits: int, window_seconds: int):
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                key = f"{request.remote_addr}:{request.path}"
                now = time.time()
                with self._lock:
                    bucket = [t for t in self._hits.get(key, []) if now - t < window_seconds]
                    if len(bucket) >= max_hits:
                        self._hits[key] = bucket
                        return jsonify({"error": "Demasiadas solicitudes. Intente de nuevo más tarde."}), 429
                    bucket.append(now)
                    self._hits[key] = bucket
                return fn(*args, **kwargs)
            return wrapper
        return decorator


rate_limiter = RateLimiter()
