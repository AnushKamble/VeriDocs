# ADR-003: Financial Table Reconstruction and Multi-Level Header Resolution

## Context
Financial statements in SEC filings (Consolidated Statements of Operations, Balance Sheets, Cash Flows, Notes) are characterized by:
1. Multi-level hierarchical column headers (e.g., Year Ended December 31, 2023 vs 2022, with sub-columns for Operating / Financing).
2. Spanned cells (`colspan` across multiple reporting periods, `rowspan` across categories).
3. Scale and unit specifications ("in millions, except share amounts", "in thousands", "$").
4. Accounting notation: negative numbers in parentheses `(1,234)` or `$(1,234)`.
5. Missing or not meaningful values denoted by em dashes `—`, hyphens `-`, `N/A`, or empty cells, which are mathematically distinct from `0.0`.

A naive HTML text flattener destroys these relationships, dissociating numbers from their column periods and line item names.

## Decision
We implement a dedicated structural table parser in `backend/veridocs/ingestion/table_parser.py`:

1. **Header Matrix Reconstruction**:
   - The parser constructs a 2D grid accounting for `colspan` and `rowspan`.
   - For each data column, an effective multi-level header path is formed by joining non-empty header levels with ` > ` (e.g. `Three Months Ended September 30 > 2023`).

2. **Row Label Hierarchy**:
   - Leading indentation, style attributes, and bold categories are preserved to maintain line-item context (e.g., `Total operating expenses > Research and development`).

3. **Cell Value Representation**:
   - `raw_text`: Exact verbatim string from HTML (e.g. `"$(1,245)"`).
   - `normalized_text`: Clean string with stripped padding (e.g. `"-1245"`).
   - `numeric_value`: Exact `decimal.Decimal` value (`Decimal("-1245")`) when parseable, else `None`.
   - `is_empty_or_dash`: Boolean flag distinguishing missing / dash / N/A from zero (`0`).
   - `unit`: Extracted table-level or column-level unit (e.g. `"USD_MILLIONS"`).

4. **Context-Preserving Table Chunks**:
   - Table chunks group adjacent rows (typically 3 to 10 rows per chunk) while **always repeating**:
     - Document metadata (Company, Form, Fiscal Period, Filing Date).
     - Section name & Table Caption.
     - Units declaration.
     - Complete effective column header line.
     - Row items with full cell values.

5. **Defensive Parsing & Diagnostic Warnings**:
   - When table structure is malformed (e.g., mismatched cell counts, irregular spans), the parser emits an explicit `ParseWarning` with error coordinates rather than fabricating cell alignments.
