"""Test script to debug LM Studio connection"""
import requests
import json

print("Testing LM Studio connection...\n")

# Test 1: Check if server is running
print("1. Testing base endpoint (http://localhost:1234)")
try:
    response = requests.get("http://localhost:1234", timeout=5)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 2: Check /v1/models endpoint
print("2. Testing /v1/models endpoint")
try:
    response = requests.get("http://localhost:1234/v1/models", timeout=5)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Models available: {json.dumps(data, indent=2)}")
    else:
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 3: Try a simple chat completion
print("3. Testing /v1/chat/completions endpoint")
try:
    response = requests.post(
        "http://localhost:1234/v1/chat/completions",
        json={
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        },
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Chat completion works!")
        data = response.json()
        print(f"   Response preview: {json.dumps(data, indent=2)[:300]}")
    else:
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 60)
print("DIAGNOSIS:")
print("=" * 60)

# Provide diagnosis
try:
    models_response = requests.get("http://localhost:1234/v1/models", timeout=5)
    if models_response.status_code == 200:
        print("✅ LM Studio server is running correctly")
        print("✅ The /v1/models endpoint works")
        
        # Check if chat completions work
        try:
            chat_response = requests.post(
                "http://localhost:1234/v1/chat/completions",
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5
                },
                timeout=10
            )
            if chat_response.status_code == 200:
                print("✅ Chat completions endpoint works")
                print("\n🎉 LM Studio is configured correctly!")
                print("\nThe issue might be with LangChain's configuration.")
                print("Try using the exact model name from the /v1/models response above.")
            elif chat_response.status_code == 404:
                print("❌ Chat completions endpoint returns 404")
                print("\nPossible issues:")
                print("1. Model name might be incorrect")
                print("2. Model might not be loaded in LM Studio")
                print("3. LM Studio version might not support this endpoint")
            else:
                print(f"❌ Chat completions returned status {chat_response.status_code}")
                print(f"   Response: {chat_response.text[:200]}")
        except Exception as e:
            print(f"❌ Chat completions test failed: {e}")
    else:
        print("❌ LM Studio server is not responding correctly")
        print("\nPlease check:")
        print("1. Is LM Studio running?")
        print("2. Is the server started in the 'Local Server' tab?")
        print("3. Is a model loaded?")
except Exception as e:
    print("❌ Cannot connect to LM Studio")
    print(f"   Error: {e}")
    print("\nPlease check:")
    print("1. Is LM Studio installed and running?")
    print("2. Is the server started in the 'Local Server' tab?")
    print("3. Is the server running on port 1234?")
