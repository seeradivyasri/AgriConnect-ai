import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class LatencyLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request latency and log status codes.
    Strictly avoids logging raw request payloads per CLAUDE.md Section 12.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        process_time_ms = (time.perf_counter() - start_time) * 1000
        
        # Log: [Method] [Path] - Status [Code] - [Duration]ms
        logger.info(f"{request.method} {request.url.path} - Status {response.status_code} - {process_time_ms:.3f}ms")
        
        return response
