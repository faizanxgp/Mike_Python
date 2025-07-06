"""
Benyon Sports API - Main Application Entry Point
Optimized for production deployment with Docker
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CORS_ORIGINS, ENVIRONMENT, DEBUG
from app.routers import files_clean, keycloak

# Create FastAPI application instance
app = FastAPI(
    title="Benyon Sports API",
    version="1.0.0",
    description="Backend API for Benyon Sports file management system",
    debug=DEBUG
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files_clean.router, prefix="/api/files", tags=["files"])
app.include_router(keycloak.router, prefix="/api/auth", tags=["authentication"])

# Health check endpoints
@app.get("/")
async def root():
    """Root endpoint - API status"""
    return {
        "status": "healthy",
        "message": "Benyon Sports API is running",
        "version": "1.0.0",
        "environment": ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "environment": ENVIRONMENT}

if __name__ == "__main__":
    import uvicorn
    from app.core.config import PORT
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=DEBUG
    )
