"""
SEC 10-K and 10-Q Section/Item parser and reading-order narrative extractor.
"""

import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel


class SectionBlock(BaseModel):
    section_id: str
    section_title: str
    text_content: str
    ordinal: int
    source_locator: str


# Regex patterns matching standard 10-K / 10-Q Item headings
ITEM_HEADING_PATTERNS = [
    re.compile(r"^(?:ITEM|Item)\s+(1A?|1B|2|3|4|5|6|7A?|8|9A?|9B|10|11|12|13|14|15)\s*[\.\:—–-]?\s*(.*)$", re.IGNORECASE),
    re.compile(r"^(?:PART|Part)\s+(I|II|III|IV)\s*[\.\:—–-]?\s*(?:ITEM|Item)\s+(1A?|2|3|4|5|6)\s*[\.\:—–-]?\s*(.*)$", re.IGNORECASE),
]


def classify_section_heading(text: str) -> Optional[Dict[str, str]]:
    """
    Classifies a line of text as an SEC Item section heading if it matches.
    Returns dict with 'section_id' and 'section_title', or None.
    """
    clean = text.strip()
    if len(clean) > 200 or len(clean) < 4:
        return None

    for pattern in ITEM_HEADING_PATTERNS:
        match = pattern.match(clean)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                item_num, title = groups
                sec_id = f"Item {item_num.upper()}"
            else:
                part_num, item_num, title = groups
                sec_id = f"Part {part_num.upper()} Item {item_num.upper()}"
            sec_title = title.strip() or sec_id
            return {"section_id": sec_id, "section_title": sec_title}
    return None


class SectionParser:
    """
    Parses document tree into sections while preserving paragraphs and lists in reading order.
    """

    def __init__(self, soup: BeautifulSoup, document_id: str):
        self.soup = soup
        self.document_id = document_id

    def extract_sections(self) -> List[SectionBlock]:
        """
        Walks the DOM in reading order, identifies section item headers,
        and aggregates narrative paragraphs into SectionBlock records.
        """
        sections: List[SectionBlock] = []
        current_section_id = "General"
        current_section_title = "Document Overview"
        current_paragraphs: List[str] = []
        ordinal = 0

        # Find narrative containers
        elements = self.soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "li"])

        for elem in elements:
            # Skip elements that are nested inside tables (tables handled by table parser)
            if elem.find_parent("table"):
                continue

            text = elem.get_text(" ", strip=True)
            if not text:
                continue

            heading_info = classify_section_heading(text)
            if heading_info:
                # Flush previous section if it had content or was a recognized heading
                if current_paragraphs or current_section_id != "General":
                    ordinal += 1
                    sections.append(SectionBlock(
                        section_id=current_section_id,
                        section_title=current_section_title,
                        text_content="\n\n".join(current_paragraphs),
                        ordinal=ordinal,
                        source_locator=f"{current_section_id}_ord_{ordinal}",
                    ))
                    current_paragraphs = []

                current_section_id = heading_info["section_id"]
                current_section_title = heading_info["section_title"]
            else:
                # Only add meaningful paragraphs (skip tiny artifact lines like single page numbers)
                if len(text) > 20:
                    current_paragraphs.append(text)

        # Flush final section
        if current_paragraphs or (current_section_id != "General" and not any(s.section_id == current_section_id for s in sections)):
            ordinal += 1
            sections.append(SectionBlock(
                section_id=current_section_id,
                section_title=current_section_title,
                text_content="\n\n".join(current_paragraphs),
                ordinal=ordinal,
                source_locator=f"{current_section_id}_ord_{ordinal}",
            ))

        return sections
