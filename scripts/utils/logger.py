"""
Rich logging utilities for the audiobook generation system.
"""

import sys
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.theme import Theme

# Custom theme for audiobook system
custom_theme = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red bold",
        "step": "blue bold",
        "highlight": "magenta",
    }
)

# Global console instance
console = Console(theme=custom_theme)


def info(message: str) -> None:
    """Print an info message."""
    console.print(f"[info]ℹ[/info] {message}")


def success(message: str) -> None:
    """Print a success message."""
    console.print(f"[success]✓[/success] {message}")


def warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[warning]⚠[/warning] {message}")


def error(message: str) -> None:
    """Print an error message."""
    console.print(f"[error]✗[/error] {message}")


def step(message: str, step_num: Optional[int] = None, total: Optional[int] = None) -> None:
    """Print a step message."""
    if step_num and total:
        console.print(f"[step][{step_num}/{total}][/step] {message}")
    else:
        console.print(f"[step]→[/step] {message}")


def header(message: str) -> None:
    """Print a header message."""
    console.print()
    console.rule(f"[bold]{message}[/bold]")
    console.print()


def create_progress() -> Progress:
    """Create a progress bar for long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def create_simple_progress() -> Progress:
    """Create a simple progress bar."""
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )
