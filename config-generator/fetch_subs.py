import os
import urllib.parse
import base64
import requests
import yaml

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
    Universal parser for vless:// URLs mapping Xray parameters to Clash Meta config.
    Supports TLS, Reality, ws, grpc, and xhttp.
    """
    url = url.strip()
    if not url.startswith("vless://"):
        return None

    url = url[8:]
    
    name = fallback_name
    if '#' in url:
        url, encoded_name = url.split('#', 1)
        name = urllib.parse.unquote(encoded_name).strip()

    if '@' not in url:
        return None
    uuid, host_and_params = url.split('@', 1)

    if '?' not in host_and_params:
        host_port = host_and_params
        params_str = ""
    else:
        host_port, params_str = host_and_params.split('?', 1)

    host, port = host_port.split(':', 1)
    query = urllib.parse.parse_qs(params_str)

    # Base proxy configuration
    proxy = {
        'name': name,
        'type': 'vless',
        'server': host,
        'port': int(port),
        'uuid': uuid,
        'udp': True,
        'encryption': query.get('encryption', ['none'])[0]
    }

    if 'flow' in query:
        proxy['flow'] = query.get('flow')[0]

    network = query.get('type', ['tcp'])[0]
    proxy['network'] = network

    # TLS and Reality mapping
    security = query.get('security', ['none'])[0]
    if security in ['tls', 'reality']:
        proxy['tls'] = True
        proxy['skip-cert-verify'] = True
        
        if 'sni' in query:
            proxy['servername'] = query.get('sni')[0]
            
        if 'fp' in query:
            proxy['client-fingerprint'] = query.get('fp')[0]
            
        if 'alpn' in query:
            alpn_raw = query.get('alpn')[0]
            proxy['alpn'] = alpn_raw.split(',') if ',' in alpn_raw else [alpn_raw]

    # Reality specific options
    if security == 'reality':
        proxy['reality-opts'] = {}
        if 'pbk' in query:
            proxy['reality-opts']['public-key'] = query.get('pbk')[0]
        if 'sid' in query:
            proxy['reality-opts']['short-id'] = query.get('sid')[0]

    # Transports mapping (ws, grpc, xhttp)
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
            
    elif network == 'xhttp':
        proxy['xhttp-opts'] = {}
        if 'path' in query:
            proxy['xhttp-opts']['path'] = urllib.parse.unquote(query.get('path')[0])
        if 'host' in query:
            proxy['xhttp-opts']['headers'] = {'Host': urllib.parse.unquote(query.get('host')[0])}
        if 'mode' in query:
            proxy['xhttp-opts']['mode'] = urllib.parse.unquote(query.get('mode')[0])

    return proxy

def fetch_and_parse(url, is_base64=False, prefix="Node"):
    """
    Fetches subscription from HTTP/HTTPS URL and parses proxies.
    """
    if not url:
        return []
        
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_text = response.text

        if is_base64:
            raw_text = decode_base64_subs(raw_text)

        proxies = []
        lines = raw_text.splitlines()
        
        # Used for numbering anonymous nodes
        idx = 1 
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            proxy_conf = parse_vless_url(line, fallback_name=f"{prefix} {idx}")
            if proxy_conf:
                proxies.append(proxy_conf)
                idx += 1
                
        return proxies
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return []

def update_extra_servers():
    """
    Reads providers.yaml, fetches all subscriptions dynamically, 
    and saves them to extra_servers.yaml grouped by provider.
    """
    print("🔄 Fetching external subscriptions from providers.yaml...")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    providers_file = os.path.join(base_dir, '.providers.yaml')
    output_file = os.path.join(base_dir, 'extra_servers.yaml')

    if not os.path.exists(providers_file):
        print("⚠️ providers.yaml not found. Skipping external subs.")
        return

    with open(providers_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    providers_config = config.get('providers', {})
    extra_servers = {}

    for provider_name, settings in providers_config.items():
        is_base64 = settings.get('type') == 'base64'
        urls = settings.get('urls', [])
        
        provider_proxies = []
        print(f"📥 Fetching nodes for provider: {provider_name}...")
        
        for url in urls:
            nodes = fetch_and_parse(url, is_base64=is_base64, prefix=provider_name)
            if nodes:
                provider_proxies.extend(nodes)
                
        if provider_proxies:
            extra_servers[provider_name] = provider_proxies
            print(f"✅ Loaded {len(provider_proxies)} nodes for {provider_name}.")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(extra_servers, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print("✅ extra_servers.yaml updated successfully.")
    except Exception as e:
        print(f"❌ Failed to save extra_servers.yaml: {e}")

if __name__ == "__main__":
    update_extra_servers()