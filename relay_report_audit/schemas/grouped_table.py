"""
Normalized representation for grouped / two-row GFM pipe table headers.

Used by deterministic markdown parsing (protection-style and similar CT layouts).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TableColumnGroup(BaseModel):
    """One top-level header with its physical subcolumns left-to-right."""

    model_config = ConfigDict(extra="forbid")

    group: str = Field(min_length=1, description="Merged group label for this column span.")
    columns: list[str] = Field(
        min_length=1,
        description="Subcolumn labels under this group (e.g. X2, X4, X6).",
    )


class GroupedTableHeaderLayout(BaseModel):
    """Semantic grouping plus one flat header string per table column."""

    model_config = ConfigDict(extra="forbid")

    grouped_headers: list[TableColumnGroup] = Field(
        min_length=1,
        description="Ordered groups; each lists subcolumns in document order.",
    )
    flat_headers: list[str] = Field(
        min_length=1,
        description="One stable label per physical column (for backward-compatible maps).",
    )


__all__ = ["GroupedTableHeaderLayout", "TableColumnGroup"]
