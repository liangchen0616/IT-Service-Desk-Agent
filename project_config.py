"""Backward-compatible configuration imports."""
from core.config import PROJECT_ROOT, ProjectConfig, load_config

__all__ = ["PROJECT_ROOT", "ProjectConfig", "load_config"]
