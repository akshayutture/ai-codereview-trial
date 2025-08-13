"""Python Code Review Agent - AI-powered GitHub code review automation."""

__version__ = "1.0.0"
__author__ = "Code Review Agent"
__email__ = "agent@example.com"
__description__ = "AI-powered GitHub code review agent in Python"

from .config import Settings
from .main import app

__all__ = ["Settings", "app", "__version__"]
