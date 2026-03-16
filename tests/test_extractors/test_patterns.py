"""Tests for pattern-based extraction modules (dates, authors, identifiers, doctypes)."""

from docforge.extractors.patterns.authors import extract_author, extract_author_last_name
from docforge.extractors.patterns.dates import extract_date, extract_year
from docforge.extractors.patterns.doctypes import (
    classify_document_type,
    classify_maritime_document,
    detect_organisation,
)
from docforge.extractors.patterns.identifiers import extract_report_id


class TestDateExtraction:
    """Test date pattern matching and parsing."""

    def test_iso_date(self):
        field = extract_date("Report dated 2023-07-15 by ABS.", {})
        assert not field.is_empty()
        assert "2023" in field.value

    def test_us_date(self):
        field = extract_date("Published 07/15/2023", {})
        assert not field.is_empty()

    def test_written_date(self):
        field = extract_date("15 July 2023", {})
        assert not field.is_empty()

    def test_year_only(self):
        field = extract_date("Copyright 2023", {})
        assert not field.is_empty()

    def test_metadata_date(self):
        field = extract_date("", {"creationDate": "D:20230715"})
        assert not field.is_empty()

    def test_no_date(self):
        field = extract_date("No temporal information here.", {})
        assert field.is_empty() or field.confidence < 0.3

    def test_extract_year(self):
        assert extract_year("2023-07-15") == "2023"
        assert extract_year("2023") == "2023"
        assert extract_year("") is None


class TestAuthorExtraction:
    """Test author pattern matching."""

    def test_explicit_author_label(self):
        field = extract_author("Author: John Smith\nDate: 2023", {})
        assert not field.is_empty()
        assert "Smith" in field.value or "John" in field.value

    def test_metadata_author(self):
        field = extract_author("", {"author": "Jane Doe"})
        assert not field.is_empty()
        assert "Jane" in field.value

    def test_last_name_extraction(self):
        assert extract_author_last_name("Smith, John") == "Smith"
        assert extract_author_last_name("John Smith") == "Smith"
        assert extract_author_last_name("") == ""


class TestOrganisationDetection:
    """Test known organisation matching."""

    def test_detect_dnv(self):
        field = detect_organisation("DNV GL Rules for Ships", {})
        assert not field.is_empty()
        assert field.value == "DNV"

    def test_detect_lloyds(self):
        field = detect_organisation("Lloyd's Register Survey Report", {})
        assert not field.is_empty()
        assert field.value == "LR"

    def test_detect_abs(self):
        field = detect_organisation("American Bureau of Shipping", {})
        assert not field.is_empty()
        assert field.value == "ABS"

    def test_detect_imo(self):
        field = detect_organisation("International Maritime Organization circular", {})
        assert not field.is_empty()
        assert field.value == "IMO"

    def test_unknown_org(self):
        field = detect_organisation("Random text with no org names", {})
        assert field.is_empty() or field.confidence < 0.5


class TestReportIdExtraction:
    """Test report ID / document number extraction."""

    def test_dnv_rp(self):
        field = extract_report_id("Reference: DNV-RP-C203", {})
        assert not field.is_empty()
        assert "DNV" in field.value

    def test_doi(self):
        field = extract_report_id("DOI: 10.1234/example.2023", {})
        assert not field.is_empty()

    def test_isbn(self):
        field = extract_report_id("ISBN 978-0-123456-78-9", {})
        assert not field.is_empty()

    def test_no_id(self):
        field = extract_report_id("No document identifiers here.", {})
        assert field.is_empty()


class TestDocumentTypeClassification:
    """Test document type classification."""

    def test_classify_invoice(self):
        field = classify_document_type("INVOICE\nAmount Due: $5,000\nPayment Terms: Net 30")
        assert not field.is_empty()
        assert "invoice" in field.value.lower()

    def test_classify_research_paper(self):
        field = classify_document_type(
            "Abstract\nThis paper presents a novel method for structural analysis. "
            "Keywords: FEA, stress, methodology. References [1] Smith et al."
        )
        assert not field.is_empty()

    def test_maritime_classification(self):
        text = (
            "Rules for Classification of Ships\n"
            "DNV GL\n"
            "Hull structural design requirements\n"
            "Survey and inspection procedures"
        )
        doc_type, domain, subdomain = classify_maritime_document(text, {})
        assert not doc_type.is_empty()
