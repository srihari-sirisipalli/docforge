"""
DocForge — Storage Package
============================

SQLite-based state persistence with transaction safety.
"""

from docforge.storage.database import StateDB
from docforge.storage.schema import configure_db, init_schema
from docforge.storage.transactions import TransactionManager

__all__ = ["StateDB", "TransactionManager", "configure_db", "init_schema"]
