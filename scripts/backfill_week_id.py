#!/usr/bin/env python3
"""
Backfill script for populating week_id field in StravaActivity records.

This script queries all StravaActivity records where week_id is null,
computes the week_id from start_date using ISO week format (YYYY-WW),
and updates records in batches for performance.

Usage:
    python scripts/backfill_week_id.py
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.strava_activity import StravaActivity


def backfill_week_ids(batch_size: int = 100) -> None:
    """
    Backfill week_id for all StravaActivity records with null week_id.
    
    Args:
        batch_size: Number of records to update per batch (default: 100)
    """
    db: Session = SessionLocal()
    
    try:
        # Query all activities with null week_id
        print("Querying activities with null week_id...")
        activities = db.query(StravaActivity).filter(
            StravaActivity.week_id.is_(None)
        ).all()
        
        total_count = len(activities)
        
        if total_count == 0:
            print("No activities found with null week_id. Nothing to backfill.")
            return
        
        print(f"Found {total_count} activities to backfill.")
        
        # Process in batches
        updated_count = 0
        batch_count = 0
        
        for i, activity in enumerate(activities):
            # Compute week_id from start_date using the model's static method
            if activity.start_date:
                activity.week_id = StravaActivity.compute_week_id(activity.start_date)
                updated_count += 1
            else:
                print(f"Warning: Activity {activity.id} has no start_date, skipping.")
            
            # Commit batch
            if (i + 1) % batch_size == 0:
                db.commit()
                batch_count += 1
                print(f"Updated {updated_count}/{total_count} activities (batch {batch_count})...")
        
        # Commit remaining records
        if updated_count % batch_size != 0:
            db.commit()
            batch_count += 1
            print(f"Updated {updated_count}/{total_count} activities (final batch)...")
        
        print(f"\nBackfill complete! Updated {updated_count} activities in {batch_count} batches.")
        
    except Exception as e:
        print(f"Error during backfill: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Main entry point for the backfill script."""
    print("=" * 60)
    print("StravaActivity week_id Backfill Script")
    print("=" * 60)
    print()
    
    try:
        backfill_week_ids(batch_size=100)
        print("\nBackfill completed successfully!")
        return 0
    except Exception as e:
        print(f"\nBackfill failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
