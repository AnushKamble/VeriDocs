from bs4 import BeautifulSoup
from veridocs.ingestion.section_parser import SectionParser, classify_section_heading


def test_classify_section_heading():
    assert classify_section_heading("Item 1. Business") == {"section_id": "Item 1", "section_title": "Business"}
    assert classify_section_heading("ITEM 1A. RISK FACTORS") == {"section_id": "Item 1A", "section_title": "RISK FACTORS"}
    assert classify_section_heading("Item 7. Management's Discussion and Analysis")["section_id"] == "Item 7"
    assert classify_section_heading("Part I. Item 1. Financial Statements")["section_id"] == "Part I Item 1"

    # Non-heading paragraph
    assert classify_section_heading("In fiscal 2023, our revenue grew significantly across all regions.") is None


def test_section_parser_reading_order():
    html = """
    <html>
        <body>
            <p>Item 1. Business</p>
            <p>Apple designs, manufactures and markets smartphones, personal computers, tablets, wearables and accessories.</p>
            <p>The company sells a range of related services including Apple Music, iCloud, and Apple Pay.</p>
            
            <p>Item 1A. Risk Factors</p>
            <p>Global economic conditions and macroeconomic volatility could adversely affect our business.</p>
            <p>The semiconductor supply chain presents operational and inventory risks.</p>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = SectionParser(soup, document_id="doc_aapl")
    sections = parser.extract_sections()

    assert len(sections) == 2
    assert sections[0].section_id == "Item 1"
    assert "Apple designs, manufactures" in sections[0].text_content
    assert sections[1].section_id == "Item 1A"
    assert "Risk Factors" in sections[1].section_title
    assert "semiconductor supply chain" in sections[1].text_content
