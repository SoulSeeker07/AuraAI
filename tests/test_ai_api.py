"""
Test AI API from .env file
Generates simple code using GLM API (ZhipuAI/BigModel)
"""

import os
import requests
import json
from pathlib import Path

# Load environment variables from .env file
env_file = Path(__file__).parent / ".env"
with open(env_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

def test_glm_api():
    """Test GLM API to generate simple code"""
    
    # Get API key
    api_key = os.environ.get("GLM_API_KEY")
    if not api_key:
        print(f"❌ GLM_API_KEY not found in environment")
        print(f"   Available keys: {list(os.environ.keys())}")
        print(f"   Current directory: {Path.cwd()}")
        print(f"   File exists: {(Path.cwd() / '.env').exists()}")
        return
    
    print(f"✅ GLM_API_KEY found: {api_key[:20]}...")
    print()
    
    # GLM API endpoint
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    # Headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Request body
    data = {
        "model": "glm-4-plus",  # Using GLM-4 Plus
        "messages": [
            {
                "role": "user",
                "content": "Write a simple Python function that calculates the " +
                          "Fibonacci sequence. Keep it very short and easy to understand."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }
    
    print("🤖 Sending request to GLM API...")
    print(f"📝 Request: {data['messages'][0]['content']}")
    print()
    
    try:
        # Make request
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"📡 Response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract generated code
            generated_code = result['choices'][0]['message']['content']
            
            print("✅ Success! Generated code:")
            print("=" * 60)
            print(generated_code)
            print("=" * 60)
            print()
            
            # Print some response info
            print("📊 Response info:")
            print(f"- Model: {result.get('model')}")
            print(f"- Usage: {result.get('usage')}")
            print()
            
            return True
        else:
            print(f"❌ API Error: {response.status_code}")
            error_data = response.json()
            print(f"   Error: {error_data.get('message', response.text)}")
            print()
            
            # Check for specific GLM errors
            if response.status_code == 429:
                print("⚠️  Account needs credits or quota is exhausted")
                print("   Please recharge or use a different account.")
            
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_groq_api():
    """Test GROQ API to generate simple code"""
    
    # Get API key
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print(f"❌ GROQ_API_KEY not found in environment")
        return
    
    print(f"✅ GROQ_API_KEY found: {api_key[:20]}...")
    print()
    
    # GROQ API endpoint
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    # Headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Request body
    data = {
        "model": "gemma2-9b-it",  # Using Google's Gemma 2 9B (open source)
        "messages": [
            {
                "role": "user",
                "content": "Write a simple Python function that calculates the " +
                          "Fibonacci sequence. Keep it very short and easy to understand."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }
    
    print("🤖 Sending request to GROQ API...")
    print(f"📝 Request: {data['messages'][0]['content']}")
    print()
    
    try:
        # Make request
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"📡 Response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract generated code
            generated_code = result['choices'][0]['message']['content']
            
            print("✅ Success! Generated code:")
            print("=" * 60)
            print(generated_code)
            print("=" * 60)
            print()
            
            # Print some response info
            print("📊 Response info:")
            print(f"- Model: {result.get('model')}")
            print(f"- Usage: {result.get('usage')}")
            print()
            
            return True
        else:
            print(f"❌ API Error: {response.status_code}")
            error_data = response.json()
            print(f"   Error: {error_data.get('error', {}).get('message', response.text)}")
            print()
            
            # Check for specific GROQ errors
            if response.status_code == 429:
                print("⚠️  Rate limit exceeded or account quota issue")
            
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing AI API from .env file")
    print()
    
    print("=" * 70)
    print("TEST 1: GLM API (ZhipuAI/BigModel)")
    print("=" * 70)
    success1 = test_glm_api()
    print()
    
    print("=" * 70)
    print("TEST 2: GROQ API (Open Source Models)")
    print("=" * 70)
    success2 = test_groq_api()
    print()
    
    if success1 or success2:
        print("✅ At least one test completed successfully!")
    else:
        print("❌ All tests failed")
        print("\n📝 Note: If tests failed, it's likely due to:")
        print("   - Insufficient API credits/quota")
        print("   - API key expired or invalid")
        print("   - Network connectivity issues")
        print("   - Rate limiting")
