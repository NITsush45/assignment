# Record Reconciliation System

Compares event records between two systems, finds disagreements, and shows them in a multi-tenant-safe UI.

## How to run

**Prerequisites**: Python 3.9+, no external packages required (uses Tornado which ships pre-installed).

```bash
# 1. Import the CSV data and run comparison
python3 backend/import_csv.py

# 2. Start the server
python3 backend/server.py

# 3. Open the UI
# Visit http://localhost:8000 in your browser
```

**Run tests**:
```bash
python3 -m pytest backend/tests/ -v
```

## What I built

### Backend (Python/Tornado/SQLite)
- **Database schema** with 4 tables: `location`, `system_a_record`, `system_b_entry`, `disagreement`
- **CSV importer** (`backend/import_csv.py`) that loads all three CSVs, normalizes dirty `record_ref` values, and never silently drops rows
- **Comparison engine** (`backend/services/comparator.py`) that detects 8 types of disagreement:
  - Missing in System B (REC-1015, REC-1061)
  - Orphan reference (REC-1999 points to nonexistent record)
  - Duplicate entry (REC-1042 exact dupe, REC-1055 split across two entries)
  - Value mismatch (REC-1003, REC-1027, REC-1088 — System B has base_value instead of total_value)
  - Date mismatch (REC-1009)
  - Location mismatch (REC-1077 — crosses org boundary)
  - Blank value (REC-1050)
  - Unparseable value (REC-1064 — "1,25,400.00")
- **REST API** with tenant-scoped endpoints:
  - `GET /api/disagreements/?org_id=ORG-A` — list with optional `reason` filter and `ordering`
  - `GET /api/summary/?org_id=ORG-A` — count by reason
  - `GET /api/orgs/` — list organizations
- **Multi-tenancy**: `org_id` is required on every query; no cross-tenant data leaks

### Frontend (Vanilla JS SPA)
- Organization selector (ORG-A / ORG-B)
- Summary cards showing totals per reason
- Disagreement table with sortable columns and reason filter
- Color-coded reason badges

### Tests (pytest)
- 28 tests covering normalizers, every disagreement type, and tenant isolation
- Each test creates isolated data in a temporary SQLite database

## What I deliberately did not build

- **Authentication/authorization**: per the brief, skipped entirely. Multi-tenancy is enforced via required `org_id` parameter, not user sessions.
- **React/Vite frontend**: no network access to install npm packages. Built a clean vanilla JS SPA instead — same functionality, zero build step, one HTML file.
- **Django**: also unavailable without network. Used Tornado (pre-installed) + raw SQLite. Same architectural separation (models/services/views), just without the ORM.
- **Pagination**: 120 rows don't need it.
- **Numeric sorting**: values are stored as strings (they represent amounts, dates, and locations depending on the disagreement type). Sorting is lexicographic. With 13 disagreements per org, this is fine.
- **CSS framework**: the brief said "plain and working beats pretty and broken."

## How I worked with the agent

### a. Name one thing the AI agent got wrong. How did you notice?

The agent initially planned the entire project around Django + React with Vite. When it tried to `pip install` and `npm create`, both failed — there was no network access. I noticed because the install commands returned `ENOTFOUND` errors. The agent then pivoted to Tornado (already installed) and vanilla JS, which was the right call but cost time on re-planning. This taught me to always verify the environment before committing to a tech stack.

### b. Which part of your submission are you least confident about, and why?

The handling of REC-1055 (the split entry). The two System B entries sum exactly to System A's total_value, which suggests it's intentional — not an error. The comparator flags it as a `duplicate_entry` with a note that the values sum correctly. But in a real system, you'd want a product decision: is a split entry a legitimate pattern (and should be reconciled by summing) or always a data quality issue? I flagged it as a disagreement because the brief says to catch "the same record entered twice," but I'm not fully confident this is the right interpretation.

### c. If you had a second day, what would you fix first?

I'd add an import audit log — a table that records every row processed, any warnings encountered, and the original raw values. Right now warnings are logged to stdout during import but aren't queryable. The `parse_warnings` field on `system_b_entry` captures per-row issues, but there's no UI to surface them. For a production system, operators need to see "what did the importer do with my data" without re-running the import.
