#!/usr/bin/env python
"""Quick test to verify FastAPI app is configured correctly."""

try:
    from app.main import app
    print("✓ App imported successfully")
    
    # Get routes
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append((route.path, list(route.methods or [])))
    
    print(f"✓ Found {len(routes)} routes configured")
    
    # Show API routes
    api_routes = [r for r in routes if '/api' in r[0]]
    print(f"✓ API routes: {len(api_routes)}")
    for path, methods in sorted(api_routes)[:10]:
        print(f"   {', '.join(sorted(methods)):10} {path}")
    
    # Check static files
    from pathlib import Path
    static_dir = Path("public")
    if static_dir.exists():
        html_files = list(static_dir.glob("*.html"))
        print(f"✓ Static files configured ({len(html_files)} HTML files found)")
    else:
        print("✗ public/ directory not found")
    
    print("\n✓ Configuration looks good!")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
