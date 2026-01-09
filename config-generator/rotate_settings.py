import os
import json
import yaml
import secrets
import random
import subprocess
import re
from dotenv import load_dotenv

# Import our internal modules
from panel_api import get_panel_session, get_inbound_data, update_inbound
import sync_configs  # Trigger Gist update

# Load environment variables
load_dotenv()

INBOUND_ID = int(os.getenv("INBOUND_ID", 1))
DOCKER_CONTAINER_NAME = os.getenv("DOCKER_CONTAINER_NAME", "3x-ui")

def generate_x25519_keys():
    """
    Generates X25519 keys by executing the Xray binary inside the Docker container.
    Adapts to the specific output format of the user's binary (PrivateKey/Password).
    """
    # The path found via docker top
    xray_path = "/app/bin/xray-linux-amd64"
    
    # Command: docker exec <container> <path_to_xray> x25519
    cmd = ["docker", "exec", DOCKER_CONTAINER_NAME, xray_path, "x25519"]
    
    try:
        # Run command and capture output
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
        
        # DEBUG: Uncomment the line below if regex fails again
        # print(f"🔍 DEBUG: Raw Xray Output:\n{output}")

        # Parse output using Regex adapted for this binary version:
        # Expected format:
        # PrivateKey: <key>
        # Password: <key>   <-- This is actually the Public Key in this version
        priv_match = re.search(r"PrivateKey:\s*(\S+)", output)
        pub_match = re.search(r"Password:\s*(\S+)", output)
        
        if not priv_match or not pub_match:
            # Fallback check for standard format just in case
            priv_match_std = re.search(r"Private Key:\s*(\S+)", output)
            pub_match_std = re.search(r"Public Key:\s*(\S+)", output)
            
            if priv_match_std and pub_match_std:
                priv_match, pub_match = priv_match_std, pub_match_std
            else:
                raise ValueError(f"Could not parse Xray output. Raw output:\n{output}")
            
        private_key = priv_match.group(1).strip()
        public_key = pub_match.group(1).strip()
        
        return private_key, public_key

    except subprocess.CalledProcessError as e:
        print(f"❌ Docker execution failed: {e.output.decode('utf-8')}")
        raise
    except Exception as e:
        print(f"❌ Error generating keys via Docker: {e}")
        raise

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
    print("🔄 Starting Reality rotation process (via Docker Xray)...")

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
    
    # A. Pick new Domain
    domains = load_rotation_domains()
    if not domains:
        print("❌ No domains loaded. Aborting.")
        return
        
    available_domains = [d for d in domains if d != current_main_sni]
    
    if not available_domains:
        print("⚠️ Only current domain available. Rotating keys only.")
        root_domain = current_main_sni or domains[0]
    else:
        root_domain = random.choice(available_domains)

    # B. Generate SNI List & Dest
    new_snis = [root_domain, f"www.{root_domain}"]
    new_dest = f"{root_domain}:443"

    # C. Generate New Keys (Docker Exec)
    try:
        new_private_key, new_public_key = generate_x25519_keys()
    except Exception:
        return # Stop if key gen failed

    # D. Generate New ShortIds
    new_short_ids = generate_short_ids(4)

    print(f"🆕 Selected Domain: {root_domain}")
    print(f"   Target (Dest): {new_dest}")
    print(f"   New Public Key: {new_public_key}")

    # 5. Modify Inbound Object
    
    reality_settings['serverNames'] = new_snis
    reality_settings['shortIds'] = new_short_ids
    
    # MHSanaei target/dest fix
    reality_settings['target'] = new_dest
    
    # Update Keys
    if 'settings' not in reality_settings:
        reality_settings['settings'] = {}
        
    reality_settings['settings']['publicKey'] = new_public_key
    reality_settings['settings']['privateKey'] = new_private_key
    
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