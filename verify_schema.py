"""Verify database schema after migration."""
import sqlite3
from pathlib import Path

db_path = Path("fitness_eval.db")

if not db_path.exists():
    print("Database not found. Run the application first to create tables.")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=== Database Tables ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
for table in tables:
    print(f"  ✓ {table}")

print("\n=== Training Plan Tables ===")
training_tables = ['training_plans', 'training_plan_weeks', 'training_plan_sessions']
for table in training_tables:
    if table in tables:
        print(f"  ✓ {table} exists")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"    Columns: {', '.join(columns)}")
    else:
        print(f"  ✗ {table} missing")

print("\n=== FaissMetadata user_id Column ===")
cursor.execute("PRAGMA table_info(faiss_metadata)")
columns = [row[1] for row in cursor.fetchall()]
if 'user_id' in columns:
    print("  ✓ user_id column exists in faiss_metadata")
else:
    print("  ✗ user_id column missing from faiss_metadata")

print("\n=== Indexes ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
indexes = [row[0] for row in cursor.fetchall()]
required_indexes = [
    'idx_training_plans_user_id',
    'idx_training_plans_status',
    'idx_training_plan_weeks_plan_id',
    'idx_training_plan_sessions_week_id',
    'idx_training_plan_sessions_completed',
    'idx_training_plan_sessions_matched_activity',
    'idx_faiss_metadata_user_id'
]
for idx in required_indexes:
    if idx in indexes:
        print(f"  ✓ {idx}")
    else:
        print(f"  ✗ {idx} missing")

conn.close()
print("\n✓ Schema verification complete!")
