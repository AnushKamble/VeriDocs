"""
Financial table reconstruction: 2D header matrix, multi-row headers, spans, and cell locators.
"""

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, Tag

from veridocs.ingestion.numeric_normalizer import (
    extract_unit_and_multiplier,
    normalize_financial_number,
)
from veridocs.schemas.data_models import TableCell, TableRecord


class TableParser:
    """
    Parses an HTML <table> element into a structured TableRecord with
    resolved multi-level column headers, row labels, cells, units, and locators.
    """

    def __init__(self, table_tag: Tag, table_id: str, document_id: str, section_id: str = ""):
        self.table_tag = table_tag
        self.table_id = table_id
        self.document_id = document_id
        self.section_id = section_id
        self.parse_warnings: List[str] = []
        self.footnotes: List[str] = []

    def _extract_caption_and_units(self) -> Tuple[str, Optional[str]]:
        """Extracts table caption and declared unit statement."""
        caption_text = ""
        caption_tag = self.table_tag.find("caption")
        if caption_tag:
            caption_text = caption_tag.get_text(" ", strip=True)

        # Look in preceding sibling tags if caption tag is absent
        if not caption_text:
            prev = self.table_tag.find_previous_sibling(["p", "div", "b", "strong"])
            if prev and ("table" in prev.get_text().lower() or len(prev.get_text().strip()) < 150):
                caption_text = prev.get_text(" ", strip=True)

        # Search for units in caption or first few rows
        sample_text = caption_text + " " + " ".join(
            tr.get_text(" ", strip=True) for tr in self.table_tag.find_all("tr", limit=3)
        )
        unit_name, _ = extract_unit_and_multiplier(sample_text)
        return caption_text or f"Table {self.table_id}", unit_name

    def _build_raw_grid(self) -> List[List[Dict[str, Any]]]:
        """
        Builds a 2D matrix of cells expanding colspan and rowspan attributes.
        Returns grid of dicts: {'text': str, 'is_header': bool, 'tag': Tag}.
        """
        rows = self.table_tag.find_all("tr")
        if not rows:
            return []

        # Determine dimensions and track occupied coordinates by rowspans
        grid: List[List[Optional[Dict[str, Any]]]] = []

        for r_idx, tr in enumerate(rows):
            while len(grid) <= r_idx:
                grid.append([])

            c_idx = 0
            cell_tags = tr.find_all(["th", "td"])

            for cell_tag in cell_tags:
                # Advance c_idx past any slots occupied by previous rowspans
                while c_idx < len(grid[r_idx]) and grid[r_idx][c_idx] is not None:
                    c_idx += 1

                try:
                    rowspan = int(cell_tag.get("rowspan", 1))
                except (ValueError, TypeError):
                    rowspan = 1
                    self.parse_warnings.append(f"Invalid rowspan on table {self.table_id} row {r_idx}")

                try:
                    colspan = int(cell_tag.get("colspan", 1))
                except (ValueError, TypeError):
                    colspan = 1
                    self.parse_warnings.append(f"Invalid colspan on table {self.table_id} row {r_idx}")

                # Bound spans against malicious/degenerate HTML
                rowspan = min(max(1, rowspan), 50)
                colspan = min(max(1, colspan), 50)

                raw_text = cell_tag.get_text(" ", strip=True)
                is_header = cell_tag.name == "th" or "font-weight:bold" in cell_tag.get("style", "").lower()

                cell_data = {
                    "text": raw_text,
                    "is_header": is_header,
                    "tag": cell_tag,
                }

                # Fill the grid across rowspan and colspan
                for r_offset in range(rowspan):
                    target_r = r_idx + r_offset
                    while len(grid) <= target_r:
                        grid.append([])

                    for c_offset in range(colspan):
                        target_c = c_idx + c_offset
                        while len(grid[target_r]) <= target_c:
                            grid[target_r].append(None)
                        grid[target_r][target_c] = cell_data

                c_idx += colspan

        # Replace any residual None with empty cell dicts
        max_cols = max((len(r) for r in grid), default=0)
        clean_grid: List[List[Dict[str, Any]]] = []
        for r_idx, r in enumerate(grid):
            clean_row = []
            for c_idx in range(max_cols):
                if c_idx < len(r) and r[c_idx] is not None:
                    clean_row.append(r[c_idx])
                else:
                    clean_row.append({"text": "", "is_header": False, "tag": None})
            clean_grid.append(clean_row)

        return clean_grid

    def parse(self) -> Tuple[TableRecord, List[TableCell]]:
        """
        Parses the table into a TableRecord and list of TableCell models.
        """
        caption, unit_name = self._extract_caption_and_units()
        grid = self._build_raw_grid()

        if not grid:
            self.parse_warnings.append(f"Empty table structure for {self.table_id}")
            record = TableRecord(
                table_id=self.table_id,
                document_id=self.document_id,
                section_id=self.section_id,
                caption=caption,
                units_text=unit_name,
                source_locator=f"table_{self.table_id}",
                column_headers=[],
                row_count=0,
                column_count=0,
                parse_warnings=self.parse_warnings,
                footnotes=self.footnotes,
            )
            return record, []

        # Check for explicit <tfoot> tags
        tfoot = self.table_tag.find("tfoot")
        if tfoot:
            for tr in tfoot.find_all("tr"):
                txt = tr.get_text(" ", strip=True)
                if txt and txt not in self.footnotes:
                    self.footnotes.append(txt)

        # Partition header rows vs data rows
        # Standard financial tables have 1 to 4 header rows
        num_header_rows = 1
        for r_idx in range(min(5, len(grid))):
            row = grid[r_idx]
            non_empty = [c for c in row if c["text"].strip()]
            unique_texts = set(c["text"].strip() for c in non_empty)
            # If a row after row 0 has a single text spanning the table, it's a category divider, not column headers
            if r_idx > 0 and len(unique_texts) == 1:
                break
            # If all non-empty cells in the row are headers or contain dates/years
            if non_empty and all(c["is_header"] or re.search(r"\b(20\d\d|19\d\d|Q[1-4]|months?)\b", c["text"], re.IGNORECASE) for c in non_empty):
                num_header_rows = r_idx + 1

        num_cols = len(grid[0]) if grid else 0

        # Build effective multi-level column headers
        column_headers: List[str] = []
        for c_idx in range(num_cols):
            header_parts = []
            for h_idx in range(num_header_rows):
                val = grid[h_idx][c_idx]["text"].strip()
                if val and (not header_parts or val != header_parts[-1]):
                    header_parts.append(val)
            col_header = " > ".join(header_parts) if header_parts else f"Column {c_idx}"
            column_headers.append(col_header)

        # Parse data rows and cells
        cells: List[TableCell] = []
        current_category = ""
        footnote_pattern = re.compile(
            r"^\s*(\(\d+\)|\([a-zA-Z]\)|[*†‡§#]+|Note\s*\d*:|Notes:)",
            re.IGNORECASE,
        )

        for r_idx in range(num_header_rows, len(grid)):
            row = grid[r_idx]
            non_empty_cells = [c for c in row if c["text"].strip()]
            if not non_empty_cells:
                continue

            # Check if this row is a footnote row (e.g. at bottom or spanning note)
            cell_texts = [c["text"].strip() for c in non_empty_cells]
            comb_text = " ".join(dict.fromkeys(cell_texts))
            is_footnote_prefix = bool(footnote_pattern.match(comb_text))

            if is_footnote_prefix and (len(set(cell_texts)) <= 2 or r_idx >= len(grid) - 4):
                if comb_text and comb_text not in self.footnotes:
                    self.footnotes.append(comb_text)
                continue

            # Check if this row is a section divider / category header spanning the row
            unique_texts = set(c["text"].strip() for c in non_empty_cells)
            if len(unique_texts) == 1 and non_empty_cells[0]["is_header"]:
                current_category = non_empty_cells[0]["text"].strip()
                continue

            # First column is typically line-item row label
            raw_row_label = row[0]["text"].strip() if num_cols > 0 else f"Row {r_idx}"
            effective_row_label = f"{current_category} > {raw_row_label}" if current_category and raw_row_label else (raw_row_label or f"Row {r_idx}")

            # Parse numeric/data columns (starting from column 1 or 0)
            start_col = 1 if num_cols > 1 and raw_row_label else 0
            for c_idx in range(start_col, num_cols):
                raw_cell_text = row[c_idx]["text"].strip()
                col_header = column_headers[c_idx]

                num_val, is_dash, cell_unit = normalize_financial_number(raw_cell_text)
                if unit_name in ["USD_MILLIONS", "USD_THOUSANDS", "USD_BILLIONS", "PER_SHARE"]:
                    final_unit = unit_name
                else:
                    final_unit = cell_unit or unit_name

                # Infer fiscal period from column header if detectable
                period_match = re.search(r"\b(20\d\d|FY\s*20\d\d|Q[1-4]\s*20\d\d)\b", col_header, re.IGNORECASE)
                fiscal_period = period_match.group(0).replace(" ", "") if period_match else None

                cell = TableCell(
                    cell_id=f"{self.table_id}_r{r_idx}_c{c_idx}",
                    row_index=r_idx,
                    column_index=c_idx,
                    raw_text=raw_cell_text,
                    normalized_text=str(num_val) if num_val is not None else raw_cell_text,
                    numeric_value=num_val,
                    is_empty_or_dash=is_dash,
                    row_label=effective_row_label,
                    column_label=col_header,
                    unit=final_unit,
                    fiscal_period=fiscal_period,
                )
                cells.append(cell)

        record = TableRecord(
            table_id=self.table_id,
            document_id=self.document_id,
            section_id=self.section_id,
            caption=caption,
            units_text=unit_name,
            source_locator=f"table_{self.table_id}",
            column_headers=column_headers,
            row_count=len(grid) - num_header_rows,
            column_count=num_cols,
            parse_warnings=self.parse_warnings,
            footnotes=self.footnotes,
        )

        return record, cells
