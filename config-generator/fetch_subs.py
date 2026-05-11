import os
import urllib.parse
import base64
import requests
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUB_SINGLE_URL = os.getenv("SUB_SINGLE_URL")
SUB_MULTI_URL = os.getenv("SUB_MULTI_URL")
PROVIDER_SINGLE_NAME = os.getenv("PROVIDER_SINGLE_NAME", "Single")
PROVIDER_MULTI_NAME = os.getenv("PROVIDER_MULTI_NAME", "Multi")

def decode_base64_subs(encoded_text):
    """
    Decodes Base64 subscription data, handling missing padding.
    """
    encoded_text = encoded_text.strip()
    padding = len(encoded_text) % 4
    if padding:
        encoded_text += "=" * (4 - padding)
    try:
        return base64.b64decode(encoded_text).decode('utf-8')
    except Exception as e:
        print(f"❌ Base64 decode error: {e}")
        return ""

def parse_vless_url(url, fallback_name="Proxy"):
    """
    Parses a vless:// URL into a Clash proxy dictionary.
    """
    url = url.strip()
    if not url.startswith("vless://"):
        return None

    # Strip scheme
    url = url[8:]
    
    # Extract remark/name
    name = fallback_name
    if '#' in url:
        url, encoded_name = url.split('#', 1)
        name = urllib.parse.unquote(encoded_name).strip()

    # Extract auth and host:port
    if '@' not in url:
        return None
    uuid, host_and_params = url.split('@', 1)

    # Extract query parameters
    if '?' not in host_and_params:
        host_port = host_and_params
        params_str = ""
    else:
        host_port, params_str = host_and_params.split('?', 1)

    host, port = host_port.split(':', 1)
    query = urllib.parse.parse_qs(params_str)

    # Build proxy dict
    proxy = {
        'name': name,
        'type': 'vless',
        'server': host,
        'port': int(port),
        'uuid': uuid,
        'udp': True
    }

    # Handle network
    network = query.get('type', ['tcp'])[0]
    proxy['network'] = network

    # Handle security (TLS / Reality)
    security = query.get('security', ['none'])[0]
    if security in ['tls', 'reality']:
        proxy['tls'] = True
        
        if 'sni' in query:
            proxy['servername'] = query.get('sni')[0]
            
        if 'alpn' in query:
            alpn_raw = query.get('alpn')[0]
            proxy['alpn'] = alpn_raw.split(',') if ',' in alpn_raw else [alpn_raw]
            
        if 'fp' in query:
            proxy['client-fingerprint'] = query.get('fp')[0]
            
        proxy['skip-cert-verify'] = True

    # Handle Reality specifics
    if security == 'reality':
        proxy['reality-opts'] = {}
        if 'pbk' in query:
            proxy['reality-opts']['public-key'] = query.get('pbk')[0]
        if 'sid' in query:
            proxy['reality-opts']['short-id'] = query.get('sid')[0]

    # Handle Network specific options (ws, grpc)
    if network == 'ws':
        proxy['ws-opts'] = {}
        if 'path' in query:
            proxy['ws-opts']['path'] = urllib.parse.unquote(query.get('path')[0])
        if 'host' in query:
            proxy['ws-opts']['headers'] = {'Host': urllib.parse.unquote(query.get('host')[0])}
    elif network == 'grpc':
        proxy['grpc-opts'] = {}
        if 'serviceName' in query:
            proxy['grpc-opts']['grpc-service-name'] = urllib.parse.unquote(query.get('serviceName')[0])

    return proxy

def fetch_and_parse(url, is_base64=False, prefix="Node"):
    """
    Fetches subscription from URL and parses proxies.
    """
    if not url:
        return[]
        
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_text = response.text

        if is_base64:
            raw_text = decode_base64_subs(raw_text)

        proxies =[]
        lines = raw_text.splitlines()
        
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            proxy_conf = parse_vless_url(line, fallback_name=f"{prefix} {idx + 1}")
            if proxy_conf:
                proxies.append(proxy_conf)
                
        return proxies
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return[]
    
def main():
    print("🔄 Fetching external subscriptions...")
    
    extra_servers = {
        'single_node': [],
        'multi_nodes':[]
    }

    # Fetch Single Node
    if SUB_SINGLE_URL:
        print(f"📥 Fetching {PROVIDER_SINGLE_NAME} nodes...")
        single_proxies = fetch_and_parse(SUB_SINGLE_URL, is_base64=False, prefix=PROVIDER_SINGLE_NAME)
        if single_proxies:
            extra_servers['single_node'] = single_proxies
            print(f"✅ Loaded {len(single_proxies)} {PROVIDER_SINGLE_NAME} nodes.")

    # Fetch Multi Nodes
    if SUB_MULTI_URL:
        print(f"📥 Fetching {PROVIDER_MULTI_NAME} nodes...")
        multi_proxies = fetch_and_parse(SUB_MULTI_URL, is_base64=True, prefix=PROVIDER_MULTI_NAME)
        if multi_proxies:
            extra_servers['multi_nodes'] = multi_proxies
            print(f"✅ Loaded {len(multi_proxies)} {PROVIDER_MULTI_NAME} nodes.")

    # Save to extra_servers.yaml
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(base_dir, 'extra_servers.yaml')
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(extra_servers, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print("✅ extra_servers.yaml updated successfully.")
    except Exception as e:
        print(f"❌ Failed to save extra_servers.yaml: {e}")

if __name__ == "__main__":
    main()