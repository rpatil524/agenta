# Avoid importing adapter here to prevent SDK dependency issues in standalone scripts
# Import directly when needed:
#   from oss.src.core.tools.providers.composio.adapter import ComposioAdapter

__all__ = [
    "ComposioAdapter",
    "ComposioToolConnectionData",
]


def __getattr__(name):
    """Lazy import to avoid SDK dependency on module import."""
    if name == "ComposioAdapter":
        from oss.src.core.tools.providers.composio.adapter import ComposioAdapter

        return ComposioAdapter
    if name == "ComposioToolConnectionData":
        from oss.src.core.tools.providers.composio.dtos import (
            ComposioToolConnectionData,
        )

        return ComposioToolConnectionData
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
