"""
Auto-Gaffer Backend - Python FastAPI Server

A World Cup 2026 Fantasy Football Manager backend with:
- Gemini LLM-powered AI consultant with function-calling
- Real x402 payment verification
- CCTP USDC bridging
- MCP (Model Context Protocol) server for squad tools
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import players, agent, cctp, transfers, auth


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Auto-Gaffer API",
        description="World Cup 2026 Fantasy Football Manager Backend",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Next.js dev server
            "http://127.0.0.1:3000",
            "http://localhost:3001",
        ],
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

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Auto-Gaffer API",
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