"""
DocForge — Rename Engine
==========================

Executes file rename and move operations with full transaction safety.
Supports dry-run mode (preview only) and requires user confirmation
before making any changes.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from docforge.infra.logging import get_logger
from docforge.naming.collision import CollisionResolver
from docforge.organizer.tree_builder import FolderOrganizer
from docforge.storage.database import StateDB
from docforge.storage.transactions import TransactionManager

logger = get_logger(__name__)
console = Console()


class RenameEngine:
    """Executes rename/move operations with transaction safety."""

    def __init__(
        self,
        db: StateDB,
        collision_strategy: str = "suffix",
        organizer: FolderOrganizer | None = None,
    ):
        self.db = db
        self.collision = CollisionResolver(strategy=collision_strategy)
        self.organizer = organizer
        self.txn = TransactionManager(db)

    def execute(self, job_id: str, dry_run: bool = True) -> dict:
        """Execute renames for all completed documents.

        Args:
            job_id:  Job ID for transaction tracking.
            dry_run: If True, only preview — don't touch files.

        Returns:
            Summary dict with counts of operations.
        """
        records = self.db.get_completed_records()

        if not records:
            console.print("[yellow]No documents ready for renaming.[/yellow]")
            return {"total": 0, "renamed": 0, "skipped": 0, "errors": 0}

        # Build operations list
        operations: list[dict] = []
        skipped = 0

        for rec in records:
            canonical = rec.get("canonical_name", "")
            original = rec.get("original_path", "")

            if not canonical or not original:
                skipped += 1
                continue

            # Resolve collisions
            final_name = self.collision.resolve(canonical, rec["file_id"])

            # Compute target path
            if self.organizer and rec.get("target_dir"):
                target = str(Path(rec["target_dir"]) / final_name)
            else:
                target = str(Path(original).parent / final_name)

            # Skip if already at target
            if Path(original).resolve() == Path(target).resolve():
                skipped += 1
                continue

            # Create mkdir operation if needed
            target_dir = str(Path(target).parent)
            if not Path(target_dir).exists():
                operations.append({
                    "file_id": rec["file_id"],
                    "operation": "mkdir",
                    "source_path": "",
                    "target_path": target_dir,
                })

            # Create rename/move operation
            operations.append({
                "file_id": rec["file_id"],
                "operation": "rename" if Path(original).parent == Path(target).parent else "move",
                "source_path": original,
                "target_path": target,
            })

        # Execute or preview
        if dry_run:
            console.print(
                f"\n[bold cyan]Dry run:[/bold cyan] {len(operations)} operations "
                f"({len(records)} documents, {skipped} skipped)"
            )
            console.print("[dim]Run with --execute to apply changes.[/dim]\n")
            return {
                "total": len(records),
                "operations": len(operations),
                "skipped": skipped,
                "errors": 0,
                "dry_run": True,
            }

        # Execute with transaction safety
        logger.info("Executing %d operations...", len(operations))
        success = self.txn.execute_batch(job_id, operations)

        result = {
            "total": len(records),
            "operations": len(operations),
            "skipped": skipped,
            "errors": 0 if success else 1,
            "dry_run": False,
            "success": success,
        }

        if success:
            console.print(f"\n[bold green]Success![/bold green] {len(operations)} operations completed.")
        else:
            console.print(f"\n[bold red]Failed![/bold red] Operations have been rolled back.")

        return result
