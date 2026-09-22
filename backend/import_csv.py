#!/usr/bin/env python3
"""Import CSV data and run comparison."""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.db import init_db, reset_db, get_connection
from backend.services.importer import import_locations, import_system_a, import_system_b
from backend.services.comparator import run_comparison

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]

    if not os.path.isdir(data_dir):
        print(f"Error: data directory not found: {data_dir}")
        sys.exit(1)

    for name in ("locations.csv", "system_a.csv", "system_b.csv"):
        if not os.path.exists(os.path.join(data_dir, name)):
            print(f"Error: missing {name} in {data_dir}")
            sys.exit(1)

    logger.info("Initializing database...")
    init_db()
    reset_db()

    conn = get_connection()
    try:
        logger.info("Importing locations...")
        loc_count = import_locations(conn, data_dir)

        logger.info("Importing System A records...")
        a_count, a_warnings = import_system_a(conn, data_dir)

        logger.info("Importing System B entries...")
        b_count, b_warnings = import_system_b(conn, data_dir)

        conn.commit()

        logger.info("Running comparison...")
        disagreements = run_comparison(conn)

        print(f"\n{'='*50}")
        print(f"Import complete:")
        print(f"  Locations:      {loc_count}")
        print(f"  System A rows:  {a_count}")
        print(f"  System B rows:  {b_count}")
        print(f"  Warnings:       {len(a_warnings) + len(b_warnings)}")
        print(f"  Disagreements:  {len(disagreements)}")
        print(f"{'='*50}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
