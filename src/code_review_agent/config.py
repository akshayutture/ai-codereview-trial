"""Configuration management for the code review agent."""

import os
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(str, Enum):
    """Environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AIModel(str, Enum):
    """Supported AI models."""
    GPT_4_TURBO = "gpt-4-turbo-preview"
    GPT_4 = "gpt-4"
    GPT_35_TURBO = "gpt-3.5-turbo"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"


class SeverityLevel(str, Enum):
    """Issue severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # GitHub Configuration
    github_token: str = Field(..., description="GitHub personal access token")
    github_webhook_secret: str = Field(..., description="GitHub webhook secret")
    
    # AI Configuration
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key")
    ai_model: AIModel = Field(AIModel.GPT_4_TURBO, description="AI model to use")
    
    # Server Configuration
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    environment: Environment = Field(Environment.DEVELOPMENT, description="Environment")
    
    # Logging Configuration
    log_level: LogLevel = Field(LogLevel.INFO, description="Logging level")
    log_format: str = Field("json", description="Log format (json or text)")
    log_file: Optional[str] = Field("logs/code_review_agent.log", description="Log file path")
    enable_structured_logging: bool = Field(True, description="Enable structured logging")
    
    # Review Configuration
    max_files_to_review: int = Field(20, description="Maximum files to review per PR")
    max_lines_per_file: int = Field(1000, description="Maximum lines per file to review")
    review_timeout_seconds: int = Field(60, description="Review timeout in seconds")
    max_concurrent_reviews: int = Field(5, description="Maximum concurrent reviews")
    
    # Review Rules
    enable_security_checks: bool = Field(True, description="Enable security checks")
    enable_performance_checks: bool = Field(True, description="Enable performance checks")
    enable_style_checks: bool = Field(True, description="Enable style checks")
    enable_best_practices: bool = Field(True, description="Enable best practices checks")
    min_severity_level: SeverityLevel = Field(SeverityLevel.MEDIUM, description="Minimum severity level")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(60, description="Rate limit per minute")
    rate_limit_burst: int = Field(10, description="Rate limit burst")
    
    # Cache Configuration
    redis_url: Optional[str] = Field(None, description="Redis URL for caching")
    cache_ttl_seconds: int = Field(3600, description="Cache TTL in seconds")
    
    # File Patterns
    include_patterns: List[str] = Field(
        default=[
            "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.java", "*.go", 
            "*.rs", "*.cpp", "*.c", "*.h", "*.hpp", "*.cs", "*.php", 
            "*.rb", "*.swift", "*.kt", "*.scala", "*.clj", "*.sh"
        ],
        description="File patterns to include in review"
    )
    exclude_patterns: List[str] = Field(
        default=[
            "*.min.js", "*.min.css", "node_modules/**", "__pycache__/**",
            "*.pyc", "*.pyo", "*.pyd", ".git/**", ".venv/**", "venv/**",
            "build/**", "dist/**", "target/**", "*.lock", "*.log"
        ],
        description="File patterns to exclude from review"
    )
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("ai_model")
    def validate_ai_model(cls, v: AIModel, values: dict) -> AIModel:
        """Validate AI model configuration."""
        openai_key = values.get("openai_api_key")
        anthropic_key = values.get("anthropic_api_key")
        
        if v.value.startswith("gpt") and not openai_key:
            raise ValueError("OpenAI API key required for GPT models")
        elif v.value.startswith("claude") and not anthropic_key:
            raise ValueError("Anthropic API key required for Claude models")
            
        return v
    
    @validator("log_file")
    def validate_log_file(cls, v: Optional[str]) -> Optional[str]:
        """Ensure log directory exists."""
        if v:
            log_path = Path(v)
            log_path.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key)
    
    @property
    def has_anthropic_key(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(self.anthropic_api_key)
    
    @property
    def uses_openai_model(self) -> bool:
        """Check if using OpenAI model."""
        return self.ai_model.value.startswith("gpt")
    
    @property
    def uses_anthropic_model(self) -> bool:
        """Check if using Anthropic model."""
        return self.ai_model.value.startswith("claude")


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
