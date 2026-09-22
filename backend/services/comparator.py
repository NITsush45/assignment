import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def _get_org_for_location(cursor, location_id):
    if not location_id:
        return "UNKNOWN"
    row = cursor.execute(
        "SELECT org_id FROM location WHERE location_id = ?", (location_id,)
    ).fetchone()
    return row["org_id"] if row else "UNKNOWN"


def _check_missing_in_b(cursor):
    """System A records with no matching System B entry."""
    rows = cursor.execute("""
        SELECT a.record_id, a.total_value, a.location_id
        FROM system_a_record a
        LEFT JOIN system_b_entry b ON a.record_id = b.record_ref_normalized
        WHERE b.entry_id IS NULL
    """).fetchall()

    results = []
    for row in rows:
        org_id = _get_org_for_location(cursor, row["location_id"])
        results.append({
            "record_id": row["record_id"],
            "reason": "missing_in_b",
            "system_a_value": row["total_value"] or "",
            "system_b_value": "",
            "location_id": row["location_id"] or "",
            "org_id": org_id,
            "detail": "Record exists in System A but has no entry in System B",
        })
    return results


def _check_orphan_references(cursor):
    """System B entries pointing at nonexistent System A records."""
    rows = cursor.execute("""
        SELECT b.entry_id, b.record_ref_normalized, b.record_ref_raw,
               b.value, b.location_id
        FROM system_b_entry b
        LEFT JOIN system_a_record a ON b.record_ref_normalized = a.record_id
        WHERE a.record_id IS NULL
          AND b.record_ref_normalized != ''
    """).fetchall()

    results = []
    for row in rows:
        org_id = _get_org_for_location(cursor, row["location_id"])
        results.append({
            "record_id": row["record_ref_normalized"],
            "reason": "orphan_reference",
            "system_a_value": "",
            "system_b_value": row["value"] or "",
            "location_id": row["location_id"] or "",
            "org_id": org_id,
            "detail": f"System B entry {row['entry_id']} references {row['record_ref_raw']!r} which does not exist in System A",
        })
    return results


def _check_duplicates(cursor):
    """Records referenced more than once in System B."""
    dup_refs = cursor.execute("""
        SELECT record_ref_normalized, COUNT(*) as cnt
        FROM system_b_entry
        WHERE record_ref_normalized != ''
        GROUP BY record_ref_normalized
        HAVING cnt > 1
    """).fetchall()

    results = []
    for dup in dup_refs:
        ref = dup["record_ref_normalized"]
        entries = cursor.execute(
            "SELECT entry_id, value, label FROM system_b_entry WHERE record_ref_normalized = ?",
            (ref,),
        ).fetchall()

        a_row = cursor.execute(
            "SELECT total_value, location_id FROM system_a_record WHERE record_id = ?",
            (ref,),
        ).fetchone()

        location_id = a_row["location_id"] if a_row else ""
        org_id = _get_org_for_location(cursor, location_id)

        values = [e["value"] for e in entries]
        entry_ids = [e["entry_id"] for e in entries]

        all_same = len(set(v for v in values if v is not None)) <= 1
        if all_same:
            detail = f"Exact duplicate: {len(entries)} entries ({', '.join(entry_ids)}) with identical values"
        else:
            value_strs = [v or "NULL" for v in values]
            total_note = ""
            if a_row and a_row["total_value"]:
                try:
                    entry_sum = sum(Decimal(v) for v in values if v)
                    a_total = Decimal(a_row["total_value"])
                    if entry_sum == a_total:
                        total_note = f" (sum {entry_sum} matches System A total)"
                except Exception:
                    pass
            detail = f"Split/conflicting entries: {', '.join(entry_ids)} with values {', '.join(value_strs)}{total_note}"

        b_value_display = ", ".join(v or "NULL" for v in values)

        results.append({
            "record_id": ref,
            "reason": "duplicate_entry",
            "system_a_value": a_row["total_value"] if a_row else "",
            "system_b_value": b_value_display,
            "location_id": location_id,
            "org_id": org_id,
            "detail": detail,
        })
    return results


