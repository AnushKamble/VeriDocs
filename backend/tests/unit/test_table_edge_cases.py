from decimal import Decimal
from bs4 import BeautifulSoup
from veridocs.ingestion.html_parser import FilingParser
from veridocs.ingestion.table_parser import TableParser


def test_malformed_table_warnings():
    # Table with invalid colspan and mismatched cells
    html = """
    <table>
        <tr>
            <th colspan="not_a_number">Header 1</th>
            <th rowspan="invalid">Header 2</th>
        </tr>
        <tr>
            <td>Only one cell</td>
        </tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = TableParser(soup.find("table"), "tbl_malformed", "doc_test")
    record, cells = parser.parse()

    # Must emit warnings rather than crashing
    assert len(record.parse_warnings) >= 2
    assert any("colspan" in w for w in record.parse_warnings)
    assert any("rowspan" in w for w in record.parse_warnings)


def test_repeated_headers_and_categories():
    html = """
    <table>
        <caption>Selected Financial Data (in thousands)</caption>
        <tr><th>Metric</th><th>FY2023</th><th>FY2022</th></tr>
        <tr><th colspan="3" style="font-weight:bold">Operating Expenses</th></tr>
        <tr><td>Selling and marketing</td><td>$5,120</td><td>$4,890</td></tr>
        <tr><td>General and admin</td><td>$2,300</td><td>$2,100</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = TableParser(soup.find("table"), "tbl_categories", "doc_test")
    record, cells = parser.parse()

    assert record.units_text == "USD_THOUSANDS"
    assert len(cells) == 4

    # Row label must preserve category hierarchy
    assert cells[0].row_label == "Operating Expenses > Selling and marketing"
    assert cells[0].numeric_value == Decimal("5120")
    assert cells[0].unit == "USD_THOUSANDS"


def test_complete_filing_parser():
    raw_html = b"""
    <html>
        <head><title>Apple Inc. Form 10-K</title></head>
        <body>
            <p>Item 7. Management's Discussion and Analysis</p>
            <p>During fiscal 2023, net sales decreased 2.8% to $383.3 billion compared to fiscal 2022.</p>
            
            <p>Item 8. Financial Statements</p>
            <table>
                <caption>Consolidated Statements of Income (in millions)</caption>
                <tr><th>Component</th><th>2023</th></tr>
                <tr><td>Total Revenue</td><td>383,285</td></tr>
                <tr><td>Operating Income</td><td>114,301</td></tr>
            </table>
        </body>
    </html>
    """
    metadata = {
        "cik": "0000320193",
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "form_type": "10-K",
        "accession_number": "0000320193-23-000106",
        "filing_date": "2023-11-03",
        "report_period": "2023-09-30",
        "fiscal_year": 2023,
    }
    parser = FilingParser(raw_html=raw_html, metadata=metadata)
    result = parser.parse()

    assert result.document.company_name == "Apple Inc."
    assert len(result.sections) >= 2
    assert len(result.tables) == 1
    assert result.tables[0].caption == "Consolidated Statements of Income (in millions)"
    assert len(result.cells) == 2
    assert result.cells[0].row_label == "Total Revenue"
    assert result.cells[0].numeric_value == Decimal("383285")
