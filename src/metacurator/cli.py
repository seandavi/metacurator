"""CLI — thin adapter over the deterministic API. Implement to SPEC 120. [deterministic]

``metacurator <command>`` mirrors the tools (resolve, archive, acquire, ground, diff,
run). Same functions underlie the Python API and the MCP server — three faces, one impl.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    help="metacurator — reproduce curated, ontology-grounded sample metadata from papers.",
    add_completion=False,
)


@app.command()
def version() -> None:
    """Print the metacurator version."""
    from . import __version__

    typer.echo(__version__)


# Commands (resolve / archive / acquire / ground / diff / run) are added as the
# corresponding specs (020–110) are implemented. See SPEC 120.


if __name__ == "__main__":
    app()
