"""
WCAI Backend - Python FastAPI Server

A World Cup 2026 Fantasy Football Manager backend with:
- Gemini LLM-powered AI consultant with function-calling
- Real x402 payment verification
- CCTP USDC bridging
- MCP (Model Context Protocol) server for squad tools
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from .config import settings
from .routers import players, agent, cctp, transfers, auth, squads, worldcup, access, tactical_lab, operations


class _RequestTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Enforce a hard body limit even for chunked requests."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max(16_384, min(int(max_bytes), 10_485_760))

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        try:
            declared = int(headers.get(b"content-length", b"0") or 0)
        except ValueError:
            declared = self.max_bytes + 1
        if declared > self.max_bytes:
            return await JSONResponse({"detail": "Request body is too large."}, status_code=413)(scope, receive, send)

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _RequestTooLarge
            return message

        try:
            return await self.app(scope, limited_receive, send)
        except _RequestTooLarge:
            return await JSONResponse({"detail": "Request body is too large."}, status_code=413)(scope, receive, send)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    docs_url = "/docs" if settings.docs_enabled else None
    redoc_url = "/redoc" if settings.docs_enabled else None
    app = FastAPI(
        title="WCAI API",
        description="World Cup 2026 Fantasy Football Manager Backend",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_bytes)
    allowed_hosts = [host.strip() for host in settings.allowed_hosts.split(",") if host.strip()]
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # Credentialed requests must have an explicit origin list. Operators add the
    # deployed frontend URL through CORS_ORIGINS rather than opening the API to
    # every browser origin.
    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    if "*" in cors_origins:
        raise RuntimeError("CORS_ORIGINS must list exact frontend origins when credentials are enabled")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "PAYMENT-SIGNATURE", "X-Payment", "X-CSRF-Token"],
        expose_headers=["PAYMENT-REQUIRED", "PAYMENT-RESPONSE", "Retry-After"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        if request.url.path.startswith(("/api/auth", "/api/access", "/api/cctp")):
            response.headers["Cache-Control"] = "no-store"
        if settings.auth_cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Include routers
    app.include_router(players.router)
    app.include_router(agent.router)
    app.include_router(cctp.router)
    app.include_router(transfers.router)
    app.include_router(auth.router)
    app.include_router(squads.router)
    app.include_router(worldcup.router)
    app.include_router(access.router)
    app.include_router(tactical_lab.router)
    app.include_router(operations.router)

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "WCAI API",
            "version": "1.0.0",
            "docs": docs_url,
            "status": "operational",
            "technologies": [
                "Gemini LLM (Function Calling)",
                "x402 Payment Verification",
                "CCTP USDC Bridging",
                "MCP Server"
            ]
        }

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Create the app instance
app = create_app()
