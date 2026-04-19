#!/usr/bin/env python3
"""
TermBot Quick Launcher

Quick start script for TermBot CLI mode.
This is a convenience wrapper that calls the standard CLI entry point.

For standard entry point, use: python -m termbot.cli or python cli.py
"""
import sys


def main() -> int:
    """Main entry point - delegates to cli.py"""
    # Import and run the CLI main function
    from cli import main as cli_main
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
