import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration for Panel ---
PANEL_URL = os.getenv("PANEL_URL", "").rstrip('/')
API_TOKEN = os.getenv("PANEL_API_TOKEN")
INBOUND_ID = int(os.getenv("INBOUND_ID", 1))
SYNC_INBOUND_IDS = [int(x.strip()) for x in os.getenv("SYNC_INBOUND_IDS", str(INBOUND_ID)).split(",") if x.strip().isdigit()]

def get_panel_session():
    """
    Initializes a session with the 3x-ui panel using API Token authentication.
    Bypasses CSRF and session cookies entirely.
    """
    if not PANEL_URL or not API_TOKEN:
        print("❌ Error: PANEL_URL or PANEL_API_TOKEN are missing in .env")
        return None

    session = requests.Session()
    
    # Set up Bearer token authentication as per official API docs
    session.headers.update({
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/json"
    })
    
    print("✅ Session initialized with API Token")
    return session

def get_inbound_data(session):
    """
    Retrieves the specific inbound data via the official REST API.
    """
    try:
        res = session.get(f"{PANEL_URL}/panel/api/inbounds/list", timeout=10)
        res.raise_for_status()
        
        data = res.json()
        if not data.get('success'):
            print(f"❌ API failure: {data.get('msg')}")
            return None
            
        inbound_list = data.get('obj',[])
        target = next((i for i in inbound_list if i['id'] == INBOUND_ID), None)
        
        if not target:
            print(f"❌ Inbound ID {INBOUND_ID} not found")
            return None
            
        return target
    except Exception as e:
        print(f"❌ API error: {e}")
        return None
    
def get_inbounds_data(session):
    """
    Retrieves multiple inbounds data via the official REST API based on SYNC_INBOUND_IDS.
    """
    try:
        res = session.get(f"{PANEL_URL}/panel/api/inbounds/list", timeout=10)
        res.raise_for_status()
        
        data = res.json()
        if not data.get('success'):
            print(f"❌ API failure: {data.get('msg')}")
            return []
            
        inbound_list = data.get('obj', [])
        targets = [i for i in inbound_list if i['id'] in SYNC_INBOUND_IDS]
        
        if not targets:
            print(f"⚠️ No inbounds found matching IDs: {SYNC_INBOUND_IDS}")
            
        return targets
    except Exception as e:
        print(f"❌ API error: {e}")
        return []
    
def update_inbound(session, inbound_id, inbound_data):
    """
    Updates the inbound settings in the panel via the official REST API.
    """
    try:
        update_url = f"{PANEL_URL}/panel/api/inbounds/update/{inbound_id}"
        
        res = session.post(update_url, json=inbound_data, timeout=10)
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