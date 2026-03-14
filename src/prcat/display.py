"""Rich-formatted display for prcat reviews."""
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .fetcher import PRData
from .reviewer import ReviewResult

console = Console()


_VERDICT_STYLE = {
    "lgtm":                 ("LGTM ✅", "bold green"),
    "needs-minor-changes":  ("Needs minor changes ⚠️", "bold yellow"),
    "needs-major-changes":  ("Needs major changes 🚨", "bold red"),
    "reviewed":             ("Reviewed", "bold cyan"),
}


def print_pr_header(pr: PRData) -> None:
    lines = [
        f"[bold]PR #{pr.number}:[/bold] {pr.title}",
        f"[dim]{pr.url}[/dim]",
        f"[cyan]{pr.head_branch}[/cyan] → [cyan]{pr.base_branch}[/cyan]  "
        f"[green]+{pr.additions}[/green]/[red]-{pr.deletions}[/red]  "
        f"{len(pr.files_changed)} file(s)",
    ]
    console.print(Panel("\n".join(lines), title="[bold blue]prcat[/bold blue]", border_style="blue"))


def print_review(result: ReviewResult) -> None:
    label, style = _VERDICT_STYLE.get(result.verdict, ("Reviewed", "bold cyan"))
    verdict_text = Text(f" {label} ", style=style)
    console.print(verdict_text)

    if result.diff_truncated:
        console.print("[yellow dim]Note: diff was truncated to fit token budget.[/yellow dim]")

    console.print(Markdown(result.raw_text))


def print_compact(result: ReviewResult) -> None:
    """Single-line summary for CI/scripts."""
    label, _ = _VERDICT_STYLE.get(result.verdict, ("Reviewed", ""))
    console.print(f"PR #{result.pr_number} [{result.verdict.upper()}] — {label}")
