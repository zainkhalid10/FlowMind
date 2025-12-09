"""Model health check service - checks if AI models are available and running"""
import requests
import os
import asyncio
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor

# Model configurations
MODELS_TO_CHECK = {
    "llama3:latest": {
        "type": "LLM",
        "endpoint": "http://localhost:11434/api/generate",
        "timeout": 10
    },
    "llava:13b": {
        "type": "VLM",
        "endpoint": "http://localhost:11434/api/generate",
        "timeout": 15
    },
    "qwen2.5vl:latest": {
        "type": "VLM",
        "endpoint": "http://localhost:11434/api/generate",
        "timeout": 15
    }
}

def check_ollama_connection() -> bool:
    """Check if Ollama service is running."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def check_model_availability(model_name: str) -> Dict[str, any]:
    """Check if a specific model is available and working."""
    model_config = MODELS_TO_CHECK.get(model_name)
    if not model_config:
        return {
            "model": model_name,
            "status": "unknown",
            "message": f"Model {model_name} not in check list"
        }
    
    try:
        # For LLM models, just check with a simple prompt
        if model_config["type"] == "LLM":
            response = requests.post(
                model_config["endpoint"],
                json={
                    "model": model_name,
                    "prompt": "Say OK",
                    "stream": False
                },
                timeout=model_config["timeout"]
            )
            if response.status_code == 200:
                return {
                    "model": model_name,
                    "type": model_config["type"],
                    "status": "available",
                    "message": "Model is working"
                }
            else:
                return {
                    "model": model_name,
                    "type": model_config["type"],
                    "status": "error",
                    "message": f"HTTP {response.status_code}"
                }
        
        # For VLM models, check with a simple image
        elif model_config["type"] == "VLM":
            import base64
            from PIL import Image
            import io
            
            # Create a tiny test image
            img = Image.new('RGB', (10, 10), color='blue')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            
            response = requests.post(
                model_config["endpoint"],
                json={
                    "model": model_name,
                    "prompt": "What color?",
                    "images": [img_b64],
                    "stream": False
                },
                timeout=model_config["timeout"]
            )
            if response.status_code == 200:
                return {
                    "model": model_name,
                    "type": model_config["type"],
                    "status": "available",
                    "message": "Model is working"
                }
            else:
                return {
                    "model": model_name,
                    "type": model_config["type"],
                    "status": "error",
                    "message": f"HTTP {response.status_code}"
                }
    except requests.exceptions.Timeout:
        return {
            "model": model_name,
            "type": model_config["type"],
            "status": "timeout",
            "message": f"Model timed out after {model_config['timeout']}s"
        }
    except Exception as e:
        return {
            "model": model_name,
            "type": model_config["type"],
            "status": "error",
            "message": str(e)[:100]
        }

def check_all_models() -> Dict[str, any]:
    """Check all models and return status."""
    print("\n" + "="*70)
    print("🔍 MODEL HEALTH CHECK - Starting...")
    print("="*70 + "\n")
    
    # Check Ollama connection first
    ollama_available = check_ollama_connection()
    if not ollama_available:
        print("❌ Ollama service is not running on localhost:11434")
        print("💡 Please start Ollama: ollama serve")
        return {
            "ollama_available": False,
            "models": {}
        }
    
    print("✅ Ollama service is running")
    
    # Check each model
    results = {}
    for model_name in MODELS_TO_CHECK.keys():
        print(f"\n📊 Checking {model_name} ({MODELS_TO_CHECK[model_name]['type']})...")
        result = check_model_availability(model_name)
        results[model_name] = result
        
        if result["status"] == "available":
            print(f"   ✅ {model_name} is WORKING")
        elif result["status"] == "timeout":
            print(f"   ⏱️  {model_name} timed out - may be slow or unavailable")
        else:
            print(f"   ❌ {model_name} is NOT available: {result['message']}")
    
    print("\n" + "="*70)
    print("✅ Model health check complete")
    print("="*70 + "\n")
    
    return {
        "ollama_available": True,
        "models": results
    }

async def check_models_async() -> Dict[str, any]:
    """Async version of model health check."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(executor, check_all_models)
    return result

