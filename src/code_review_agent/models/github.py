"""GitHub-related Pydantic models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """GitHub user model."""
    id: int
    login: str
    avatar_url: str
    html_url: str
    type: str


class Repository(BaseModel):
    """GitHub repository model."""
    id: int
    name: str
    full_name: str
    private: bool
    html_url: str
    description: Optional[str] = None
    language: Optional[str] = None
    default_branch: str
    owner: User


class PullRequest(BaseModel):
    """GitHub pull request model."""
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    draft: bool
    html_url: str
    diff_url: str
    patch_url: str
    head: Dict[str, Any]
    base: Dict[str, Any]
    user: User
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime] = None
    merge_commit_sha: Optional[str] = None
    assignees: List[User] = Field(default_factory=list)
    requested_reviewers: List[User] = Field(default_factory=list)
    labels: List[Dict[str, Any]] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


class GitHubWebhookPayload(BaseModel):
    """GitHub webhook payload model."""
    action: str
    number: int
    pull_request: PullRequest
    repository: Repository
    sender: User
    
    class Config:
        """Pydantic configuration."""
        extra = "allow"  # Allow additional fields from GitHub


class FileChange(BaseModel):
    """File change in a pull request."""
    filename: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    changes: int
    blob_url: str
    raw_url: str
    contents_url: str
    patch: Optional[str] = None
    previous_filename: Optional[str] = None


class CommitInfo(BaseModel):
    """Commit information."""
    sha: str
    message: str
    author: Dict[str, Any]
    committer: Dict[str, Any]
    timestamp: datetime
    url: str
