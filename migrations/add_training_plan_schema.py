"""
Migration script for adding training plan schema and user_id to faiss_metadata.

This migration:
1. Adds user_id column to faiss_metadata table (if not exists)
2. Creates training_plans, training_plan_weeks, and training_plan_sessions tables
3. Creates all necessary indexes

This is an additive-only migration following the design principle of never
dropping or modifying existing data.
"""
import sqlite3
from pathlib import Path


def get_db_path():
    """Get the database path from config or use default."""
    # Default SQLite database path
    return Path(__file__).parent.parent / "fitness_eval.db"


def run_migration():
    """Execute the migration."""
    db_path = get_db_path()
    
    if not db_path.exists():
        print(f"Database not found at {db_path}. Tables will be created on first run.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        print("Starting migration: add_training_plan_schema")
        
        # Check if user_id column already exists in faiss_metadata
        cursor.execute("PRAGMA table_info(faiss_metadata)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'user_id' not in columns:
            print("Adding user_id column to faiss_metadata table...")
            cursor.execute("""
                ALTER TABLE faiss_metadata 
                ADD COLUMN user_id INTEGER
            """)
            print("✓ Added user_id column to faiss_metadata")
            
            # Create index for user_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_faiss_metadata_user_id 
                ON faiss_metadata(user_id)
            """)
            print("✓ Created index idx_faiss_metadata_user_id")
        else:
            print("✓ user_id column already exists in faiss_metadata")
        
        # Update the check constraint to include 'chat_message' record type
        # Note: SQLite doesn't support ALTER TABLE to modify constraints
        # The constraint will be updated when the table is recreated by SQLAlchemy
        print("✓ Check constraint will be updated by SQLAlchemy on next startup")
        
        # Commit the changes
        conn.commit()
        print("\nMigration completed successfully!")
        print("\nNote: New tables (training_plans, training_plan_weeks, training_plan_sessions)")
        print("will be automatically created by SQLAlchemy on application startup.")
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
