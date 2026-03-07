"""Debug script to test Strava sync and see detailed errors."""
import asyncio
import traceback
from app.database import SessionLocal
from app.services.strava_client import StravaClient


async def test_sync():
    """Test the sync_activities method and print detailed errors."""
    db = SessionLocal()
    
    try:
        print("Creating StravaClient...")
        client = StravaClient(db)
        
        print("Starting sync for athlete_id=1...")
        synced_count = await client.sync_activities(athlete_id=1)
        
        print(f"✅ Success! Synced {synced_count} activities")
        
    except Exception as e:
        print(f"❌ Error occurred!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Error repr: {repr(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_sync())
