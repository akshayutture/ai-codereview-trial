"""AI service for generating code reviews."""

import asyncio
import json
import re
from typing import List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import Settings, get_settings
from ..models.review import ReviewComment, ReviewType, SeverityLevel


class AIService:
    """Service for AI-powered code analysis."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize AI service."""
        self.settings = settings or get_settings()
        self._client = httpx.AsyncClient(timeout=30.0)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def analyze_code_changes(
        self,
        file_path: str,
        file_content: str,
        diff_content: str,
        context: str = ""
    ) -> List[ReviewComment]:
        """Analyze code changes and generate review comments."""
        if self.settings.uses_openai_model:
            return await self._analyze_with_openai(file_path, file_content, diff_content, context)
        elif self.settings.uses_anthropic_model:
            return await self._analyze_with_anthropic(file_path, file_content, diff_content, context)
        else:
            raise ValueError(f"Unsupported AI model: {self.settings.ai_model}")
    
    async def _analyze_with_openai(
        self,
        file_path: str,
        file_content: str,
        diff_content: str,
        context: str
    ) -> List[ReviewComment]:
        """Analyze code using OpenAI API."""
        prompt = self._build_review_prompt(file_path, file_content, diff_content, context)
        
        payload = {
            "model": self.settings.ai_model.value,
            "messages": [
                {
                    "role": "system",
                    "content": self._get_system_prompt()
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"}
        }
        
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        response = await self._client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        return self._parse_ai_response(content, file_path)
    
    async def _analyze_with_anthropic(
        self,
        file_path: str,
        file_content: str,
        diff_content: str,
        context: str
    ) -> List[ReviewComment]:
        """Analyze code using Anthropic API."""
        prompt = self._build_review_prompt(file_path, file_content, diff_content, context)
        
        payload = {
            "model": self.settings.ai_model.value,
            "max_tokens": 2000,
            "temperature": 0.1,
            "system": self._get_system_prompt(),
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        response = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["content"][0]["text"]
        
        return self._parse_ai_response(content, file_path)
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for AI analysis."""
        return """You are an expert code reviewer. Analyze the provided code changes and identify issues related to:

1. Security vulnerabilities (SQL injection, XSS, authentication issues, etc.)
2. Performance problems (inefficient algorithms, memory leaks, etc.)
3. Code style and formatting issues
4. Best practices violations
5. Potential bugs and logic errors
6. Maintainability concerns

For each issue found, provide:
- Exact line number(s) where the issue occurs
- Clear description of the problem
- Suggested fix or improvement
- Severity level (low, medium, high, critical)
- Issue type (security, performance, style, best_practices, bug, maintainability)
- Confidence score (0.0 to 1.0)

Respond with a JSON object containing an array of "comments" with the following structure:
{
  "comments": [
    {
      "line_number": 42,
      "message": "Description of the issue",
      "suggestion": "Suggested fix",
      "severity": "medium",
      "review_type": "security",
      "confidence": 0.85
    }
  ]
}

Focus on actionable feedback and avoid nitpicking. Only report issues you're confident about."""
    
    def _build_review_prompt(
        self,
        file_path: str,
        file_content: str,
        diff_content: str,
        context: str
    ) -> str:
        """Build the review prompt for AI analysis."""
        language = self._detect_language(file_path)
        
        prompt = f"""Please review the following {language} code changes:

**File:** {file_path}
**Language:** {language}

**Context:** {context}

**Full File Content:**
```{language}
{file_content}
```

**Changes (diff):**
```diff
{diff_content}
```

Please analyze the changes and provide a code review focusing on the modified lines. Consider the full file context when evaluating the changes."""
        
        return prompt
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.clj': 'clojure',
            '.sh': 'bash',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sql': 'sql'
        }
        
        for ext, lang in extension_map.items():
            if file_path.lower().endswith(ext):
                return lang
        
        return 'text'
    
    def _parse_ai_response(self, content: str, file_path: str) -> List[ReviewComment]:
        """Parse AI response and convert to ReviewComment objects."""
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group()
            
            data = json.loads(content)
            comments = []
            
            for comment_data in data.get("comments", []):
                try:
                    comment = ReviewComment(
                        file_path=file_path,
                        line_number=comment_data.get("line_number"),
                        message=comment_data["message"],
                        suggestion=comment_data.get("suggestion"),
                        severity=SeverityLevel(comment_data.get("severity", "medium")),
                        review_type=ReviewType(comment_data.get("review_type", "best_practices")),
                        confidence=float(comment_data.get("confidence", 0.8))
                    )
                    comments.append(comment)
                except (ValueError, KeyError) as e:
                    # Skip invalid comments but log the error
                    continue
            
            return comments
            
        except json.JSONDecodeError:
            # Fallback: create a single comment with the raw response
            return [
                ReviewComment(
                    file_path=file_path,
                    message=f"AI analysis completed but response format was unexpected: {content[:200]}...",
                    severity=SeverityLevel.LOW,
                    review_type=ReviewType.BEST_PRACTICES,
                    confidence=0.5
                )
            ]
    
    async def generate_summary(self, all_comments: List[ReviewComment]) -> str:
        """Generate a summary of all review comments."""
        if not all_comments:
            return "No issues found in this pull request. Great work! 🎉"
        
        # Group comments by severity and type
        by_severity = {}
        by_type = {}
        
        for comment in all_comments:
            severity = comment.severity.value
            review_type = comment.review_type.value
            
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_type[review_type] = by_type.get(review_type, 0) + 1
        
        # Build summary
        total_issues = len(all_comments)
        summary_parts = [f"Found {total_issues} issue{'s' if total_issues != 1 else ''} in this pull request:"]
        
        # Add severity breakdown
        if by_severity:
            severity_parts = []
            for severity in ["critical", "high", "medium", "low"]:
                count = by_severity.get(severity, 0)
                if count > 0:
                    severity_parts.append(f"{count} {severity}")
            
            if severity_parts:
                summary_parts.append(f"**Severity:** {', '.join(severity_parts)}")
        
        # Add type breakdown
        if by_type:
            type_parts = []
            for issue_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
                type_parts.append(f"{count} {issue_type.replace('_', ' ')}")
            
            if type_parts:
                summary_parts.append(f"**Categories:** {', '.join(type_parts[:3])}")  # Top 3
        
        # Add recommendations
        critical_count = by_severity.get("critical", 0)
        high_count = by_severity.get("high", 0)
        
        if critical_count > 0:
            summary_parts.append("⚠️ **Critical issues found** - please address before merging.")
        elif high_count > 0:
            summary_parts.append("⚠️ **High priority issues found** - recommend addressing before merging.")
        else:
            summary_parts.append("✅ No critical issues found. Consider addressing the suggestions for improved code quality.")
        
        return "\n\n".join(summary_parts)
