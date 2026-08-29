import requests

def list_gemini_models(api_key: str):
    endpoints = [
        "https://generativelanguage.googleapis.com/v1beta/models",
        "https://generativelanguage.googleapis.com/v1/models"
    ]
    
    for ep in endpoints:
        url = f"{ep}?key={api_key}"
        try:
            r = requests.get(url, timeout=5)
            print(f"Endpoint: {ep} -> Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
                print(f"Available generateContent models ({len(models)}):", models[:8])
                return models
            else:
                print("Error Response:", r.text[:200])
        except Exception as e:
            print("Exception:", e)
    return []

if __name__ == "__main__":
    list_gemini_models("test_key")
