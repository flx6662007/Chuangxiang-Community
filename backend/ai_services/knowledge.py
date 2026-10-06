"""Compatibility imports; competition knowledge uses the shared BGE retrieval."""
from .competition_knowledge import retrieve_knowledge, rebuild_index  # noqa: F401
from information_library.semantic import SemanticError as EmbeddingUnavailable  # noqa: F401
