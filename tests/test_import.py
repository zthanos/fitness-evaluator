#!/usr/bin/env python
import sys
try:
    import app.services.llm_client
    print("Module imported successfully")
    print(dir(app.services.llm_client))
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
