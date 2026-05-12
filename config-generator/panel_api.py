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
    Bypasses 3.0.0+ Gin CSRF protection.
    """
    if not PANEL_URL or not USERNAME or not PASSWORD:
        print("❌ Error: Panel credentials (URL, USERNAME, PASSWORD) are missing in .env")
        return None

    import re  # Импортируем модуль регулярных выражений прямо здесь для удобства

    base_url = PANEL_URL.rstrip('/')
    login_url = f"{base_url}/login"

    session = requests.Session()
    
    # 1. Базовые заголовки браузера
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": base_url,
        "Referer": f"{base_url}/"
    })

    # 2. Идем на главную страницу, чтобы получить куки и вытащить CSRF токен
    try:
        res_get = session.get(f"{base_url}/", timeout=5)
        csrf_token = None
        
        # Пытаемся найти токен в заголовках (на всякий случай)
        if 'X-CSRF-Token' in res_get.headers:
            csrf_token = res_get.headers['X-CSRF-Token']
            
        # Пытаемся вытащить токен из HTML-кода страницы (чаще всего он в <meta name="csrf-token">)
        if not csrf_token:
            match = re.search(r'name=["\']csrf-?token["\']\s+content=["\']([^"\']+)["\']', res_get.text, re.IGNORECASE)
            if match:
                csrf_token = match.group(1)
            else:
                # Альтернативный вариант - поиск в JS переменных
                match = re.search(r'csrf-?token["\']?\s*[:=]\s*["\']([^"\']+)["\']', res_get.text, re.IGNORECASE)
                if match:
                    csrf_token = match.group(1)

        # Если нашли токен - добавляем в заголовки
        if csrf_token:
            session.headers.update({"X-CSRF-Token": csrf_token})
            print(f"✅ CSRF Token extracted: {csrf_token[:5]}...")
        else:
            print("⚠️ CSRF Token not found in HTML. Login might fail.")
            
    except Exception as e:
        print(f"⚠️ Warning: Initial GET request failed: {e}")

    # 3. Отправляем форму логина (ОБЯЗАТЕЛЬНО с twoFactorCode, как просит новая версия)
    payload = {
        'username': USERNAME, 
        'password': PASSWORD,
        'twoFactorCode': ''
    }
    
    try:
        # Отправляем именно как форму (data=payload)
        res = session.post(login_url, data=payload, timeout=10)
        
        if res.status_code != 200:
            print(f"❌ Server rejected the request with HTTP {res.status_code}")
            return None
            
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