"""Module 4 — Context Management.

Keeps total tokens under budget by summarizing older turns, masking observation
noise, and applying lost-in-the-middle reordering when needed.
"""

from harness.context.manager import ContextManager

__all__ = ["ContextManager"]
