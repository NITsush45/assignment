import pytest
from decimal import Decimal

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.normalizers import normalize_record_ref, parse_value


class TestNormalizeRecordRef:
    def test_already_canonical(self):
        assert normalize_record_ref("REC-1034") == "REC-1034"

    def test_lowercase_no_dash(self):
        assert normalize_record_ref("rec1034") == "REC-1034"

    def test_spaces_everywhere(self):
        assert normalize_record_ref(" REC - 1070 ") == "REC-1070"

    def test_bare_number(self):
        assert normalize_record_ref("1112") == "REC-1112"

    def test_uppercase_no_dash(self):
        assert normalize_record_ref("REC1099") == "REC-1099"

    def test_leading_trailing_whitespace(self):
        assert normalize_record_ref("  REC-1001  ") == "REC-1001"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            normalize_record_ref("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            normalize_record_ref("   ")

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            normalize_record_ref("INVALID")

    def test_mixed_case_with_spaces(self):
        assert normalize_record_ref(" Rec - 2000 ") == "REC-2000"


class TestParseValue:
    def test_normal_decimal(self):
        val, warning = parse_value("94834.38")
        assert val == Decimal("94834.38")
        assert warning == ""

    def test_integer(self):
        val, warning = parse_value("100")
        assert val == Decimal("100")
        assert warning == ""

    def test_blank_string(self):
        val, warning = parse_value("")
        assert val is None
        assert warning == "blank_value"

    def test_whitespace_only(self):
        val, warning = parse_value("   ")
        assert val is None
        assert warning == "blank_value"

    def test_indian_comma_format(self):
        val, warning = parse_value("1,25,400.00")
        assert val is None
        assert "unparseable_value" in warning

    def test_plain_text(self):
        val, warning = parse_value("not-a-number")
        assert val is None
        assert "unparseable_value" in warning

    def test_negative_number(self):
        val, warning = parse_value("-500.00")
        assert val == Decimal("-500.00")
        assert warning == ""
