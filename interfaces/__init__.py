"""
Interfaces module.

Provides interaction layer abstractions for different modes.
"""
from interfaces.base import BaseHandler
from interfaces.cli import CLIHandler
from interfaces.web import WebHandler, WebSession

__all__ = [
    "BaseHandler",
    "CLIHandler",
    "WebHandler",
    "WebSession",
]
