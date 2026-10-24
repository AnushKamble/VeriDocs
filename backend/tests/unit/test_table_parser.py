from decimal import Decimal
from bs4 import BeautifulSoup
from veridocs.ingestion.table_parser import TableParser


def test_table_parser_multi_row_headers():
    html = """
    <table>
        <caption>Consolidated Statements of Operations (in millions)</caption>
        <tr>
            <th rowspan="2">Line Item</th>
            <th colspan="2">Three Months Ended September 30</th>
        </tr>
        <tr>
            <th>2023</th>
            <th>2022</th>
        </tr>
        <tr>
            <td>Total net sales</td>
            <td>$89,498</td>
            <td>$90,146</td>
        </tr>
        <tr>
            <td>Research and development</td>
            <td>(7,307)</td>
            <td>(6,761)</td>
        </tr>
        <tr>
            <td>Discontinued ops</td>
            <td>—</td>
            <td>—</td>
        </tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    table_tag = soup.find("table")

    parser = TableParser(table_tag, table_id="tbl_test_01", document_id="doc_123", section_id="Item 8")
    record, cells = parser.parse()

    assert record.table_id == "tbl_test_01"
    assert record.caption == "Consolidated Statements of Operations (in millions)"
    assert record.units_text == "USD_MILLIONS"
    assert record.column_count == 3
    assert len(record.column_headers) == 3

    # Check effective multi-level column headers
    assert record.column_headers[0] == "Line Item"
    assert "Three Months Ended September 30 > 2023" in record.column_headers[1]
    assert "Three Months Ended September 30 > 2022" in record.column_headers[2]

    # Verify cells
    assert len(cells) == 6  # 3 rows x 2 data columns

    # Cell 0: Net sales 2023 -> 89498
    c0 = cells[0]
    assert c0.row_label == "Total net sales"
    assert c0.numeric_value == Decimal("89498")
    assert not c0.is_empty_or_dash

    # Cell 2: R&D 2023 -> -7307 (parentheses negative!)
    c2 = cells[2]
    assert c2.row_label == "Research and development"
    assert c2.numeric_value == Decimal("-7307")
    assert not c2.is_empty_or_dash

    # Cell 4: Discontinued ops -> em dash
    c4 = cells[4]
    assert c4.row_label == "Discontinued ops"
    assert c4.numeric_value is None
    assert c4.is_empty_or_dash is True
