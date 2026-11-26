"""manifest_er - entity resolution for messy customer names in cargo manifests."""

from .cleaning import basic, clean_name
from .matching import match_key
from .memory import load_master, resolve, save_master, standardize

__all__ = ["basic", "clean_name", "match_key", "resolve", "standardize",
           "load_master", "save_master"]
__version__ = "1.1.0"
