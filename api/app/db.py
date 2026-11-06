import json
import sqlite3
from contextlib import contextmanager

from .config import DATA, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
  uei TEXT PRIMARY KEY, cage TEXT, legal_name TEXT, naics TEXT, poc_name TEXT, poc_email TEXT, address TEXT);
CREATE TABLE IF NOT EXISTS test_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT, company_uei TEXT NOT NULL, system_name TEXT NOT NULL,
  mission_area TEXT NOT NULL, test_functions TEXT NOT NULL, description TEXT, quantity INTEGER DEFAULT 1,
  desired_start TEXT, desired_end TEXT, classification TEXT DEFAULT 'UNCLASSIFIED',
  status TEXT NOT NULL DEFAULT 'submitted', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS recommendations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL, source TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft', payload TEXT NOT NULL, devin_session_id TEXT, devin_session_url TEXT,
  reviewer TEXT, review_note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS schedule_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, site_code TEXT NOT NULL, range_complex_id TEXT NOT NULL,
  title TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, weapon_class TEXT DEFAULT 'none',
  firing_point_id TEXT, target_area_id TEXT, equipment_ids TEXT DEFAULT '[]', personnel_ids TEXT DEFAULT '[]',
  request_id INTEGER, recommendation_id INTEGER, status TEXT DEFAULT 'scheduled');
"""

JSON_COLS = {"naics", "test_functions", "payload", "equipment_ids", "personnel_ids"}


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def tx():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def row(r):
    if r is None:
        return None
    d = dict(r)
    for k in JSON_COLS & d.keys():
        if isinstance(d[k], str):
            d[k] = json.loads(d[k])
    return d


def init_db(reset: bool = False):
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    with tx() as con:
        con.executescript(SCHEMA)
        if con.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0:
            for c in json.loads((DATA / "seed" / "companies.json").read_text()):
                con.execute("INSERT INTO companies VALUES (?,?,?,?,?,?,?)",
                            (c["uei"], c["cage"], c["legal_name"], json.dumps(c["naics"]),
                             c["poc_name"], c["poc_email"], c["address"]))
            for e in json.loads((DATA / "seed" / "schedule.json").read_text()):
                con.execute(
                    "INSERT INTO schedule_events (site_code,range_complex_id,title,start,end,weapon_class,"
                    "firing_point_id,target_area_id,equipment_ids,personnel_ids) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (e["site_code"], e["range_complex_id"], e["title"], e["start"], e["end"], e["weapon_class"],
                     e.get("firing_point_id"), e.get("target_area_id"), json.dumps(e["equipment_ids"]),
                     json.dumps(e["personnel_ids"])))
