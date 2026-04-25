"""
Migrate data from SQLite to PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite fitness_eval.db \
        --postgres postgresql://fitness_user:fitness_password@localhost:5460/fitness

Tables migrated:
    athletes, chat_sessions, chat_messages, daily_logs

Skipped (will be repopulated by the app):
    faiss_metadata  -> vector_embeddings requires re-embedding; RAG engine handles this on first use
    strava_tokens   -> encrypted bytes tied to old key; user must reconnect Strava
    alembic_version -> managed by alembic, not copied
    all empty tables
"""
import argparse
import sqlite3
import sys
from datetime import datetime


def parse_args():
    p = argparse.ArgumentParser(description="Migrate SQLite -> PostgreSQL")
    p.add_argument("--sqlite", default="fitness_eval.db", help="Path to SQLite db file")
    p.add_argument(
        "--postgres",
        default="postgresql://fitness_user:fitness_password@localhost:5460/fitness",
        help="PostgreSQL connection string",
    )
    p.add_argument("--dry-run", action="store_true", help="Print what would be done without writing")
    return p.parse_args()


def migrate_athletes(sqlite_cur, pg_cur, dry_run):
    sqlite_cur.execute("SELECT id, name, email, date_of_birth, current_plan, goals, created_at, updated_at FROM athletes")
    rows = sqlite_cur.fetchall()
    print(f"\nathletes: {len(rows)} row(s)")
    for row in rows:
        id_, name, email, dob, plan, goals, created_at, updated_at = row
        print(f"  -> id={id_} name={name!r} email={email!r}")
        if not dry_run:
            pg_cur.execute(
                """
                INSERT INTO athletes (id, name, email, date_of_birth, current_plan, goals, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (id_, name, email, dob, plan, goals, created_at, updated_at),
            )
    if not dry_run and rows:
        # Sync the sequence so auto-increment doesn't collide
        max_id = max(r[0] for r in rows)
        pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('athletes', 'id'), {max_id})")


def migrate_chat_sessions(sqlite_cur, pg_cur, dry_run):
    sqlite_cur.execute("SELECT id, athlete_id, title, created_at, updated_at FROM chat_sessions")
    rows = sqlite_cur.fetchall()
    print(f"\nchat_sessions: {len(rows)} row(s)")
    for row in rows:
        id_, athlete_id, title, created_at, updated_at = row
        print(f"  -> id={id_} athlete_id={athlete_id} title={title!r}")
        if not dry_run:
            pg_cur.execute(
                """
                INSERT INTO chat_sessions (id, athlete_id, title, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (id_, athlete_id, title, created_at, updated_at),
            )
    if not dry_run and rows:
        max_id = max(r[0] for r in rows)
        pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('chat_sessions', 'id'), {max_id})")


def migrate_chat_messages(sqlite_cur, pg_cur, dry_run):
    sqlite_cur.execute("SELECT id, session_id, role, content, created_at FROM chat_messages")
    rows = sqlite_cur.fetchall()
    print(f"\nchat_messages: {len(rows)} row(s)")
    for row in rows:
        id_, session_id, role, content, created_at = row
        print(f"  -> id={id_} session_id={session_id} role={role}")
        if not dry_run:
            pg_cur.execute(
                """
                INSERT INTO chat_messages (id, session_id, role, content, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (id_, session_id, role, content, created_at),
            )
    if not dry_run and rows:
        max_id = max(r[0] for r in rows)
        pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('chat_messages', 'id'), {max_id})")


def migrate_daily_logs(sqlite_cur, pg_cur, dry_run):
    sqlite_cur.execute(
        "SELECT id, log_date, fasting_hours, calories_in, protein_g, carbs_g, fat_g, "
        "adherence_score, notes, week_id, created_at, updated_at FROM daily_logs"
    )
    rows = sqlite_cur.fetchall()
    print(f"\ndaily_logs: {len(rows)} row(s)")
    for row in rows:
        id_ = row[0]
        print(f"  -> id={id_} log_date={row[1]}")
        if not dry_run:
            pg_cur.execute(
                """
                INSERT INTO daily_logs
                    (id, log_date, fasting_hours, calories_in, protein_g, carbs_g, fat_g,
                     adherence_score, notes, week_id, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO NOTHING
                """,
                row,
            )


def main():
    args = parse_args()

    # Connect SQLite
    try:
        sqlite_conn = sqlite3.connect(args.sqlite)
        sqlite_cur = sqlite_conn.cursor()
    except Exception as e:
        print(f"ERROR: Cannot open SQLite db {args.sqlite!r}: {e}")
        sys.exit(1)

    # Connect PostgreSQL
    try:
        import psycopg2
        pg_conn = psycopg2.connect(args.postgres)
        pg_cur = pg_conn.cursor()
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot connect to PostgreSQL {args.postgres!r}: {e}")
        sys.exit(1)

    if args.dry_run:
        print("DRY RUN — no data will be written\n")

    try:
        migrate_athletes(sqlite_cur, pg_cur, args.dry_run)
        migrate_chat_sessions(sqlite_cur, pg_cur, args.dry_run)
        migrate_chat_messages(sqlite_cur, pg_cur, args.dry_run)
        migrate_daily_logs(sqlite_cur, pg_cur, args.dry_run)

        print("\nSkipped:")
        print("  faiss_metadata  (6 rows) — vector_embeddings needs re-embedding; RAG will repopulate")
        print("  strava_tokens           — encrypted with old key; reconnect Strava after migration")

        if not args.dry_run:
            pg_conn.commit()
            print("\nMigration complete.")
        else:
            print("\nDry run complete — nothing written.")
    except Exception as e:
        if not args.dry_run:
            pg_conn.rollback()
        print(f"\nERROR during migration: {e}")
        raise
    finally:
        sqlite_conn.close()
        pg_cur.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
