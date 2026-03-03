#!/usr/bin/env python
import sys
try:
    print("Testing llm_client imports...")
    
    print("1. Importing httpx...")
    import httpx
    print("   ✓ httpx imported")
    
    print("2. Importing json...")
    import json
    print("   ✓ json imported")
    
    print("3. Importing asyncio...")
    import asyncio
    print("   ✓ asyncio imported")
    
    print("4. Importing app.config...")
    from app.config import get_settings
    print("   ✓ app.config imported")
    
    print("5. Testing get_settings()...")
    settings = get_settings()
    print(f"   ✓ Settings: {settings.LM_STUDIO_BASE_URL}")
    
    print("\nAll imports successful! Now trying module import...")
    import app.services.llm_client as llm
    print(f"Module contents: {dir(llm)}")
    
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
