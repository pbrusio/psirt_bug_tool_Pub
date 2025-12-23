"""
FastAPI application for PSIRT vulnerability analysis
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from .api.routes import router
from .api.inventory_routes import router as inventory_router
from .api.review_routes import router as review_router
from .api.system_routes import router as system_router
from .api.reasoning_routes import router as reasoning_router
from .api.tutorial_routes import router as tutorial_router
from .api.admin_guide_routes import router as admin_guide_router
from .api.setup_guide_routes import router as setup_guide_router
from .api.docs_hub_routes import router as docs_hub_router
from .core import config
import logging
import uuid
from contextvars import ContextVar

# Request ID context variable - allows access from anywhere in the request
request_id_var: ContextVar[str] = ContextVar('request_id', default='no-request-id')


class RequestIDFilter(logging.Filter):
    """Logging filter that adds request_id to log records"""
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


# Configure logging with request ID support
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s'
)

# Add request ID filter to root logger
for handler in logging.root.handlers:
    handler.addFilter(RequestIDFilter())

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to inject request ID into each request"""

    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]  # Short 8-char ID for readability

        # Store in request state for route handlers
        request.state.request_id = request_id

        # Set context variable for logging
        token = request_id_var.set(request_id)

        try:
            # Log incoming request
            logger.info(f"{request.method} {request.url.path}")

            response = await call_next(request)

            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Reset context variable
            request_id_var.reset(token)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory sliding window rate limiter per IP.

    Rate limits are configurable via environment variables:
    - RATE_LIMIT_DEFAULT: Default requests/minute (100)
    - RATE_LIMIT_ANALYZE: /analyze-psirt limit (30)
    - RATE_LIMIT_VERIFY: /verify-* limit (20)
    - RATE_LIMIT_SCAN: /scan-device limit (60)
    """

    def __init__(self, app):
        super().__init__(app)
        self.request_counts: dict = {}  # {ip: [(timestamp, path), ...]}
        self.window_seconds = config.RATE_LIMIT_WINDOW_SECONDS

        # Path-specific limits (more restrictive for expensive operations)
        self.path_limits = {
            "/api/v1/analyze-psirt": config.RATE_LIMIT_ANALYZE,
            "/api/v1/verify-device": config.RATE_LIMIT_VERIFY,
            "/api/v1/verify-snapshot": config.RATE_LIMIT_VERIFY,
            "/api/v1/scan-device": config.RATE_LIMIT_SCAN,
            # Reasoning endpoints (computationally intensive)
            "/api/v1/reasoning/explain": 30,
            "/api/v1/reasoning/remediate": 20,
            "/api/v1/reasoning/ask": 20,
            "/api/v1/reasoning/summary": 10,
        }

        # Paths exempt from rate limiting
        self.exempt_paths = {
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/v1/health",
            "/api/v1/health/db",
        }

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, respecting X-Forwarded-For for proxied requests"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_limit_for_path(self, path: str) -> int:
        """Get rate limit for specific path"""
        for pattern, limit in self.path_limits.items():
            if path.startswith(pattern):
                return limit
        return config.RATE_LIMIT_DEFAULT

    def _cleanup_old_requests(self, ip: str, current_time: float):
        """Remove requests outside the sliding window"""
        if ip in self.request_counts:
            cutoff = current_time - self.window_seconds
            self.request_counts[ip] = [
                (ts, path) for ts, path in self.request_counts[ip]
                if ts > cutoff
            ]

    async def dispatch(self, request: Request, call_next):
        import time

        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Skip rate limiting for GET requests (only limit mutating operations)
        if request.method == "GET":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        current_time = time.time()
        path = request.url.path

        # Cleanup old requests
        self._cleanup_old_requests(client_ip, current_time)

        # Get applicable limit
        limit = self._get_limit_for_path(path)

        # Count requests to this path pattern in current window
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []

        # Count total requests in current window
        total_requests = len(self.request_counts[client_ip])

        if total_requests >= limit:
            logger.warning(f"Rate limit exceeded for {client_ip}: {total_requests}/{limit} on {path}")
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Max {limit} requests per {self.window_seconds}s.",
                    "retry_after": self.window_seconds
                },
                headers={"Retry-After": str(self.window_seconds)}
            )

        # Record this request
        self.request_counts[client_ip].append((current_time, path))

        return await call_next(request)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to check API key for write operations (POST/PUT/DELETE)"""

    # Paths that require API key authentication (when not in DEV_MODE)
    PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    # Paths that are always open (no auth required)
    OPEN_PATHS = {
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/health",
        "/api/v1/health/db",
    }

    async def dispatch(self, request: Request, call_next):
        # Skip auth in DEV_MODE
        if config.DEV_MODE:
            return await call_next(request)

        # Skip auth if no API key is configured
        if not config.ADMIN_API_KEY:
            return await call_next(request)

        # Skip auth for safe methods (GET, HEAD, OPTIONS)
        if request.method not in self.PROTECTED_METHODS:
            return await call_next(request)

        # Skip auth for open paths
        if request.url.path in self.OPEN_PATHS:
            return await call_next(request)

        # Check API key header
        provided_key = request.headers.get("X-ADMIN-KEY", "")

        if provided_key != config.ADMIN_API_KEY:
            logger.warning(f"Unauthorized access attempt: {request.method} {request.url.path}")
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Provide X-ADMIN-KEY header."}
            )

        return await call_next(request)


