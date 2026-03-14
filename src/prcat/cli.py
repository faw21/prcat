"""prcat CLI entry point."""
from __future__ import annotations

import subprocess
import sys

import click
from rich.console import Console

from . import __version__
from .display import console, print_compact, print_pr_header, print_review
from .fetcher import fetch_pr
from .reviewer import review_pr

err_console = Console(stderr=True)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("pr_ref")
@click.option(
    "--repo", "-r",
    default=None,
    metavar="OWNER/REPO",
    help="GitHub repository (auto-detected from git remote if omitted).",
)
@click.option(
    "--style", "-s",
    default="review",
    type=click.Choice(["review", "summary", "risks"], case_sensitive=False),
    show_default=True,
    help="Review style.",
)
@click.option(
    "--provider",
    default="claude",
    type=click.Choice(["claude", "openai", "ollama"], case_sensitive=False),
    show_default=True,
    help="AI provider.",
)
@click.option(
    "--model", "-m",
    default=None,
    help="Override AI model (e.g. claude-sonnet-4-5, gpt-4o, qwen2.5:7b).",
)
@click.option(
    "--no-comments",
    is_flag=True,
    default=False,
    help="Skip fetching existing PR comments.",
)
@click.option(
    "--compact",
    is_flag=True,
    default=False,
    help="One-line output (for CI/scripts). Exit 1 if needs-major-changes.",
)
@click.option(
    "--copy",
    is_flag=True,
    default=False,
    help="Copy review to clipboard.",
)
@click.option(
    "--output", "-o",
    default=None,
    metavar="FILE",
    help="Save review to a file.",
)
@click.version_option(__version__, prog_name="prcat")
def main(
    pr_ref: str,
    repo: str | None,
    style: str,
    provider: str,
    model: str | None,
    no_comments: bool,
    compact: bool,
    copy: bool,
    output: str | None,
) -> None:
    """AI-powered PR reviewer — understand any pull request in seconds.

    PR_REF can be:
    \b
      123                            # PR number in current repo
      owner/repo#123                 # explicit repo
      https://github.com/org/r/pull/1  # full URL
    """
    try:
        with console.status(f"Fetching PR {pr_ref}...", spinner="dots"):
            pr = fetch_pr(pr_ref, repo=repo, include_comments=not no_comments)

        if not compact:
            print_pr_header(pr)

        with console.status(f"Reviewing with {provider}...", spinner="dots"):
            result = review_pr(pr, style=style, provider=provider, model=model)

        if compact:
            print_compact(result)
        else:
            print_review(result)

        if copy:
            _copy_to_clipboard(result.raw_text)
            console.print("[dim]Review copied to clipboard.[/dim]")

        if output:
            with open(output, "w") as f:
                f.write(f"# PR #{result.pr_number}: {result.pr_title}\n\n")
                f.write(result.raw_text)
            console.print(f"[dim]Review saved to {output}[/dim]")

        if result.has_critical:
            sys.exit(1)

    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(2)
    except KeyboardInterrupt:
        err_console.print("\n[yellow]Cancelled.[/yellow]")
        sys.exit(130)
    except Exception as e:
        err_console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(2)


def _copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard."""
    import platform
    import subprocess

    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        elif system == "Linux":
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        elif system == "Windows":
            subprocess.run(["clip"], input=text.encode(), check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass  # clipboard copy is best-effort
