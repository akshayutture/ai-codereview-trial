"""Main FastAPI application for the code review agent."""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .models.github import GitHubWebhookPayload
from .models.review import ManualReviewRequest, ReviewMetrics
from .utils.logging import setup_logging
from .webhooks.github_webhook import GitHubWebhookHandler

# Setup logging
settings = get_settings()
setup_logging(settings)
logger = structlog.get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Python Code Review Agent",
    description="AI-powered GitHub code review agent",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Initialize webhook handler
webhook_handler = GitHubWebhookHandler(settings)

# Global metrics storage (in production, use Redis or database)
_metrics = {
    "total_reviews": 0,
    "total_comments": 0,
    "total_errors": 0,
    "start_time": datetime.utcnow()
}


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(
        "Starting Code Review Agent",
        version="1.0.0",
        environment=settings.environment.value,
        ai_model=settings.ai_model.value,
        host=settings.host,
        port=settings.port
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down Code Review Agent")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.environment.value
    }


@app.get("/metrics")
async def get_metrics() -> ReviewMetrics:
    """Get review metrics and statistics."""
    uptime_seconds = (datetime.utcnow() - _metrics["start_time"]).total_seconds()
    
    return ReviewMetrics(
        total_reviews=_metrics["total_reviews"],
        total_comments=_metrics["total_comments"],
        average_review_time=0.0,  # Would calculate from stored data
        issues_by_severity={},  # Would aggregate from stored data
        issues_by_type={},  # Would aggregate from stored data
        most_common_issues=[],  # Would calculate from stored data
        review_success_rate=1.0 - (_metrics["total_errors"] / max(_metrics["total_reviews"], 1))
    )


@app.get("/status")
async def get_status():
    """Get current status and active reviews."""
    active_reviews = webhook_handler.get_active_reviews()
    
    return {
        "status": "running",
        "active_reviews": active_reviews,
        "active_review_count": len(active_reviews),
        "settings": {
            "ai_model": settings.ai_model.value,
            "max_files_to_review": settings.max_files_to_review,
            "max_concurrent_reviews": settings.max_concurrent_reviews,
            "environment": settings.environment.value
        }
    }


@app.post("/webhook/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events."""
    try:
        # Get request body and signature
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")
        
        # Parse payload
        payload_data = await request.json()
        payload = GitHubWebhookPayload(**payload_data)
        
        # Handle webhook
        result = await webhook_handler.handle_webhook(
            payload=payload,
            signature=signature,
            payload_body=body
        )
        
        # Update metrics
        if result.get("status") == "started":
            _metrics["total_reviews"] += 1
        
        return result
        
    except Exception as e:
        logger.error(
            "Error handling GitHub webhook",
            error=str(e),
            exc_info=True
        )
        _metrics["total_errors"] += 1
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )


@app.post("/review/manual")
async def trigger_manual_review(request: ManualReviewRequest):
    """Trigger a manual code review."""
    try:
        result = await webhook_handler.trigger_manual_review(
            repo_full_name=request.repository_full_name,
            pr_number=request.pull_request_number,
            force=request.force_review
        )
        
        # Update metrics
        if result.get("status") == "started":
            _metrics["total_reviews"] += 1
        
        return result
        
    except Exception as e:
        logger.error(
            "Error triggering manual review",
            repo=request.repository_full_name,
            pr_number=request.pull_request_number,
            error=str(e),
            exc_info=True
        )
        _metrics["total_errors"] += 1
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual review failed: {str(e)}"
        )


@app.get("/reviews/active")
async def get_active_reviews():
    """Get list of currently active reviews."""
    return webhook_handler.get_active_reviews()


@app.delete("/reviews/{request_id}")
async def cancel_review(request_id: str):
    """Cancel an active review."""
    try:
        cancelled = await webhook_handler.review_engine.cancel_review(request_id)
        
        if cancelled:
            return {"status": "cancelled", "request_id": request_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review {request_id} not found or already completed"
            )
            
    except Exception as e:
        logger.error(
            "Error cancelling review",
            request_id=request_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel review: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.is_development else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "code_review_agent.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.value.lower()
    )
