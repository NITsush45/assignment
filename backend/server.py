#!/usr/bin/env python3
"""Tornado API server for reconciliation data."""

import json
import logging
import os
import sys

import tornado.ioloop
import tornado.web

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.db import get_connection, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

ALLOWED_ORDERINGS = {
    "record_id", "-record_id",
    "reason", "-reason",
    "system_a_value", "-system_a_value",
    "system_b_value", "-system_b_value",
    "location_id", "-location_id",
}


class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header("Content-Type", "application/json")

    def options(self):
        self.set_status(204)
        self.finish()


class DisagreementListHandler(BaseHandler):
    def get(self):
        org_id = self.get_argument("org_id", None)
        if not org_id:
            self.set_status(400)
            self.write(json.dumps({"error": "org_id parameter is required"}))
            return

        reason = self.get_argument("reason", None)
        ordering = self.get_argument("ordering", "record_id")

        if ordering not in ALLOWED_ORDERINGS:
            ordering = "record_id"

        conn = get_connection()
        try:
            query = "SELECT * FROM disagreement WHERE org_id = ?"
            params = [org_id]

            if reason:
                query += " AND reason = ?"
                params.append(reason)

            desc = ordering.startswith("-")
            col = ordering.lstrip("-")
            direction = "DESC" if desc else "ASC"
            query += f" ORDER BY {col} {direction}"

            rows = conn.execute(query, params).fetchall()
            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "record_id": row["record_id"],
                    "reason": row["reason"],
                    "reason_display": row["reason"].replace("_", " ").title(),
                    "system_a_value": row["system_a_value"],
                    "system_b_value": row["system_b_value"],
                    "location_id": row["location_id"],
                    "org_id": row["org_id"],
                    "detail": row["detail"],
                    "created_at": row["created_at"],
                })

            self.write(json.dumps({"count": len(results), "results": results}))
        finally:
            conn.close()


class SummaryHandler(BaseHandler):
    def get(self):
        org_id = self.get_argument("org_id", None)
        if not org_id:
            self.set_status(400)
            self.write(json.dumps({"error": "org_id parameter is required"}))
            return

        conn = get_connection()
        try:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM disagreement WHERE org_id = ?",
                (org_id,),
            ).fetchone()["cnt"]

            by_reason_rows = conn.execute(
                "SELECT reason, COUNT(*) as cnt FROM disagreement WHERE org_id = ? GROUP BY reason",
                (org_id,),
            ).fetchall()

            by_reason = {row["reason"]: row["cnt"] for row in by_reason_rows}

            self.write(json.dumps({
                "org_id": org_id,
                "total_disagreements": total,
                "by_reason": by_reason,
            }))
        finally:
            conn.close()


class OrgsHandler(BaseHandler):
    def get(self):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT DISTINCT org_id FROM location ORDER BY org_id"
            ).fetchall()
            self.write(json.dumps({
                "orgs": [row["org_id"] for row in rows],
            }))
        finally:
            conn.close()


def make_app():
    return tornado.web.Application(
        [
            (r"/api/disagreements/", DisagreementListHandler),
            (r"/api/summary/", SummaryHandler),
            (r"/api/orgs/", OrgsHandler),
            (r"/()", tornado.web.StaticFileHandler, {"path": STATIC_DIR, "default_filename": "index.html"}),
            (r"/(.*)", tornado.web.StaticFileHandler, {"path": STATIC_DIR}),
        ],
        debug=True,
    )


def main():
    port = int(os.environ.get("PORT", 8000))

    init_db()

    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) as cnt FROM disagreement").fetchone()["cnt"]
    conn.close()

    if count == 0:
        logger.warning("No disagreements in database. Run 'python3 backend/import_csv.py' first.")

    app = make_app()
    app.listen(port)
    logger.info("Server running on http://localhost:%d", port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
