"""Core review engine for analyzing pull requests."""

import asyncio
import fnmatch
import time
from typing import Dict, List, Optional, Tuple

import structlog

from ..config import Settings, get_settings
from ..models.github import FileChange
from ..models.review import ReviewComment, ReviewRequest, ReviewResponse
from .ai_service import AIService

logger = structlog.get_logger(__name__)


class ReviewEngine:
    """Core engine for conducting code reviews."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize review engine."""
        self.settings = settings or get_settings()
        self._active_reviews: Dict[str, asyncio.Task] = {}
    
    async def review_pull_request(
        self,
        request: ReviewRequest,
        file_changes: List[FileChange],
        file_contents: Dict[str, str]
    ) -> ReviewResponse:
        """Review a pull request and generate comments."""
        start_time = time.time()
        request_id = f"{request.repository_full_name}#{request.pull_request_number}"
        
        logger.info(
            "Starting pull request review",
            request_id=request_id,
            files_count=len(file_changes),
            head_sha=request.head_sha
        )
        
        try:
            # Filter files to review
            files_to_review = self._filter_files_for_review(file_changes)
            
            if not files_to_review:
                logger.info("No files to review after filtering", request_id=request_id)
                return self._create_empty_response(request, start_time)
            
            # Limit number of files
            if len(files_to_review) > self.settings.max_files_to_review:
                logger.warning(
                    "Too many files to review, limiting",
                    request_id=request_id,
                    total_files=len(files_to_review),
                    max_files=self.settings.max_files_to_review
                )
                files_to_review = files_to_review[:self.settings.max_files_to_review]
            
            # Analyze files concurrently
            all_comments = []
            async with AIService(self.settings) as ai_service:
                tasks = []
                
                for file_change in files_to_review:
                    if file_change.filename in file_contents:
                        task = self._analyze_file(
                            ai_service,
                            file_change,
                            file_contents[file_change.filename],
                            request_id
                        )
                        tasks.append(task)
                
                # Execute with concurrency limit
                semaphore = asyncio.Semaphore(self.settings.max_concurrent_reviews)
                
                async def bounded_task(task):
                    async with semaphore:
                        return await task
                
                results = await asyncio.gather(
                    *[bounded_task(task) for task in tasks],
                    return_exceptions=True
                )
                
                # Collect successful results
                for result in results:
                    if isinstance(result, list):
                        all_comments.extend(result)
                    elif isinstance(result, Exception):
                        logger.error(
                            "Error analyzing file",
                            request_id=request_id,
                            error=str(result)
                        )
                
                # Generate summary
                summary = await ai_service.generate_summary(all_comments)
            
            # Create response
            duration = time.time() - start_time
            response = ReviewResponse(
                request_id=request_id,
                repository_full_name=request.repository_full_name,
                pull_request_number=request.pull_request_number,
                comments=all_comments,
                summary=summary,
                total_issues=len(all_comments),
                issues_by_severity=self._count_by_severity(all_comments),
                issues_by_type=self._count_by_type(all_comments),
                review_duration_seconds=duration,
                ai_model_used=self.settings.ai_model.value
            )
            
            logger.info(
                "Completed pull request review",
                request_id=request_id,
                total_comments=len(all_comments),
                duration_seconds=duration,
                issues_by_severity=response.issues_by_severity
            )
            
            return response
            
        except Exception as e:
            logger.error(
                "Error during pull request review",
                request_id=request_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _analyze_file(
        self,
        ai_service: AIService,
        file_change: FileChange,
        file_content: str,
        request_id: str
    ) -> List[ReviewComment]:
        """Analyze a single file and return review comments."""
        try:
            # Skip if file is too large
            lines = file_content.count('\n') + 1
            if lines > self.settings.max_lines_per_file:
                logger.warning(
                    "Skipping large file",
                    request_id=request_id,
                    filename=file_change.filename,
                    lines=lines,
                    max_lines=self.settings.max_lines_per_file
                )
                return []
            
            # Build context
            context = self._build_file_context(file_change)
            
            # Analyze with AI
            comments = await ai_service.analyze_code_changes(
                file_path=file_change.filename,
                file_content=file_content,
                diff_content=file_change.patch or "",
                context=context
            )
            
            # Filter comments by severity
            filtered_comments = self._filter_comments_by_severity(comments)
            
            logger.debug(
                "Analyzed file",
                request_id=request_id,
                filename=file_change.filename,
                comments_found=len(comments),
                comments_after_filter=len(filtered_comments)
            )
            
            return filtered_comments
            
        except Exception as e:
            logger.error(
                "Error analyzing file",
                request_id=request_id,
                filename=file_change.filename,
                error=str(e)
            )
            return []
    
    def _filter_files_for_review(self, file_changes: List[FileChange]) -> List[FileChange]:
        """Filter files that should be reviewed."""
        filtered_files = []
        
        for file_change in file_changes:
            # Skip deleted files
            if file_change.status == "removed":
                continue
            
            # Check include patterns
            if not self._matches_patterns(file_change.filename, self.settings.include_patterns):
                continue
            
            # Check exclude patterns
            if self._matches_patterns(file_change.filename, self.settings.exclude_patterns):
                continue
            
            filtered_files.append(file_change)
        
        return filtered_files
    
    def _matches_patterns(self, filename: str, patterns: List[str]) -> bool:
        """Check if filename matches any of the patterns."""
        for pattern in patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False
    
    def _build_file_context(self, file_change: FileChange) -> str:
        """Build context information for file analysis."""
        context_parts = [
            f"File status: {file_change.status}",
            f"Changes: +{file_change.additions} -{file_change.deletions}"
        ]
        
        if file_change.previous_filename:
            context_parts.append(f"Renamed from: {file_change.previous_filename}")
        
        return " | ".join(context_parts)
    
    def _filter_comments_by_severity(self, comments: List[ReviewComment]) -> List[ReviewComment]:
        """Filter comments based on minimum severity level."""
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_level = severity_order.get(self.settings.min_severity_level.value, 1)
        
        return [
            comment for comment in comments
            if severity_order.get(comment.severity.value, 0) >= min_level
        ]
    
    def _count_by_severity(self, comments: List[ReviewComment]) -> Dict[str, int]:
        """Count comments by severity level."""
        counts = {}
        for comment in comments:
            severity = comment.severity.value
            counts[severity] = counts.get(severity, 0) + 1
        return counts
    
    def _count_by_type(self, comments: List[ReviewComment]) -> Dict[str, int]:
        """Count comments by review type."""
        counts = {}
        for comment in comments:
            review_type = comment.review_type.value
            counts[review_type] = counts.get(review_type, 0) + 1
        return counts
    
    def _create_empty_response(self, request: ReviewRequest, start_time: float) -> ReviewResponse:
        """Create an empty response when no files to review."""
        return ReviewResponse(
            request_id=f"{request.repository_full_name}#{request.pull_request_number}",
            repository_full_name=request.repository_full_name,
            pull_request_number=request.pull_request_number,
            comments=[],
            summary="No files found that match the review criteria.",
            total_issues=0,
            issues_by_severity={},
            issues_by_type={},
            review_duration_seconds=time.time() - start_time,
            ai_model_used=self.settings.ai_model.value
        )
    
    async def cancel_review(self, request_id: str) -> bool:
        """Cancel an active review."""
        if request_id in self._active_reviews:
            task = self._active_reviews[request_id]
            task.cancel()
            del self._active_reviews[request_id]
            logger.info("Cancelled review", request_id=request_id)
            return True
        return False
    
    def get_active_reviews(self) -> List[str]:
        """Get list of active review request IDs."""
        return list(self._active_reviews.keys())
