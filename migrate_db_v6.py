"""
Migration v6 — ajout des colonnes manquantes (spec vs implémentation).

Nouvelles colonnes :
  user_alerts   : min_input_qty, exclude_trending_down, exclude_high_volatility, min_kontract_score
  opportunities : strategy_used, cout_ajuste, high_volatility
"""

import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///kontract.db")

if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL[len("sqlite:///"):]
elif DATABASE_URL.startswith("sqlite://"):
    db_path = DATABASE_URL[len("sqlite://"):]
else:
    db_path = "kontract.db"

print(f"Migration v6 → {db_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

MIGRATIONS = [
    # user_alerts
    "ALTER TABLE user_alerts ADD COLUMN min_input_qty INTEGER DEFAULT 10",
    "ALTER TABLE user_alerts ADD COLUMN exclude_trending_down BOOLEAN DEFAULT 0",
    "ALTER TABLE user_alerts ADD COLUMN exclude_high_volatility BOOLEAN DEFAULT 0",
    "ALTER TABLE user_alerts ADD COLUMN min_kontract_score REAL DEFAULT 0.0",
    # opportunities
    "ALTER TABLE opportunities ADD COLUMN strategy_used TEXT",
    "ALTER TABLE opportunities ADD COLUMN cout_ajuste REAL",
    "ALTER TABLE opportunities ADD COLUMN high_volatility BOOLEAN",
]

for sql in MIGRATIONS:
    try:
        cur.execute(sql)
        print(f"  OK : {sql}")
    except sqlite3.OperationalError as exc:
        print(f"  SKIP ({exc}) : {sql}")

conn.commit()
conn.close()
print("Migration v6 terminée.")
