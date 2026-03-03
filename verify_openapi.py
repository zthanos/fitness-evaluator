#!/usr/bin/env python
from app.main import app

# Get OpenAPI schema
schema = app.openapi()
print('✓ OpenAPI Schema Generated Successfully')
print(f'  - Total Paths: {len(schema.get("paths", {}))}')
print(f'  - Tags: {len(schema.get("tags", []))}')
print(f'  - Schemas: {len(schema.get("components", {}).get("schemas", {}))}')
print()
print('API Organization:')
for tag in schema.get('tags', []):
    name = tag.get('name', 'unknown')
    desc = tag.get('description', 'No description')
    print(f'  • {name}: {desc}')

print()
print('Documentation Endpoints:')
print('  • Swagger UI: http://localhost:8000/docs')
print('  • ReDoc: http://localhost:8000/redoc')
print('  • OpenAPI JSON: http://localhost:8000/openapi.json')
