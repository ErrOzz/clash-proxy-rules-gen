import os
import json
import yaml
import secrets
import random
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from dotenv import load_dotenv

# Import our internal modules
from panel_api import get_panel_session, get_inbound_data, update_inbound
from domain_tls_checker import check_domain_tls13  # NEW IMPORT
import sync_configs  # Trigger Gist update

# Load environment variables
load_dotenv()

INBOUND_ID = int(os.getenv("INBOUND_ID", 1))

def generate_x25519_keys():
    """
    Generates X25519 keys using Python 'cryptography'.
    Uses URL-Safe Base64 encoding to be compatible with Xray/Panel.
    """
    # 1. Generate Private Key
    private_key_obj = x25519.X25519PrivateKey.generate()
    
    # 2. Derive Public Key
    public_key_obj = private_key_obj.public_key()
    
    # 3. Get raw bytes
    private_bytes = private_key_obj.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_bytes = public_key_obj.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    # 4. Encode URL-SAFE and strip padding
    # This replaces '+' with '-' and '/' with '_'
    private_b64 = base64.urlsafe_b64encode(private_bytes).decode('utf-8').rstrip('=')
    public_b64 = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')
    
    return private_b64, public_b64

def generate_short_ids(count=4):
    """
    Generates a list of random ShortIds.
    """
    return [secrets.token_hex(4) for _ in range(count)]

def load_rotation_domains():
    """
    Loads the list of domains from YAML file.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'rotation_domains.yaml')
    
    if not os.path.exists(file_path):
        print("❌ rotation_domains.yaml not found!")
        return []
        
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def rotate():
    print("🔄 Starting Reality rotation process...")

    # 1. Authenticate
    session = get_panel_session()
    if not session: return

    # 2. Get Current Inbound Data
    inbound = get_inbound_data(session)
    if not inbound: return
    
    print(f"ℹ️ Target Inbound: {inbound['remark']}")

    # 3. Parse current settings
    try:
        stream_settings = json.loads(inbound['streamSettings'])
        if stream_settings.get('security') != 'reality':
            print("❌ Error: Inbound is not using Reality security. Aborting.")
            return
            
        reality_settings = stream_settings.get('realitySettings', {})
        current_snis = reality_settings.get('serverNames', [''])
        current_main_sni = current_snis[0] if current_snis else ""
        
    except Exception as e:
        print(f"❌ Error parsing current settings: {e}")
        return

    # 4. Prepare New Settings
    
    # A. Pick new Domain with TLS 1.3 Validation
    domains = load_rotation_domains()
    if not domains:
        print("❌ No domains loaded. Aborting.")
        return
        
    current_root = current_main_sni.replace("www.", "")
    
    # Filter out current domain to ensure change
    available_domains = [d for d in domains if d.replace("www.", "") != current_root]
    
    if not available_domains:
        print("⚠️ No other domains available in list. Using current pool.")
        available_domains = [d for d in domains] # fallback to all domains

    # Shuffle list to pick randomly
    random.shuffle(available_domains)
    
    selected_domain = None
    
    print("🔍 Checking domains for TLS 1.3 support...")
    for domain in available_domains:
        # Ensure we check the clean domain name
        clean_domain = domain.replace("www.", "")
        
        # Validate!
        if check_domain_tls13(clean_domain):
            selected_domain = clean_domain
            break # Found a working domain!
        else:
            print(f"⏩ Skipping {clean_domain} (Validation failed)")
            
    if not selected_domain:
        print("❌ CRITICAL: No valid TLS 1.3 domains found in the list! Aborting rotation to preserve connectivity.")
        return

    root_domain = selected_domain

    # B. Generate SNI List & Dest
    # We use the domain exactly as provided (validated above).
    # If it's a subdomain (dl.google.com), we don't need 'www'.
    new_snis = [root_domain]
    
    # Optional: Add 'www' ONLY if the domain looks like a root domain (has only 1 dot)
    if root_domain.count('.') == 1:
        new_snis.append(f"www.{root_domain}")
        
    new_dest = f"{root_domain}:443"

    # C. Generate New Keys (Python + URLSafe)
    new_private_key, new_public_key = generate_x25519_keys()
    
    # D. Generate New ShortIds
    new_short_ids = generate_short_ids(4)

    print(f"✅ Selected Domain: {root_domain}")
    print(f"   Target (Dest): {new_dest}")
    print(f"   New Public Key: {new_public_key}")

    # 5. Modify Inbound Object
    
    reality_settings['serverNames'] = new_snis
    reality_settings['shortIds'] = new_short_ids
    reality_settings['target'] = new_dest
    
    # --- KEY UPDATE FIX ---
    # Ensure 'settings' exists for publicKey
    if 'settings' not in reality_settings:
        reality_settings['settings'] = {}
        
    # Public Key goes into nested 'settings'
    reality_settings['settings']['publicKey'] = new_public_key
    
    # Private Key goes into ROOT of 'realitySettings' (Typical for MHSanaei)
    reality_settings['privateKey'] = new_private_key
    # ----------------------
    
    # Pack back
    stream_settings['realitySettings'] = reality_settings
    inbound['streamSettings'] = json.dumps(stream_settings)

    # 6. Send Update
    print("⏳ Updating panel settings...")
    success = update_inbound(session, INBOUND_ID, inbound)
    
    if success:
        print("✅ Rotation successful!")
        print("🚀 Triggering config sync...")
        sync_configs.main()
    else:
        print("❌ Rotation failed.")

if __name__ == "__main__":
    rotate()