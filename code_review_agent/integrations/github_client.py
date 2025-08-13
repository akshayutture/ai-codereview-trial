"""GitHub API client for pull request operations."""

import base64
from typing import Dict, List, Optional, Tuple

import structlog
from github import Github
from github.GithubException import GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository

from ..config import Settings, get_settings
from ..models.github import FileChange
from ..models.review import ReviewComment

logger = structlog.get_logger(__name__)


class GitHubClient:
    """Client for GitHub API operations."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize GitHub client."""
        self.settings = settings or get_settings()
        self._github = Github(self.settings.github_token)
    
    async def get_pull_request(self, repo_full_name: str, pr_number: int) -> PullRequest:
        """Get pull request information."""
        try:
            repo = self._github.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            
            logger.debug(
                "Retrieved pull request",
                repo=repo_full_name,
                pr_number=pr_number,
                title=pr.title,
                state=pr.state
            )
            
            return pr
            
        except GithubException as e:
            logger.error(
                "Error retrieving pull request",
                repo=repo_full_name,
                pr_number=pr_number,
                error=str(e)
            )
            raise
    
    async def get_pull_request_files(
        self, 
        repo_full_name: str, 
        pr_number: int
    ) -> List[FileChange]:
        """Get list of changed files in a pull request."""
        try:
            pr = await self.get_pull_request(repo_full_name, pr_number)
            files = pr.get_files()
            
            file_changes = []
            for file in files:
                file_change = FileChange(
                    filename=file.filename,
                    status=file.status,
                    additions=file.additions,
                    deletions=file.deletions,
                    changes=file.changes,
                    blob_url=file.blob_url,
                    raw_url=file.raw_url,
                    contents_url=file.contents_url,
                    patch=file.patch,
                    previous_filename=getattr(file, 'previous_filename', None)
                )
                file_changes.append(file_change)
            
            logger.debug(
                "Retrieved pull request files",
                repo=repo_full_name,
                pr_number=pr_number,
                files_count=len(file_changes)
            )
            
            return file_changes
            
        except GithubException as e:
            logger.error(
                "Error retrieving pull request files",
                repo=repo_full_name,
                pr_number=pr_number,
                error=str(e)
            )
            raise
    
    async def get_file_contents(
        self,
        repo_full_name: str,
        file_changes: List[FileChange],
        ref: str
    ) -> Dict[str, str]:
        """Get file contents for the specified files."""
        try:
            repo = self._github.get_repo(repo_full_name)
            file_contents = {}
            
            for file_change in file_changes:
                # Skip deleted files
                if file_change.status == "removed":
                    continue
                
                try:
                    # Get file content from the specific commit
                    content = repo.get_contents(file_change.filename, ref=ref)
                    
                    if content.encoding == "base64":
                        decoded_content = base64.b64decode(content.content).decode('utf-8')
                    else:
                        decoded_content = content.content
                    
                    file_contents[file_change.filename] = decoded_content
                    
                except GithubException as e:
                    if e.status == 404:
                        logger.warning(
                            "File not found",
                            repo=repo_full_name,
                            filename=file_change.filename,
                            ref=ref
                        )
                    else:
                        logger.error(
                            "Error retrieving file content",
                            repo=repo_full_name,
                            filename=file_change.filename,
                            ref=ref,
                            error=str(e)
                        )
                except UnicodeDecodeError:
                    logger.warning(
                        "Binary file skipped",
                        repo=repo_full_name,
                        filename=file_change.filename
                    )
            
            logger.debug(
                "Retrieved file contents",
                repo=repo_full_name,
                files_retrieved=len(file_contents),
                total_files=len(file_changes)
            )
            
            return file_contents
            
        except GithubException as e:
            logger.error(
                "Error retrieving file contents",
                repo=repo_full_name,
                ref=ref,
                error=str(e)
            )
            raise
    
    async def post_review_comments(
        self,
        repo_full_name: str,
        pr_number: int,
        comments: List[ReviewComment],
        summary: str,
        commit_sha: str
    ) -> bool:
        """Post review comments to a pull request."""
        try:
            pr = await self.get_pull_request(repo_full_name, pr_number)
            
            # Group comments by file for better organization
            comments_by_file = {}
            for comment in comments:
                if comment.file_path not in comments_by_file:
                    comments_by_file[comment.file_path] = []
                comments_by_file[comment.file_path].append(comment)
            
            # Post individual line comments
            review_comments = []
            for file_path, file_comments in comments_by_file.items():
                for comment in file_comments:
                    if comment.line_number:
                        review_comment = {
                            "path": file_path,
                            "line": comment.line_number,
                            "body": self._format_comment_body(comment)
                        }
                        review_comments.append(review_comment)
            
            # Create the review
            if review_comments or summary:
                review_body = self._format_review_body(summary, comments)
                
                # Determine review event based on severity
                event = self._determine_review_event(comments)
                
                pr.create_review(
                    body=review_body,
                    event=event,
                    comments=review_comments,
                    commit_id=commit_sha
                )
                
                logger.info(
                    "Posted review comments",
                    repo=repo_full_name,
                    pr_number=pr_number,
                    comments_count=len(review_comments),
                    event=event
                )
                
                return True
            else:
                logger.info(
                    "No comments to post",
                    repo=repo_full_name,
                    pr_number=pr_number
                )
                return False
                
        except GithubException as e:
            logger.error(
                "Error posting review comments",
                repo=repo_full_name,
                pr_number=pr_number,
                error=str(e)
            )
            raise
    
    async def post_summary_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        summary: str
    ) -> bool:
        """Post a summary comment to a pull request."""
        try:
            pr = await self.get_pull_request(repo_full_name, pr_number)
            
            # Check if we already posted a review comment
            existing_comments = pr.get_issue_comments()
            bot_marker = "<!-- code-review-agent-summary -->"
            
            for comment in existing_comments:
                if bot_marker in comment.body:
                    # Update existing comment
                    comment.edit(f"{bot_marker}\n{summary}")
                    logger.info(
                        "Updated existing summary comment",
                        repo=repo_full_name,
                        pr_number=pr_number
                    )
                    return True
            
            # Create new comment
            pr.create_issue_comment(f"{bot_marker}\n{summary}")
            
            logger.info(
                "Posted summary comment",
                repo=repo_full_name,
                pr_number=pr_number
            )
            
            return True
            
        except GithubException as e:
            logger.error(
                "Error posting summary comment",
                repo=repo_full_name,
                pr_number=pr_number,
                error=str(e)
            )
            raise
    
    def _format_comment_body(self, comment: ReviewComment) -> str:
        """Format a review comment body."""
        severity_emoji = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "💡",
            "low": "ℹ️"
        }
        
        type_emoji = {
            "security": "🔒",
            "performance": "⚡",
            "style": "🎨",
            "best_practices": "✨",
            "bug": "🐛",
            "maintainability": "🔧",
            "documentation": "📝"
        }
        
        emoji = severity_emoji.get(comment.severity.value, "💡")
        type_emoji_str = type_emoji.get(comment.review_type.value, "")
        
        body_parts = [
            f"{emoji} **{comment.severity.value.title()} {comment.review_type.value.replace('_', ' ').title()}** {type_emoji_str}",
            "",
            comment.message
        ]
        
        if comment.suggestion:
            body_parts.extend([
                "",
                "**Suggestion:**",
                comment.suggestion
            ])
        
        if comment.confidence < 0.8:
            body_parts.extend([
                "",
                f"*Confidence: {comment.confidence:.0%}*"
            ])
        
        return "\n".join(body_parts)
    
    def _format_review_body(self, summary: str, comments: List[ReviewComment]) -> str:
        """Format the main review body."""
        body_parts = [
            "## 🤖 AI Code Review",
            "",
            summary
        ]
        
        if comments:
            # Add statistics
            total_files = len(set(comment.file_path for comment in comments))
            body_parts.extend([
                "",
                f"**Files reviewed:** {total_files}",
                f"**Issues found:** {len(comments)}"
            ])
        
        body_parts.extend([
            "",
            "---",
            "*This review was generated by an AI code review agent. Please review the suggestions and apply your judgment.*"
        ])
        
        return "\n".join(body_parts)
    
    def _determine_review_event(self, comments: List[ReviewComment]) -> str:
        """Determine the appropriate review event based on comment severity."""
        if not comments:
            return "COMMENT"
        
        # Check for critical or high severity issues
        for comment in comments:
            if comment.severity.value in ["critical", "high"]:
                return "REQUEST_CHANGES"
        
        # If only medium/low severity issues, approve with comments
        return "COMMENT"
    
    async def check_permissions(self, repo_full_name: str) -> Tuple[bool, List[str]]:
        """Check if the bot has necessary permissions."""
        try:
            repo = self._github.get_repo(repo_full_name)
            permissions = []
            issues = []
            
            # Check if we can read the repository
            try:
                repo.get_contents("README.md")
                permissions.append("read")
            except GithubException:
                issues.append("Cannot read repository contents")
            
            # Check if we can create issues/comments
            try:
                # This is a dry run - we don't actually create anything
                permissions.append("write")
            except GithubException:
                issues.append("Cannot write to repository")
            
            logger.info(
                "Checked repository permissions",
                repo=repo_full_name,
                permissions=permissions,
                issues=issues
            )
            
            return len(issues) == 0, issues
            
        except GithubException as e:
            logger.error(
                "Error checking permissions",
                repo=repo_full_name,
                error=str(e)
            )
            return False, [f"Cannot access repository: {str(e)}"]
