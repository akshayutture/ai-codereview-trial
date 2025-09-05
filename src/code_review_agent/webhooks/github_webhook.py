"""GitHub webhook handler for processing pull request events."""

import asyncio
import hashlib
import hmac
from typing import Dict, Optional

import structlog
from fastapi import HTTPException

from ..config import Settings, get_settings
from ..integrations.github_client import GitHubClient
from ..models.github import GitHubWebhookPayload
from ..models.review import ReviewRequest
from ..services.review_engine import ReviewEngine

logger = structlog.get_logger(__name__)


class GitHubWebhookHandler:
    """Handler for GitHub webhook events."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize webhook handler."""
        self.settings = settings or get_settings()
        self.github_client = GitHubClient(self.settings)
        self.review_engine = ReviewEngine(self.settings)
        self._active_tasks: Dict[str, asyncio.Task] = {}
    
    def verify_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify GitHub webhook signature."""
        if not signature_header:
            return False
        
        try:
            # Extract signature from header
            signature = signature_header.split('=')[1]
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.settings.github_webhook_secret.encode(),
                payload_body,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except (IndexError, ValueError):
            return False
    
    async def handle_webhook(
        self,
        payload: GitHubWebhookPayload,
        signature: Optional[str] = None,
        payload_body: Optional[bytes] = None
    ) -> Dict[str, str]:
        """Handle incoming GitHub webhook."""
        # Verify signature if provided
        if signature and payload_body:
            if not self.verify_signature(payload_body, signature):
                logger.warning(
                    "Invalid webhook signature",
                    action=payload.action,
                    repo=payload.repository.full_name,
                    pr_number=payload.pull_request.number
                )
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        logger.info(
            "Received GitHub webhook",
            action=payload.action,
            repo=payload.repository.full_name,
            pr_number=payload.pull_request.number,
            pr_title=payload.pull_request.title,
            sender=payload.sender.login
        )
        
        # Handle different actions
        if payload.action in ["opened", "synchronize", "reopened"]:
            return await self._handle_pull_request_event(payload)
        elif payload.action == "closed":
            return await self._handle_pull_request_closed(payload)
        else:
            logger.debug(
                "Ignoring webhook action",
                action=payload.action,
                repo=payload.repository.full_name,
                pr_number=payload.pull_request.number
            )
            return {"status": "ignored", "reason": f"Action '{payload.action}' not handled"}
    
    async def _handle_pull_request_event(self, payload: GitHubWebhookPayload) -> Dict[str, str]:
        """Handle pull request opened/updated events."""
        repo_name = payload.repository.full_name
        pr_number = payload.pull_request.number
        request_id = f"{repo_name}#{pr_number}"
        
        # Cancel any existing review for this PR
        if request_id in self._active_tasks:
            self._active_tasks[request_id].cancel()
            logger.info("Cancelled previous review", request_id=request_id)
        
        # Skip draft PRs unless configured otherwise
        if payload.pull_request.draft:
            logger.info(
                "Skipping draft pull request",
                request_id=request_id
            )
            return {"status": "skipped", "reason": "Draft pull request"}
        
        # Start review in background
        task = asyncio.create_task(
            self._conduct_review(payload),
            name=f"review-{request_id}"
        )
        self._active_tasks[request_id] = task
        
        # Don't await the task - let it run in background
        return {"status": "started", "request_id": request_id}
    
    async def _handle_pull_request_closed(self, payload: GitHubWebhookPayload) -> Dict[str, str]:
        """Handle pull request closed events."""
        request_id = f"{payload.repository.full_name}#{payload.pull_request.number}"
        
        # Cancel any active review
        if request_id in self._active_tasks:
            self._active_tasks[request_id].cancel()
            del self._active_tasks[request_id]
            logger.info("Cancelled review for closed PR", request_id=request_id)
        
        return {"status": "cancelled", "reason": "Pull request closed"}
    
    async def _conduct_review(self, payload: GitHubWebhookPayload) -> None:
        """Conduct the actual code review."""
        repo_name = payload.repository.full_name
        pr_number = payload.pull_request.number
        request_id = f"{repo_name}#{pr_number}"
        
        try:
            logger.info("Starting code review", request_id=request_id)
            
            # Get pull request files
            file_changes = await self.github_client.get_pull_request_files(
                repo_name, pr_number
            )
            
            if not file_changes:
                logger.info("No files to review", request_id=request_id)
                await self.github_client.post_summary_comment(
                    repo_name,
                    pr_number,
                    "No files found to review in this pull request."
                )
                return
            
            # Get file contents
            file_contents = await self.github_client.get_file_contents(
                repo_name,
                file_changes,
                payload.pull_request.head["sha"]
            )
            
            if not file_contents:
                logger.info("No file contents retrieved", request_id=request_id)
                await self.github_client.post_summary_comment(
                    repo_name,
                    pr_number,
                    "Unable to retrieve file contents for review."
                )
                return
            
            # Create review request
            review_request = ReviewRequest(
                repository_full_name=repo_name,
                pull_request_number=pr_number,
                head_sha=payload.pull_request.head["sha"],
                base_sha=payload.pull_request.base["sha"],
                files_to_review=[fc.filename for fc in file_changes],
                context={
                    "pr_title": payload.pull_request.title,
                    "pr_body": payload.pull_request.body or "",
                    "author": payload.pull_request.user.login,
                    "action": payload.action
                }
            )
            
            # Conduct review
            review_response = await self.review_engine.review_pull_request(
                review_request,
                file_changes,
                file_contents
            )
            
            # Post results
            if review_response.comments:
                # Post detailed review with line comments
                await self.github_client.post_review_comments(
                    repo_name,
                    pr_number,
                    review_response.comments,
                    review_response.summary,
                    payload.pull_request.head["sha"]
                )
            else:
                # Post summary comment only
                await self.github_client.post_summary_comment(
                    repo_name,
                    pr_number,
                    review_response.summary
                )
            
            logger.info(
                "Completed code review",
                request_id=request_id,
                comments_count=len(review_response.comments),
                duration_seconds=review_response.review_duration_seconds
            )
            
        except asyncio.CancelledError:
            logger.info("Review cancelled", request_id=request_id)
            raise
        except Exception as e:
            logger.error(
                "Error during code review",
                request_id=request_id,
                error=str(e),
                exc_info=True
            )
            
            # Post error comment
            try:
                await self.github_client.post_summary_comment(
                    repo_name,
                    pr_number,
                    f"❌ Code review failed due to an error: {str(e)}\n\n"
                    "Please check the logs or try again later."
                )
            except Exception as post_error:
                logger.error(
                    "Failed to post error comment",
                    request_id=request_id,
                    error=str(post_error)
                )
        finally:
            # Clean up task reference
            if request_id in self._active_tasks:
                del self._active_tasks[request_id]
    
    async def trigger_manual_review(
        self,
        repo_full_name: str,
        pr_number: int,
        force: bool = False
    ) -> Dict[str, str]:
        """Trigger a manual review of a pull request."""
        request_id = f"{repo_full_name}#{pr_number}"
        
        # Check if review is already running
        if request_id in self._active_tasks and not force:
            return {
                "status": "already_running",
                "request_id": request_id,
                "message": "Review is already in progress"
            }
        
        try:
            # Get pull request info
            pr = await self.github_client.get_pull_request(repo_full_name, pr_number)
            
            # Create mock payload for manual review
            from ..models.github import GitHubWebhookPayload, Repository, User
            
            # This is a simplified payload for manual reviews
            # In a real implementation, you'd want to construct this more carefully
            mock_payload = GitHubWebhookPayload(
                action="manual_review",
                number=pr_number,
                pull_request=pr,  # This would need proper conversion
                repository=Repository(
                    id=pr.base.repo.id,
                    name=pr.base.repo.name,
                    full_name=repo_full_name,
                    private=pr.base.repo.private,
                    html_url=pr.base.repo.html_url,
                    description=pr.base.repo.description,
                    language=pr.base.repo.language,
                    default_branch=pr.base.repo.default_branch,
                    owner=User(
                        id=pr.base.repo.owner.id,
                        login=pr.base.repo.owner.login,
                        avatar_url=pr.base.repo.owner.avatar_url,
                        html_url=pr.base.repo.owner.html_url,
                        type=pr.base.repo.owner.type
                    )
                ),
                sender=User(
                    id=0,
                    login="manual-trigger",
                    avatar_url="",
                    html_url="",
                    type="User"
                )
            )
            
            # Cancel existing review if force is True
            if force and request_id in self._active_tasks:
                self._active_tasks[request_id].cancel()
                logger.info("Force cancelled previous review", request_id=request_id)
            
            # Start review
            task = asyncio.create_task(
                self._conduct_review(mock_payload),
                name=f"manual-review-{request_id}"
            )
            self._active_tasks[request_id] = task
            
            return {
                "status": "started",
                "request_id": request_id,
                "message": "Manual review started"
            }
            
        except Exception as e:
            logger.error(
                "Error starting manual review",
                request_id=request_id,
                error=str(e)
            )
            return {
                "status": "error",
                "request_id": request_id,
                "message": f"Failed to start review: {str(e)}"
            }
    
    def get_active_reviews(self) -> Dict[str, Dict[str, str]]:
        """Get information about active reviews."""
        active_reviews = {}
        for request_id, task in self._active_tasks.items():
            active_reviews[request_id] = {
                "status": "running" if not task.done() else "completed",
                "task_name": task.get_name()
            }
        return active_reviews
