"""Review-related Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..config import SeverityLevel


class ReviewType(str, Enum):
    """Types of review comments."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    BEST_PRACTICES = "best_practices"
    BUG = "bug"
    MAINTAINABILITY = "maintainability"
    DOCUMENTATION = "documentation"


class ReviewComment(BaseModel):
    """A single review comment."""
    file_path: str
    line_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    message: str
    suggestion: Optional[str] = None
    severity: SeverityLevel
    review_type: ReviewType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    rule_id: Optional[str] = None
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class ReviewRule(BaseModel):
    """Configuration for a review rule."""
    id: str
    name: str
    description: str
    enabled: bool = True
    severity: SeverityLevel
    review_type: ReviewType
    file_patterns: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=list)
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class ReviewRequest(BaseModel):
    """Request for code review."""
    repository_full_name: str
    pull_request_number: int
    head_sha: str
    base_sha: str
    files_to_review: List[str] = Field(default_factory=list)
    rules: List[ReviewRule] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class ReviewResponse(BaseModel):
    """Response from code review."""
    request_id: str
    repository_full_name: str
    pull_request_number: int
    comments: List[ReviewComment]
    summary: str
    total_issues: int
    issues_by_severity: Dict[str, int] = Field(default_factory=dict)
    issues_by_type: Dict[str, int] = Field(default_factory=dict)
    review_duration_seconds: float
    ai_model_used: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class ManualReviewRequest(BaseModel):
    """Manual review request model."""
    repository_full_name: str
    pull_request_number: int
    force_review: bool = False
    specific_files: Optional[List[str]] = None
    custom_rules: Optional[List[ReviewRule]] = None


class ReviewMetrics(BaseModel):
    """Review metrics and statistics."""
    total_reviews: int
    total_comments: int
    average_review_time: float
    issues_by_severity: Dict[str, int]
    issues_by_type: Dict[str, int]
    most_common_issues: List[Dict[str, Any]]
    review_success_rate: float
    last_updated: datetime = Field(default_factory=datetime.utcnow)
