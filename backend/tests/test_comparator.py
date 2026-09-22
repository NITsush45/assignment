import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.comparator import run_comparison
from backend.tests.conftest import insert_system_a, insert_system_b


class TestMissingInB:
    def test_record_in_a_with_no_b_entry(self, conn, seed_locations):
        insert_system_a(conn, "REC-1015", location_id="LOC-103", total_value="41095.33")
        conn.commit()

        results = run_comparison(conn)

        assert len(results) == 1
        assert results[0]["record_id"] == "REC-1015"
        assert results[0]["reason"] == "missing_in_b"
        assert results[0]["org_id"] == "ORG-A"


class TestOrphanReference:
    def test_b_entry_pointing_at_nonexistent_a_record(self, conn, seed_locations):
        insert_system_b(conn, "ENT/2026/4901", "REC-1999", location_id="LOC-102",
                        value="41250.00", value_raw="41250.00")
        conn.commit()

        results = run_comparison(conn)

        assert len(results) == 1
        assert results[0]["record_id"] == "REC-1999"
        assert results[0]["reason"] == "orphan_reference"
        assert results[0]["org_id"] == "ORG-A"


class TestDuplicateEntry:
    def test_exact_duplicate(self, conn, seed_locations):
        insert_system_a(conn, "REC-1042", location_id="LOC-101", total_value="112837.06")
        insert_system_b(conn, "ENT/2026/4042", "REC-1042", location_id="LOC-101",
                        value="112837.06", value_raw="112837.06")
        insert_system_b(conn, "ENT/2026/4902", "REC-1042", location_id="LOC-101",
                        value="112837.06", value_raw="112837.06")
        conn.commit()

        results = run_comparison(conn)

        dup = [r for r in results if r["reason"] == "duplicate_entry"]
        assert len(dup) == 1
        assert dup[0]["record_id"] == "REC-1042"
        assert "Exact duplicate" in dup[0]["detail"]

    def test_split_entry(self, conn, seed_locations):
        insert_system_a(conn, "REC-1055", location_id="LOC-103", total_value="179877.32")
        insert_system_b(conn, "ENT/2026/4055", "REC-1055", location_id="LOC-103",
                        value="71950.93", value_raw="71950.93", label="Entry for CAT-08")
        insert_system_b(conn, "ENT/2026/4903", "REC-1055", location_id="LOC-103",
                        value="107926.39", value_raw="107926.39", label="Entry part 2 of 2")
        conn.commit()

        results = run_comparison(conn)

        dup = [r for r in results if r["reason"] == "duplicate_entry"]
        assert len(dup) == 1
        assert dup[0]["record_id"] == "REC-1055"
        assert "sum" in dup[0]["detail"].lower() or "Split" in dup[0]["detail"]


class TestValueMismatch:
    def test_different_values(self, conn, seed_locations):
        insert_system_a(conn, "REC-1003", location_id="LOC-202", total_value="121388.01")
        insert_system_b(conn, "ENT/2026/4003", "REC-1003", location_id="LOC-202",
                        value="94834.38", value_raw="94834.38")
        conn.commit()

        results = run_comparison(conn)

        vm = [r for r in results if r["reason"] == "value_mismatch"]
        assert len(vm) == 1
        assert vm[0]["record_id"] == "REC-1003"
        assert vm[0]["system_a_value"] == "121388.01"
        assert vm[0]["system_b_value"] == "94834.38"
        assert vm[0]["org_id"] == "ORG-B"


class TestDateMismatch:
    def test_different_dates(self, conn, seed_locations):
        insert_system_a(conn, "REC-1009", location_id="LOC-201",
                        event_date="2026-03-31", total_value="111699.30")
        insert_system_b(conn, "ENT/2026/4009", "REC-1009", location_id="LOC-201",
                        recorded_on="2026-04-02", value="111699.30", value_raw="111699.30")
        conn.commit()

        results = run_comparison(conn)

        dm = [r for r in results if r["reason"] == "date_mismatch"]
        assert len(dm) == 1
        assert dm[0]["record_id"] == "REC-1009"
        assert dm[0]["system_a_value"] == "2026-03-31"
        assert dm[0]["system_b_value"] == "2026-04-02"


class TestLocationMismatch:
    def test_different_locations_cross_org(self, conn, seed_locations):
        insert_system_a(conn, "REC-1077", location_id="LOC-102",
                        total_value="83361.40")
        insert_system_b(conn, "ENT/2026/4077", "REC-1077", location_id="LOC-201",
                        value="83361.40", value_raw="83361.40")
        conn.commit()

        results = run_comparison(conn)

        lm = [r for r in results if r["reason"] == "location_mismatch"]
        assert len(lm) == 2
        orgs = {r["org_id"] for r in lm}
        assert orgs == {"ORG-A", "ORG-B"}


class TestBlankValue:
    def test_blank_value_in_b(self, conn, seed_locations):
        insert_system_a(conn, "REC-1050", location_id="LOC-202", total_value="160405.85")
        insert_system_b(conn, "ENT/2026/4050", "REC-1050", location_id="LOC-202",
                        value=None, value_raw="")
        conn.commit()

        results = run_comparison(conn)

        bv = [r for r in results if r["reason"] == "blank_value"]
        assert len(bv) == 1
        assert bv[0]["record_id"] == "REC-1050"


class TestUnparseableValue:
    def test_unparseable_value_in_b(self, conn, seed_locations):
        insert_system_a(conn, "REC-1064", location_id="LOC-101", total_value="183244.16")
        insert_system_b(conn, "ENT/2026/4064", "REC-1064", location_id="LOC-101",
                        value=None, value_raw="1,25,400.00")
        conn.commit()

        results = run_comparison(conn)

        uv = [r for r in results if r["reason"] == "unparseable_value"]
        assert len(uv) == 1
        assert uv[0]["record_id"] == "REC-1064"
        assert uv[0]["system_b_value"] == "1,25,400.00"


class TestNoDisagreement:
    def test_matching_records_produce_no_disagreement(self, conn, seed_locations):
        insert_system_a(conn, "REC-1001", location_id="LOC-201",
                        event_date="2026-04-03", total_value="88969.92")
        insert_system_b(conn, "ENT/2026/4001", "REC-1001", location_id="LOC-201",
                        recorded_on="2026-04-03", value="88969.92", value_raw="88969.92")
        conn.commit()

        results = run_comparison(conn)

        assert len(results) == 0


class TestTenantIsolation:
    def test_disagreements_scoped_to_correct_org(self, conn, seed_locations):
        insert_system_a(conn, "REC-2001", location_id="LOC-101", total_value="100.00")
        insert_system_a(conn, "REC-2002", location_id="LOC-201", total_value="200.00")
        conn.commit()

        results = run_comparison(conn)

        org_a = [r for r in results if r["org_id"] == "ORG-A"]
        org_b = [r for r in results if r["org_id"] == "ORG-B"]

        assert all(r["record_id"] == "REC-2001" for r in org_a)
        assert all(r["record_id"] == "REC-2002" for r in org_b)

        a_record_ids = {r["record_id"] for r in org_a}
        b_record_ids = {r["record_id"] for r in org_b}
        assert a_record_ids.isdisjoint(b_record_ids)
