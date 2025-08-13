"""Command-line interface for the code review agent."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .config import get_settings
from .integrations.github_client import GitHubClient
from .utils.logging import setup_logging
from .webhooks.github_webhook import GitHubWebhookHandler

app = typer.Typer(
    name="code-review-agent",
    help="AI-powered GitHub code review agent",
    add_completion=False
)
console = Console()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    log_level: str = typer.Option("info", help="Log level"),
):
    """Start the code review agent server."""
    settings = get_settings()
    setup_logging(settings)
    
    console.print(f"🚀 Starting Code Review Agent on {host}:{port}")
    console.print(f"📊 Environment: {settings.environment.value}")
    console.print(f"🤖 AI Model: {settings.ai_model.value}")
    
    uvicorn.run(
        "code_review_agent.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower()
    )


@app.command()
def config():
    """Show current configuration."""
    settings = get_settings()
    
    table = Table(title="Code Review Agent Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    # Server settings
    table.add_row("Host", settings.host)
    table.add_row("Port", str(settings.port))
    table.add_row("Environment", settings.environment.value)
    table.add_row("Log Level", settings.log_level.value)
    
    # AI settings
    table.add_row("AI Model", settings.ai_model.value)
    table.add_row("Has OpenAI Key", "✅" if settings.has_openai_key else "❌")
    table.add_row("Has Anthropic Key", "✅" if settings.has_anthropic_key else "❌")
    
    # Review settings
    table.add_row("Max Files", str(settings.max_files_to_review))
    table.add_row("Max Lines per File", str(settings.max_lines_per_file))
    table.add_row("Review Timeout", f"{settings.review_timeout_seconds}s")
    table.add_row("Max Concurrent", str(settings.max_concurrent_reviews))
    
    # GitHub settings
    table.add_row("Has GitHub Token", "✅" if settings.github_token else "❌")
    table.add_row("Has Webhook Secret", "✅" if settings.github_webhook_secret else "❌")
    
    console.print(table)


@app.command()
def test_github(
    repo: str = typer.Argument(..., help="Repository name (owner/repo)"),
):
    """Test GitHub API connection and permissions."""
    async def _test():
        settings = get_settings()
        setup_logging(settings)
        
        console.print(f"🔍 Testing GitHub connection for {repo}")
        
        try:
            client = GitHubClient(settings)
            has_access, issues = await client.check_permissions(repo)
            
            if has_access:
                console.print("✅ GitHub connection successful!")
                console.print("✅ Repository access confirmed")
            else:
                console.print("❌ GitHub connection failed!")
                for issue in issues:
                    console.print(f"  • {issue}")
                    
        except Exception as e:
            console.print(f"❌ Error: {e}")
    
    asyncio.run(_test())


@app.command()
def review(
    repo: str = typer.Argument(..., help="Repository name (owner/repo)"),
    pr_number: int = typer.Argument(..., help="Pull request number"),
    force: bool = typer.Option(False, help="Force review even if already running"),
):
    """Trigger a manual code review."""
    async def _review():
        settings = get_settings()
        setup_logging(settings)
        
        console.print(f"🔍 Starting manual review for {repo}#{pr_number}")
        
        try:
            handler = GitHubWebhookHandler(settings)
            result = await handler.trigger_manual_review(repo, pr_number, force)
            
            if result["status"] == "started":
                console.print("✅ Review started successfully!")
                console.print(f"📝 Request ID: {result['request_id']}")
            elif result["status"] == "already_running":
                console.print("⚠️ Review already in progress")
                console.print("Use --force to cancel and restart")
            else:
                console.print(f"❌ Review failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            console.print(f"❌ Error: {e}")
    
    asyncio.run(_review())


@app.command()
def status():
    """Show agent status and active reviews."""
    async def _status():
        settings = get_settings()
        setup_logging(settings)
        
        try:
            handler = GitHubWebhookHandler(settings)
            active_reviews = handler.get_active_reviews()
            
            console.print("📊 Code Review Agent Status")
            console.print(f"🤖 AI Model: {settings.ai_model.value}")
            console.print(f"📈 Active Reviews: {len(active_reviews)}")
            
            if active_reviews:
                table = Table(title="Active Reviews")
                table.add_column("Request ID", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Task Name", style="yellow")
                
                for request_id, info in active_reviews.items():
                    table.add_row(
                        request_id,
                        info["status"],
                        info["task_name"]
                    )
                
                console.print(table)
            else:
                console.print("✅ No active reviews")
                
        except Exception as e:
            console.print(f"❌ Error: {e}")
    
    asyncio.run(_status())


@app.command()
def init(
    directory: Optional[Path] = typer.Argument(None, help="Directory to initialize"),
):
    """Initialize a new code review agent configuration."""
    if directory is None:
        directory = Path.cwd()
    
    env_file = directory / ".env"
    
    if env_file.exists():
        overwrite = typer.confirm(f".env file already exists in {directory}. Overwrite?")
        if not overwrite:
            console.print("❌ Initialization cancelled")
            return
    
    # Copy .env.example to .env
    try:
        from importlib import resources
        
        # Read the example file from the package
        example_content = """# GitHub Configuration
GITHUB_TOKEN=ghp_your_github_personal_access_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here

# AI Configuration (Choose one or both)
OPENAI_API_KEY=sk-your_openai_api_key_here
ANTHROPIC_API_KEY=sk-ant-your_anthropic_api_key_here

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=development

# Review Configuration
AI_MODEL=gpt-4-turbo-preview
MAX_FILES_TO_REVIEW=20
MAX_LINES_PER_FILE=1000
REVIEW_TIMEOUT_SECONDS=60
MAX_CONCURRENT_REVIEWS=5

# Review Rules
ENABLE_SECURITY_CHECKS=true
ENABLE_PERFORMANCE_CHECKS=true
ENABLE_STYLE_CHECKS=true
ENABLE_BEST_PRACTICES=true
MIN_SEVERITY_LEVEL=medium
"""
        
        env_file.write_text(example_content)
        console.print(f"✅ Created .env file in {directory}")
        console.print("📝 Please edit the .env file with your configuration")
        
    except Exception as e:
        console.print(f"❌ Error creating .env file: {e}")


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
