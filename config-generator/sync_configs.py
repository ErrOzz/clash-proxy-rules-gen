import os
import json
import yaml
import requests
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

# Import API functions from our module
from panel_api import get_panel_session, get_inbound_data, get_inbounds_data
import fetch_subs

# Load environment variables
load_dotenv()

# --- Configuration ---
# Note: Panel credentials are now handled inside panel_api.py, 
# but we still need these variables here for logic or Gist.
GIST_ID = os.getenv("GIST_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SERVER_HOST = os.getenv("SERVER_HOST")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
RULE_PROVIDER_URL = os.getenv("RULE_PROVIDER_URL")
TEMPLATE_NAME = os.getenv("TEMPLATE_NAME", "clash_client_template.yaml.j2")
PROVIDER_SINGLE_NAME = os.getenv("PROVIDER_SINGLE_NAME", "Single")
PROVIDER_MULTI_NAME = os.getenv("PROVIDER_MULTI_NAME", "Multi")

# --- Helper Functions ---

def to_yaml_filter(value):
    """
    Custom Jinja2 filter to convert Python dict to YAML string.
    sort_keys=False is CRITICAL to maintain the order defined in the dictionary.
    """
    return yaml.dump(value, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()

def strip_comments(text):
    """
    Removes YAML comments (lines starting with # and inline comments).
    Preserves empty lines for readability.
    """
    cleaned_lines = []
    for line in text.splitlines():
        # 1. Skip full line comments (e.g. "# Settings")
        if line.strip().startswith('#'):
            continue
        
        # 2. Remove inline comments (e.g. "port: 443 # Default")
        # We split by " #" (space + hash) to avoid breaking things like colors "#FFF" or URLs
        if ' #' in line:
            line = line.split(' #', 1)[0].rstrip()
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)

def load_extra_servers():
    """
    Loads extra servers from the local YAML file.
    Now returns a dictionary with 'single_node' and 'multi_nodes' lists.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'extra_servers.yaml')

    # Default structure
    empty_servers = {'single_node': [], 'multi_nodes':[]}

    if not os.path.exists(file_path):
        return empty_servers

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else empty_servers
    except Exception as e:
        print(f"❌ Error loading extra servers: {e}")
        return empty_servers

def update_gist(files_payload):
    """Uploads to Gist."""
    if not GITHUB_TOKEN or not GIST_ID:
        print("⚠️ GITHUB_TOKEN or GIST_ID missing.")
        return

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
    }
    
    try:
        print(f"🚀 Uploading {len(files_payload)} files to Gist...")
        res = requests.patch(f"https://api.github.com/gists/{GIST_ID}", headers=headers, json={'files': files_payload})
        res.raise_for_status()
        print("✅ Gist updated successfully!")
    except Exception as e:
        print(f"❌ Upload failed: {e}")

# --- Core Logic ---

def parse_inbound_json(inbound):
    """
    Unpacks the settings from the inbound data.
    Handles both string (legacy API) and dict (new API) formats.
    """
    try:
        stream_settings = inbound.get('streamSettings', {})
        if isinstance(stream_settings, str):
            stream_settings = json.loads(stream_settings)
            
        settings = inbound.get('settings', {})
        if isinstance(settings, str):
            settings = json.loads(settings)
            
        return stream_settings, settings
    except Exception as e:
        print(f"❌ JSON Parsing error: {e}")
        return None, None

def build_client_proxy(client, inbound, stream_settings, general_settings):
    """
    Constructs the dictionary for a specific client following the EXACT requested order.
    """
    
    # 0. Check Protocol
    if inbound['protocol'] != 'vless':
        return None

    address = SERVER_HOST if SERVER_HOST else "YOUR_SERVER_IP"

    # Start building dictionary
    proxy = {}

    # --- Block 1: Basic Info ---
    proxy['name'] = inbound['remark']
    proxy['type'] = 'vless'
    proxy['server'] = address
    proxy['port'] = inbound['port']
    proxy['udp'] = True
    proxy['uuid'] = client['id']

    if client.get('flow'):
        proxy['flow'] = client['flow']

    proxy['packet-encoding'] = 'xudp'

    # --- Block 2: Reality / TLS ---
    security = stream_settings.get('security', 'none')

    if security == 'reality':
        proxy['tls'] = True
        
        # Reality Settings Extraction
        reality_settings = stream_settings.get('realitySettings', {})
        r_settings = reality_settings.get('settings', {})
        
        server_names = reality_settings.get('serverNames', [''])
        proxy['servername'] = server_names[0] if server_names else ""

        proxy['alpn'] = ['h2', 'http/1.1']
        proxy['client-fingerprint'] = r_settings.get('fingerprint', 'chrome')
        proxy['skip-cert-verify'] = True

        proxy['reality-opts'] = {
            'public-key': r_settings.get('publicKey', ''),
            'short-id': reality_settings.get('shortIds', [''])[0]
        }

    # --- Block 3: Encryption ---
    proxy['encryption'] = general_settings.get('encryption', "")

    # --- Block 4: Network ---
    network = stream_settings.get('network', 'tcp')
    proxy['network'] = network

    if network == 'xhttp':
        xhttp_settings = stream_settings.get('xhttpSettings', {})
        proxy['xhttp-opts'] = {}
        if 'path' in xhttp_settings:
            proxy['xhttp-opts']['path'] = xhttp_settings['path']
        if 'host' in xhttp_settings:
            proxy['xhttp-opts']['headers'] = {'Host': xhttp_settings['host']}
        if 'mode' in xhttp_settings:
            proxy['xhttp-opts']['mode'] = xhttp_settings['mode']

    return proxy

def main():
    # 0. Update Extra Servers from Subscriptions
    print("🌐 Step 0: Updating external subscriptions...")
    fetch_subs.update_extra_servers()
    print("-" * 30)

    # 1. Create API Session
    session = get_panel_session()
    if not session: return

    # 2. Get ALL targeted inbounds
    inbounds = get_inbounds_data(session)
    if not inbounds: return

    # Group proxies by client email
    # Structure: {'email': [proxy1, proxy2]}
    clients_proxies_map = {}

    # 3. Parse JSON Data for all inbounds
    for inbound in inbounds:
        print(f"ℹ️ Processing inbound: {inbound['remark']} ({inbound['protocol']})")
        stream_settings, general_settings = parse_inbound_json(inbound)
        if not stream_settings: continue

        clients = general_settings.get('clients', [])
        
        for client in clients:
            email = client.get('email')
            if not email or not client.get('id'): continue
            
            proxy = build_client_proxy(client, inbound, stream_settings, general_settings)
            if proxy:
                if email not in clients_proxies_map:
                    clients_proxies_map[email] = []
                clients_proxies_map[email].append(proxy)

    print(f"ℹ️ Found {len(clients_proxies_map)} unique clients across inbounds")

    # 4. Load Extra Servers (Dynamic Dict)
    providers_dict = load_extra_servers()

    # 5. Setup Template
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, 'templates')
    
    env = Environment(loader=FileSystemLoader(template_dir))
    env.filters['to_yaml'] = to_yaml_filter
    
    try:
        template = env.get_template(TEMPLATE_NAME)
    except Exception as e:
        print(f"❌ Template error ({TEMPLATE_NAME}): {e}")
        return

    # 6. Generate & Save
    generated_files_content = {}
    output_dir = os.path.join(base_dir, 'generated_configs')
    os.makedirs(output_dir, exist_ok=True)
    
    for email, panel_proxies in clients_proxies_map.items():
        # Render template passing dynamic lists
        raw_content = template.render(
            panel_proxies=panel_proxies,
            providers=providers_dict,
            rule_provider_url=RULE_PROVIDER_URL
        )
        config_content = strip_comments(raw_content)
        
        filename = f"{email}.yaml"
        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
            
        generated_files_content[filename] = {'content': config_content}
        print(f"📄 Generated: {filename}")

    # 7. Generate Index File
    if generated_files_content and GITHUB_USERNAME:
        index_lines = []
        
        # Sort filenames for better readability
        for filename in sorted(generated_files_content.keys()):
            # Construct raw URL
            # Format: https://gist.githubusercontent.com/USER/GIST_ID/raw/filename.yaml
            raw_url = f"https://gist.githubusercontent.com/{GITHUB_USERNAME}/{GIST_ID}/raw/{filename}"
            
            # Add to list
            index_lines.append(f"{filename}:")
            index_lines.append(f"{raw_url}")
            index_lines.append("") # Empty line separator

        index_filename = "0 Clash client config files.txt"
        generated_files_content[index_filename] = {'content': '\n'.join(index_lines)}
        print(f"📑 Index file generated: {index_filename}")

    # 8. Upload
    if generated_files_content:
        update_gist(generated_files_content)
    else:
        print("⚠️ No configs generated")

if __name__ == "__main__":
    main()