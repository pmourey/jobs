#!/usr/bin/env python3
"""Apply simple migration to prod SQLite DB: add ft_offer_id column to job table if missing."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'instance' / 'jobs_prod.sqlite3'
if not DB.exists():
    print('ERROR: DB not found at', DB)
    raise SystemExit(1)

con = sqlite3.connect(str(DB))
cur = con.cursor()
try:
    cur.execute("PRAGMA table_info(job)")
    cols = [r[1] for r in cur.fetchall()]
    print('Existing columns:', cols)
    if 'ft_offer_id' in cols:
        print('Column ft_offer_id already present — nothing to do.')
    else:
        print('Adding column ft_offer_id to job table...')
        cur.execute("ALTER TABLE job ADD COLUMN ft_offer_id VARCHAR(30)")
        con.commit()
        print('Done.')
except Exception as e:
    print('Migration failed:', e)
    raise
finally:
    con.close()
