"""Entry point: uv run python -m granola_fast_mcp"""

from granola_fast_mcp.server import mcp


def main() -> None:
    mcp.run()


main()
