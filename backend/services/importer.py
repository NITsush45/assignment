import csv
import logging
import os
from .normalizers import normalize_record_ref, parse_value

logger = logging.getLogger(__name__)


def import_locations(conn, data_dir):
    path = os.path.join(data_dir, "locations.csv")
    cursor = conn.cursor()
    count = 0

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                "INSERT INTO location (location_id, org_id, location_name) VALUES (?, ?, ?)",
                (row["location_id"].strip(), row["org_id"].strip(), row["location_name"].strip()),
            )
            count += 1

    logger.info("Imported %d locations", count)
    return count


def import_system_a(conn, data_dir):
    path = os.path.join(data_dir, "system_a.csv")
    cursor = conn.cursor()
    count = 0
    warnings = []

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_id = row["record_id"].strip()
            actor_id = row["actor_id"].strip()
            state = row["state"].strip()

            if not actor_id:
                warnings.append(f"{record_id}: blank actor_id")

            if state == "VOIDED":
                warnings.append(f"{record_id}: state is VOIDED")

            cursor.execute(
                """INSERT INTO system_a_record
                   (record_id, location_id, event_date, category_code,
                    actor_id, base_value, adjustment, total_value, state)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record_id,
                    row["location_id"].strip(),
                    row["event_date"].strip(),
                    row["category_code"].strip(),
                    actor_id,
                    row["base_value"].strip(),
                    row["adjustment"].strip(),
                    row["total_value"].strip(),
                    state,
                ),
            )
            count += 1

    for w in warnings:
        logger.warning("system_a: %s", w)

    logger.info("Imported %d system_a records (%d warnings)", count, len(warnings))
    return count, warnings


def import_system_b(conn, data_dir):
    path = os.path.join(data_dir, "system_b.csv")
    cursor = conn.cursor()
    count = 0
    warnings = []

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry_id = row["entry_id"].strip()
            record_ref_raw = row["record_ref"]
            row_warnings = []

            try:
                record_ref_normalized = normalize_record_ref(record_ref_raw)
            except ValueError as e:
                record_ref_normalized = ""
                row_warnings.append(str(e))

            location_id = row["location_id"].strip() if row["location_id"].strip() else None

            recorded_on = row["recorded_on"].strip() if row["recorded_on"].strip() else None

            value_raw = row["value"].strip() if row["value"] else ""
            parsed_value, value_warning = parse_value(value_raw)
            if value_warning:
                row_warnings.append(value_warning)

            value_str = str(parsed_value) if parsed_value is not None else None
            label = row.get("label", "").strip()
            parse_warnings_str = "; ".join(row_warnings)

            cursor.execute(
                """INSERT INTO system_b_entry
                   (entry_id, record_ref_raw, record_ref_normalized, location_id,
                    recorded_on, value, value_raw, label, parse_warnings)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    record_ref_raw,
                    record_ref_normalized,
                    location_id,
                    recorded_on,
                    value_str,
                    value_raw,
                    label,
                    parse_warnings_str,
                ),
            )
            count += 1
            if row_warnings:
                warnings.extend([f"{entry_id}: {w}" for w in row_warnings])

    for w in warnings:
        logger.warning("system_b: %s", w)

    logger.info("Imported %d system_b entries (%d warnings)", count, len(warnings))
    return count, warnings


def run_import(data_dir, db_path=None):
    from .. import db as db_module

    if db_path:
        original_path = db_module.DB_PATH
        db_module.DB_PATH = db_path

    try:
        db_module.init_db()
        db_module.reset_db()
        conn = db_module.get_connection()

        try:
            loc_count = import_locations(conn, data_dir)
            a_count, a_warnings = import_system_a(conn, data_dir)
            b_count, b_warnings = import_system_b(conn, data_dir)
            conn.commit()

            return {
                "locations": loc_count,
                "system_a": a_count,
                "system_b": b_count,
                "warnings": a_warnings + b_warnings,
            }
        finally:
            conn.close()
    finally:
        if db_path:
            db_module.DB_PATH = original_path