def _check_matched_pairs(cursor):
    """
    For 1:1 matched pairs, check value, date, and location mismatches.
    Also checks for blank/unparseable values.
    """
    rows = cursor.execute("""
        SELECT a.record_id, a.total_value, a.event_date, a.location_id AS a_location,
               b.entry_id, b.value, b.value_raw, b.recorded_on, b.location_id AS b_location
        FROM system_a_record a
        INNER JOIN system_b_entry b ON a.record_id = b.record_ref_normalized
        WHERE b.record_ref_normalized IN (
            SELECT record_ref_normalized FROM system_b_entry
            WHERE record_ref_normalized != ''
            GROUP BY record_ref_normalized
            HAVING COUNT(*) = 1
        )
    """).fetchall()

    results = []
    for row in rows:
        a_loc = row["a_location"]
        org_id = _get_org_for_location(cursor, a_loc)

        if row["value"] is None and (row["value_raw"] is None or row["value_raw"] == ""):
            results.append({
                "record_id": row["record_id"],
                "reason": "blank_value",
                "system_a_value": row["total_value"] or "",
                "system_b_value": "",
                "location_id": a_loc or "",
                "org_id": org_id,
                "detail": "System B entry has a blank/empty value field",
            })
        elif row["value"] is None and row["value_raw"]:
            results.append({
                "record_id": row["record_id"],
                "reason": "unparseable_value",
                "system_a_value": row["total_value"] or "",
                "system_b_value": row["value_raw"],
                "location_id": a_loc or "",
                "org_id": org_id,
                "detail": f"System B value {row['value_raw']!r} could not be parsed as a number",
            })
        elif row["value"] is not None:
            try:
                a_val = Decimal(row["total_value"])
                b_val = Decimal(row["value"])
                if a_val != b_val:
                    results.append({
                        "record_id": row["record_id"],
                        "reason": "value_mismatch",
                        "system_a_value": row["total_value"],
                        "system_b_value": row["value"],
                        "location_id": a_loc or "",
                        "org_id": org_id,
                        "detail": f"System A total_value={row['total_value']}, System B value={row['value']}",
                    })
            except Exception:
                pass

        if row["recorded_on"] and row["event_date"] and row["recorded_on"] != row["event_date"]:
            results.append({
                "record_id": row["record_id"],
                "reason": "date_mismatch",
                "system_a_value": row["event_date"],
                "system_b_value": row["recorded_on"],
                "location_id": a_loc or "",
                "org_id": org_id,
                "detail": f"System A event_date={row['event_date']}, System B recorded_on={row['recorded_on']}",
            })

        b_loc = row["b_location"]
        if a_loc and b_loc and a_loc != b_loc:
            a_org = _get_org_for_location(cursor, a_loc)
            b_org = _get_org_for_location(cursor, b_loc)

            results.append({
                "record_id": row["record_id"],
                "reason": "location_mismatch",
                "system_a_value": a_loc,
                "system_b_value": b_loc,
                "location_id": a_loc,
                "org_id": a_org,
                "detail": f"System A location={a_loc} ({a_org}), System B location={b_loc} ({b_org})",
            })

            if a_org != b_org:
                results.append({
                    "record_id": row["record_id"],
                    "reason": "location_mismatch",
                    "system_a_value": a_loc,
                    "system_b_value": b_loc,
                    "location_id": b_loc,
                    "org_id": b_org,
                    "detail": f"System A location={a_loc} ({a_org}), System B location={b_loc} ({b_org})",
                })

    return results


def run_comparison(conn):
    """Run all checks and populate the disagreement table. Returns list of disagreements."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM disagreement")

    all_disagreements = []
    all_disagreements.extend(_check_missing_in_b(cursor))
    all_disagreements.extend(_check_orphan_references(cursor))
    all_disagreements.extend(_check_duplicates(cursor))
    all_disagreements.extend(_check_matched_pairs(cursor))

    for d in all_disagreements:
        cursor.execute(
            """INSERT INTO disagreement
               (record_id, reason, system_a_value, system_b_value,
                location_id, org_id, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                d["record_id"], d["reason"], d["system_a_value"],
                d["system_b_value"], d["location_id"], d["org_id"],
                d["detail"],
            ),
        )

    conn.commit()
    logger.info("Found %d disagreements", len(all_disagreements))
    return all_disagreements
