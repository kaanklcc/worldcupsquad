"""
WCAI Backend - Python FastAPI Server

A World Cup 2026 Fantasy Football Manager backend with:
- Gemini LLM-powered AI consultant with function-calling
- Real x402 payment verification
- CCTP USDC bridging
- MCP (Model Context Protocol) server for squad tools
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import players, agent, cctp, transfers, auth, squads, worldcup, access, tactical_lab, operations


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="WCAI API",
        description="World Cup 2026 Fantasy Football Manager Backend",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Credentialed requests must have an explicit origin list. Operators add the
    # deployed frontend URL through CORS_ORIGINS rather than opening the API to
    # every browser origin.
    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
            "docs": "/docs",
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
