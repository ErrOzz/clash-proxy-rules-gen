import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration for Panel ---
PANEL_URL = os.getenv("PANEL_URL")
USERNAME = os.getenv("PANEL_USERNAME")
PASSWORD = os.getenv("PANEL_PASSWORD")
INBOUND_ID = int(os.getenv("INBOUND_ID", 1))

def get_panel_session():
    """
    Authenticates with the 3x-ui panel and returns a session object.
    """
    if not PANEL_URL or not USERNAME or not PASSWORD:
        print("❌ Error: Panel credentials (URL, USERNAME, PASSWORD) are missing in .env")
        return None

    session = requests.Session()
    login_url = f"{PANEL_URL}/login"
    payload = {'username': USERNAME, 'password': PASSWORD}
    
    try:
        res = session.post(login_url, data=payload)
        res.raise_for_status()
        
        response_json = res.json()
        if response_json.get('success'):
            print("✅ Login successful")
            return session
        else:
            print(f"❌ Login failed: {response_json.get('msg')}")
            return None
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None

def get_inbound_data(session):
    """
    Retrieves the specific inbound data via MHSanaei API.
    """
    try:
        # Using GET for MHSanaei API
        res = session.get(f"{PANEL_URL}/panel/api/inbounds/list")
        res.raise_for_status()
        
        data = res.json()
        if not data.get('success'):
            print(f"❌ API failure: {data.get('msg')}")
            return None
            
        inbound_list = data.get('obj', [])
        target = next((i for i in inbound_list if i['id'] == INBOUND_ID), None)
        
        if not target:
            print(f"❌ Inbound ID {INBOUND_ID} not found")
            return None
            
        return target
    except Exception as e:
        print(f"❌ API error: {e}")
        return None
    
def update_inbound(session, inbound_id, inbound_data):
    """
    Updates the inbound settings in the panel.
    """
    try:
        # MHSanaei API endpoint for updating inbound
        update_url = f"{PANEL_URL}/panel/api/inbounds/update/{inbound_id}"
        
        # We need to send the full inbound object back
        res = session.post(update_url, json=inbound_data)
        res.raise_for_status()
        
        response_json = res.json()
        if response_json.get('success'):
            print(f"✅ Inbound {inbound_id} updated successfully")
            return True
        else:
            print(f"❌ Update failed: {response_json.get('msg')}")
            return False
            
    except Exception as e:
        print(f"❌ Update API error: {e}")
        return False