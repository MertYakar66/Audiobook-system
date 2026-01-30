
import requests
import json
import sys

BASE_URL = "http://localhost:13378"
USERNAME = "root"
PASSWORD = "1234"

def setup_library():
    # 1. Login
    print("Logging in...")
    login_payload = {
        "username": USERNAME,
        "password": PASSWORD
    }
    
    try:
        res = requests.post(f"{BASE_URL}/login", json=login_payload)
        if res.status_code != 200:
            # If login fails, maybe it's the first time setup?
            # Audiobookshelf usually requires creating the first user.
            # Let's check init status
            print(f"Login failed: {res.status_code} {res.text}. Checking if setup is needed...")
            return False
            
        token = res.json().get("user", {}).get("token") or res.json().get("token")
        if not token:
            # Maybe the response structure is different
            print(f"Could not get token from response: {res.text}")
            return False
            
        print("Login successful.")
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Check libraries
        res = requests.get(f"{BASE_URL}/api/libraries", headers=headers)
        libraries = res.json().get("libraries", [])
        print(f"Found {len(libraries)} libraries.")
        
        for lib in libraries:
            if lib["name"] == "Audiobooks":
                print("Library 'Audiobooks' already exists.")
                return True
        
        # 3. Create Library
        print("Creating 'Audiobooks' library...")
        # Audiobookshelf requires a folder path for the library.
        # Based on docker-compose, /audiobooks is mapped to volumes/audiobooks (or similar).
        # We need to know the mapping. 
        # Typically startup script mapped volumes/audiobooks -> /audiobooks (inside container).
        
        library_payload = {
            "name": "Audiobooks",
            "folders": [{"path": "/audiobooks"}], 
            "icon": "default",
            "mediaType": "book",
            "provider": "google", # Metadata provider
            "settings": {
                "autoScanCronExpression": "0 0 * * *"
            }
        }
        
        res = requests.post(f"{BASE_URL}/api/libraries", json=library_payload, headers=headers)
        if res.status_code == 200:
            print("Library created successfully.")
            return True
        else:
            print(f"Failed to create library: {res.status_code} {res.text}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    setup_library()
