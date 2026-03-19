"""API v1 router configuration.

This module sets up the main API router and includes all sub-routers for different
endpoints like authentication and chatbot functionality.
"""

from fastapi import APIRouter

from app.api.v1.poker import router as poker_router

api_router = APIRouter()

# Include routers
api_router.include_router(poker_router, prefix="/poker", tags=["poker"])
