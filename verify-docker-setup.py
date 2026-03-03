#!/usr/bin/env python3
"""Verify Docker setup configuration"""

import os
import json
from pathlib import Path

print("=" * 60)
print("🔍 Docker Configuration Verification")
print("=" * 60)

checks = {
    "✓ Files": [],
    "✓ Configuration": [],
    "⚠ Recommendations": [],
    "✗ Errors": []
}

# Check required files
files_to_check = {
    "docker-compose.yml": "Docker Compose configuration",
    "Dockerfile": "FastAPI container definition",
    "docker-run.sh": "Linux/Mac helper script",
    "docker-run.ps1": "Windows PowerShell helper script",
    ".env.example": "Environment configuration template",
    ".dockerignore": "Docker build optimization",
    ".gitignore": "Git ignore rules",
    "DOCKER_GUIDE.md": "Docker documentation",
    "QUICK_START.md": "Quick start guide",
    "app/config.py": "Updated configuration",
    "app/services/llm_client.py": "LLM client",
}

for filename, description in files_to_check.items():
    if Path(filename).exists():
        checks["✓ Files"].append(f"{filename} - {description}")
    else:
        checks["✗ Errors"].append(f"Missing: {filename}")

# Check Docker installation
import subprocess
try:
    result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        checks["✓ Configuration"].append(f"Docker installed: {result.stdout.strip()}")
    else:
        checks["⚠ Recommendations"].append("Docker not found in PATH - install Docker Desktop")
except FileNotFoundError:
    checks["⚠ Recommendations"].append("Docker not found - install from https://www.docker.com/products/docker-desktop")

try:
    result = subprocess.run(["docker-compose", "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        checks["✓ Configuration"].append(f"Docker Compose installed: {result.stdout.strip()}")
except FileNotFoundError:
    checks["⚠ Recommendations"].append("Docker Compose not found - included with Docker Desktop")

# Check .env file
if Path(".env").exists():
    checks["✓ Configuration"].append(".env file exists")
else:
    checks["⚠ Recommendations"].append("No .env file - run: cp .env.example .env")

# Check Python environment
try:
    import docker
    checks["✓ Configuration"].append("Docker Python library installed")
except ImportError:
    pass

# Print results
print("\n📋 Check Results:\n")

for category, items in checks.items():
    if items:
        print(f"\n{category}")
        for item in items:
            if "✓" in category:
                print(f"  ✅ {item}")
            elif "⚠" in category:
                print(f"  ⚠️  {item}")
            else:
                print(f"  ❌ {item}")

print("\n" + "=" * 60)

# Summary
errors = checks["✗ Errors"]
warnings = checks["⚠ Recommendations"]

if errors:
    print(f"\n⛔ {len(errors)} ERRORS found - fix before proceeding")
    exit(1)
elif warnings:
    print(f"\n⚠️  {len(warnings)} warnings - recommended fixes")
    print("\nTo get started:")
    print("  1. cp .env.example .env")
    print("  2. ./docker-run.sh up (Mac/Linux) or .\\docker-run.ps1 -Command up (Windows)")
    print("  3. Open http://localhost:8000")
else:
    print("\n✅ All checks passed! Ready to start.")
    print("\nNext steps:")
    print("  1. cp .env.example .env")
    print("  2. ./docker-run.sh up (Mac/Linux) or .\\docker-run.ps1 -Command up (Windows)")
    print("  3. Open http://localhost:8000")

print("\n" + "=" * 60)