# Create FastAPI app (disable default docs to use custom styled version)
app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESCRIPTION,
    docs_url=None,  # Disable default, we'll add custom
    redoc_url=None  # Disable default, we'll add custom
)

# Add request ID middleware (first, so it's available to all others)
app.add_middleware(RequestIDMiddleware)

# Add rate limiting middleware (after request ID, before API key)
app.add_middleware(RateLimitMiddleware)
logger.info(f"Rate limiting enabled: {config.RATE_LIMIT_DEFAULT}/min default, "
            f"{config.RATE_LIMIT_ANALYZE}/min analyze, {config.RATE_LIMIT_SCAN}/min scan")

# Add API key middleware for write operations (before CORS)
app.add_middleware(APIKeyMiddleware)
if not config.DEV_MODE and config.ADMIN_API_KEY:
    logger.info("API key authentication enabled for write operations")
else:
    logger.info("API key authentication disabled (DEV_MODE or no key configured)")

# CORS middleware (configurable via ALLOWED_ORIGINS env var)
logger.info(f"CORS allowed origins: {config.ALLOWED_ORIGINS}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)
app.include_router(inventory_router)
app.include_router(review_router)
app.include_router(system_router)
app.include_router(reasoning_router)
app.include_router(tutorial_router)
app.include_router(admin_guide_router)
app.include_router(setup_guide_router)
app.include_router(docs_hub_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PSIRT Vulnerability Analysis API",
        "version": config.API_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health"
    }


# Minimal navigation bar for Swagger/ReDoc - matches the other docs nav style
# (Removed get_api_docs_nav_bar in favor of docs_common.get_nav_bar)

@app.get("/docs", include_in_schema=False)
async def swagger_redirect():
    """Redirect /docs to /api/v1/api-reference for consistency"""
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/api/v1/api-reference")


@app.get("/redoc", include_in_schema=False)
async def redoc_redirect():
    """Redirect /redoc to /api/v1/redoc for consistency"""
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/api/v1/redoc")


@app.get("/api/v1/api-reference", include_in_schema=False)
async def custom_swagger_ui_html():
    """Swagger UI with unified dark theme and navigation"""
    from .api.docs_common import get_nav_bar, SHARED_STYLES
    
    swagger_html = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{config.API_TITLE} - API Reference",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )
    
    # Custom CSS to override Swagger UI for dark mode consistency
    swagger_dark_overrides = """
        /* Core Backgrounds & Colors */
        body { margin: 0; padding: 0; background: #0f172a; }
        .swagger-ui { color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        
        /* Headers & Text */
        .swagger-ui .info .title, .swagger-ui .info h1, .swagger-ui .info h2, .swagger-ui .info h3, .swagger-ui .info h4, .swagger-ui .info h5 { color: #f8fafc; }
        .swagger-ui .info p, .swagger-ui .info li { color: #e2e8f0; }
        .swagger-ui .scheme-container { background: #1e293b; box-shadow: none; border-bottom: 1px solid #475569; }

        /* Expanded endpoint description text - make readable */
        .swagger-ui .opblock-description-wrapper p,
        .swagger-ui .opblock-description-wrapper li,
        .swagger-ui .opblock-external-docs-wrapper p,
        .swagger-ui .opblock-body p,
        .swagger-ui .opblock-body li,
        .swagger-ui .opblock-section-header h4,
        .swagger-ui .opblock-description {
            color: #e2e8f0 !important;
        }

        /* Bullet points in endpoint descriptions */
        .swagger-ui .opblock-description-wrapper ul li,
        .swagger-ui .opblock-body ul li,
        .swagger-ui .renderedMarkdown li,
        .swagger-ui .markdown li {
            color: #f1f5f9 !important;
        }
        
        /* Operations/Endpoints */
        .swagger-ui .opblock { border-radius: 8px; box-shadow: none; border: 1px solid #475569; background: #1e293b; }
        .swagger-ui .opblock .opblock-summary { border-bottom: 1px solid #475569; }
        .swagger-ui .opblock .opblock-summary-method { border-radius: 6px; }
        .swagger-ui .opblock .opblock-summary-description { color: #cbd5e1; } /* Lighter text for description */
        
        /* Tags */
        .swagger-ui .opblock-tag { color: #f8fafc; border-bottom: 1px solid #475569; }
        .swagger-ui .opblock-tag small { color: #94a3b8; }
        
        /* Inputs & Forms */
        .swagger-ui input[type=text], .swagger-ui input[type=password], .swagger-ui input[type=email], .swagger-ui textarea { 
            background: #334155; 
            color: #f8fafc; 
            border: 1px solid #475569; 
            outline: none;
        }
        .swagger-ui input::placeholder { color: #94a3b8; opacity: 0.7; }
        .swagger-ui select { background: #334155; color: #f8fafc; border: 1px solid #475569; }
        
        /* Tables & Parameters */
        .swagger-ui table thead tr td, .swagger-ui table thead tr th { color: #f8fafc; border-bottom: 1px solid #475569; }
        .swagger-ui .parameters-col_description { color: #cbd5e1; }
        .swagger-ui .parameter__name { color: #f8fafc; }
        .swagger-ui .parameter__type { color: #a855f7; } /* Purple accent */
        .swagger-ui .parameter__extension, .swagger-ui .parameter__in { color: #94a3b8; }
        
        /* Responses */
        .swagger-ui .response-col_status { color: #94a3b8; }
        .swagger-ui .response-col_description { color: #cbd5e1; }
        .swagger-ui .tab li { color: #94a3b8; }
        
        /* Buttons */
        .swagger-ui .btn { box-shadow: none; border: 1px solid #475569; color: #f8fafc; background: #334155; }
        .swagger-ui .btn:hover { background: #1e293b; border-color: #94a3b8; }
        .swagger-ui .btn.execute { background-color: #3b82f6; border-color: #3b82f6; color: white; }
        .swagger-ui .btn.btn-clear { background: transparent; border-color: #ef4444; color: #ef4444; }
        .swagger-ui .btn.authorize { color: #22c55e; border-color: #22c55e; background: transparent; }
        .swagger-ui .btn.authorize svg { fill: #22c55e; }
        
        /* Models */
        .swagger-ui section.models { border: 1px solid #475569; background: #1e293b; border-radius: 8px; }
        .swagger-ui section.models h4 { color: #94a3b8; }
        .swagger-ui .model { color: #f8fafc; }
        .swagger-ui .model-title { color: #f8fafc; }
        .swagger-ui .prop-type { color: #a855f7; }
        .swagger-ui .prop-format { color: #94a3b8; }
        .swagger-ui .model-box { background: #1e293b; }
        
        /* Modals */
        .swagger-ui .dialog-ux .modal-ux { background: #1e293b; border: 1px solid #475569; color: #f8fafc; }
        .swagger-ui .dialog-ux .modal-ux-header { border-bottom: 1px solid #475569; }
        .swagger-ui .dialog-ux .modal-ux-content h4 { color: #f8fafc; }
        
        /* Adjust main container to account for fixed nav */
        .swagger-ui { margin-top: 20px; }
        
        /* Markdown Tables (Fix for invisible text in description) */
        /* High specificity to override Swagger's .markdown table selectors */
        .swagger-ui .markdown table, .swagger-ui table { width: 100% !important; border-collapse: collapse !important; background: transparent !important; }
        .swagger-ui .markdown table tr, .swagger-ui table tr { background-color: #0f172a !important; }
        .swagger-ui .markdown table tbody tr:nth-of-type(odd), .swagger-ui table tbody tr:nth-of-type(odd) { background-color: #1e293b !important; }
        
        .swagger-ui .markdown table thead tr th, .swagger-ui table thead tr th,
        .swagger-ui .markdown table tbody tr td, .swagger-ui table tbody tr td { 
            color: #f8fafc !important; 
            border: 1px solid #475569 !important; 
            padding: 8px !important;
        }
        .swagger-ui .markdown table thead tr th, .swagger-ui table thead tr th { background-color: #1e293b !important; font-weight: bold !important; }
        
        .swagger-ui .markdown table tbody tr:hover, .swagger-ui table tbody tr:hover { background-color: #334155 !important; }
        .swagger-ui .markdown table tbody tr:hover td, .swagger-ui table tbody tr:hover td { background-color: #334155 !important; }

        /* Model/Schema Expanders */
        .swagger-ui .model-box-control, .swagger-ui .models-control, .swagger-ui .model-toggle { color: #94a3b8 !important; outline: none !important; }
        .swagger-ui .model-box-control:hover, .swagger-ui .models-control:hover, .swagger-ui .model-toggle:hover { color: #f8fafc !important; }
        .swagger-ui .model-toggle:after { filter: invert(1); }
        .swagger-ui button { outline: none !important; }
        
        /* Arrow icons - Aggressive fill override */
        .swagger-ui svg.arrow { fill: #f8fafc !important; opacity: 1 !important; enable-background: new 0 0 24 24; }
        .swagger-ui .model-toggle svg { fill: #f8fafc !important; }
        
        /* Code Blocks */
        .swagger-ui code, .swagger-ui .markdown code { background: #334155 !important; color: #f8fafc !important; text-shadow: none !important; }
        .swagger-ui pre, .swagger-ui .markdown pre { background: #1e293b !important; border: 1px solid #475569 !important; color: #f8fafc !important; }
        
        /* Path handling */
        .swagger-ui .opblock .opblock-summary-path { color: #f8fafc; }
        .swagger-ui .opblock .opblock-summary-path__deprecated { color: #94a3b8; }
        
        /* Fix for Expand/Collapse buttons in Schemas */
        .swagger-ui .model-box .model-box-control:focus, .swagger-ui .models-control:focus, .swagger-ui .model-toggle:focus { outline: none; }

        /* Try it out panel and execute section */
        .swagger-ui .try-out, .swagger-ui .try-out__btn { background: #334155 !important; color: #f8fafc !important; }
        .swagger-ui .try-out__btn { border: 1px solid #475569 !important; }
        .swagger-ui .try-out__btn:hover { background: #475569 !important; }

        /* Execute wrapper / response area */
        .swagger-ui .execute-wrapper,
        .swagger-ui .btn-group,
        .swagger-ui .opblock-body .opblock-section,
        .swagger-ui .opblock-section-header {
            background: #1e293b !important;
        }

        /* Response section backgrounds */
        .swagger-ui .responses-wrapper,
        .swagger-ui .response,
        .swagger-ui .responses-inner {
            background: #1e293b !important;
        }

        /* Live response area */
        .swagger-ui .live-responses-table,
        .swagger-ui .response-col_links {
            background: #1e293b !important;
            color: #f8fafc !important;
        }

        /* Curl command box */
        .swagger-ui .curl-command {
            background: #0f172a !important;
            border: 1px solid #475569 !important;
        }

        /* Request URL */
        .swagger-ui .request-url {
            background: #0f172a !important;
            color: #f8fafc !important;
        }

        /* Tab underlines */
        .swagger-ui .tab li:first-of-type:after { background: #3b82f6 !important; }
    """
    
    html_content = swagger_html.body.decode()
    
    # Inject styles and navigation
    # Add meta tag to prevent caching of the HTML to ensure CSS updates are seen
    head_content = f"""
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
        <meta http-equiv="Pragma" content="no-cache" />
        <meta http-equiv="Expires" content="0" />
        <style>
            {SHARED_STYLES}
            {swagger_dark_overrides}
        </style>
    """
    
    body_content = f"""
        {get_nav_bar('api')}
        <div style="padding-bottom: 50px;">
    """
    
    html_content = html_content.replace("</head>", f"{head_content}</head>")
    html_content = html_content.replace("<body>", f"<body>{body_content}")
    html_content = html_content.replace("</body>", "</div></body>")
    
    return HTMLResponse(content=html_content)


@app.get("/api/v1/redoc", include_in_schema=False)
async def custom_redoc_html():
    """ReDoc with unified dark theme and navigation"""
    from .api.docs_common import get_nav_bar, SHARED_STYLES

    nav_bar = get_nav_bar("redoc")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{config.API_TITLE} - API Reference (ReDoc)</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        {SHARED_STYLES}
        body {{
            margin: 0;
            padding: 0;
            background: #0f172a;
        }}
        redoc {{
            display: block;
            margin-top: 0;
        }}

        /* ============================================
           ReDoc Markdown Table Dark Theme Fixes
           ============================================ */

        /* Force dark backgrounds and light text on ALL tables */
        table {{
            width: 100% !important;
            border-collapse: collapse !important;
            background-color: #0f172a !important;
        }}

        tr {{
            background-color: #0f172a !important;
        }}

        tbody tr:nth-child(odd) {{
            background-color: #1e293b !important;
        }}

        td, th {{
            color: #f8fafc !important;
            border: 1px solid #475569 !important;
            padding: 10px 12px !important;
        }}

        thead tr, thead th {{
            background-color: #334155 !important;
            font-weight: 600 !important;
        }}

        tbody tr:hover, tbody tr:hover td {{
            background-color: #475569 !important;
        }}

        table code {{
            background-color: #1e293b !important;
            color: #f8fafc !important;
        }}

        table strong {{
            color: #3b82f6 !important;
        }}

        /* ============================================
           ReDoc Text & Panel Fixes
           ============================================ */

        /* Make description/secondary text more readable */
        p, li, span {{
            color: #e2e8f0 !important;
        }}

        /* Fix the "Try it out" panel / request body area */
        [class*="react-tabs__tab-panel"],
        [class*="tab-panel"],
        [class*="request-body"],
        div[class*="sc-"] {{
            background-color: #1e293b !important;
        }}

        /* Buttons in ReDoc */
        button {{
            background-color: #334155 !important;
            color: #f8fafc !important;
            border: 1px solid #475569 !important;
        }}

        button:hover {{
            background-color: #475569 !important;
        }}

        /* Tab buttons */
        [class*="tab"] {{
            color: #cbd5e1 !important;
        }}

        [class*="tab"][class*="active"],
        [class*="tab"]:hover {{
            color: #f8fafc !important;
        }}

        /* Input fields and textareas */
        input, textarea, select {{
            background-color: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid #475569 !important;
        }}

        /* Labels */
        label {{
            color: #cbd5e1 !important;
        }}

        /* Schema/model boxes */
        [class*="model-box"],
        [class*="schema"] {{
            background-color: #1e293b !important;
        }}
    </style>
</head>
<body>
    {nav_bar}
    <redoc spec-url='/openapi.json'
           hide-download-button
           theme='{{"colors": {{"primary": {{"main": "#3b82f6"}}, "success": {{"main": "#22c55e"}}, "warning": {{"main": "#f97316"}}, "error": {{"main": "#ef4444"}}, "text": {{"primary": "#f8fafc", "secondary": "#cbd5e1"}}, "http": {{"get": "#22c55e", "post": "#3b82f6", "put": "#f97316", "delete": "#ef4444"}}}}, "sidebar": {{"backgroundColor": "#1e293b", "textColor": "#f8fafc"}}, "rightPanel": {{"backgroundColor": "#0f172a", "width": "40%", "textColor": "#f8fafc"}}, "typography": {{"fontSize": "15px", "code": {{"backgroundColor": "#334155", "color": "#f8fafc"}}}}}}'>
    </redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.on_event("startup")
async def startup_event():
    """Startup event - initialize services"""
    logging.info("🚀 Starting PSIRT Analysis API...")
    logging.info(f"📦 SEC-8B model: {config.MODEL_NAME}")
    logging.info(f"🔢 Quantization: {config.QUANTIZATION_BITS}-bit")
    logging.info("✅ API ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event - cleanup"""
    logging.info("👋 Shutting down API...")
