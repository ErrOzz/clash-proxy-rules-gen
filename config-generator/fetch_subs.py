import os
import urllib.parse
import base64
import requests
import yaml
import json
from typing import Dict, Any
from logger import log

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

    # Base proxy configuration (Explicitly typed as Dict[str, Any] to satisfy VSCode)
    proxy: Dict[str, Any] = {
        'name': name,
        'type': 'vless',
        'server': host,
        'port': int(port),
        'uuid': uuid,
        'udp': True,
        'encryption': query.get('encryption', ['none'])[0]
    }

    if 'flow' in query:
        # Use direct key access since we already checked it exists
        proxy['flow'] = query['flow'][0]

    network = query.get('type', ['tcp'])[0]
    proxy['network'] = network

    # TLS and Reality mapping
    security = query.get('security', ['none'])[0]
    if security in ['tls', 'reality']:
        proxy['tls'] = True
        proxy['skip-cert-verify'] = True
        
        if 'sni' in query:
            proxy['servername'] = query['sni'][0]
            
        if 'fp' in query:
            proxy['client-fingerprint'] = query['fp'][0]
            
        if 'alpn' in query:
            alpn_raw = query['alpn'][0]
            proxy['alpn'] = alpn_raw.split(',') if ',' in alpn_raw else [alpn_raw]

    # Reality specific options
    if security == 'reality':
        reality_opts: Dict[str, Any] = {
            'support-x25519mlkem768': True
        }
        if 'pbk' in query:
            reality_opts['public-key'] = query['pbk'][0]
        if 'sid' in query:
            reality_opts['short-id'] = query['sid'][0]
            
        proxy['reality-opts'] = reality_opts

    # Transports mapping (ws, grpc, xhttp)
    if network == 'ws':
        ws_opts: Dict[str, Any] = {}
        if 'path' in query:
            ws_opts['path'] = urllib.parse.unquote(query['path'][0])
        if 'host' in query:
            ws_opts['headers'] = {'Host': urllib.parse.unquote(query['host'][0])}
        proxy['ws-opts'] = ws_opts
            
    elif network == 'grpc':
        grpc_opts: Dict[str, Any] = {}
        if 'serviceName' in query:
            grpc_opts['grpc-service-name'] = urllib.parse.unquote(query['serviceName'][0])
        proxy['grpc-opts'] = grpc_opts
            
    elif network == 'xhttp':
        xhttp_opts: Dict[str, Any] = {}
        if 'path' in query:
            xhttp_opts['path'] = urllib.parse.unquote(query['path'][0])
        if 'host' in query:
            xhttp_opts['headers'] = {'Host': urllib.parse.unquote(query['host'][0])}
        if 'mode' in query:
            xhttp_opts['mode'] = urllib.parse.unquote(query['mode'][0])
        proxy['xhttp-opts'] = xhttp_opts

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
        log(f"⚠️ Error fetching {url}: {e}")
        return []

def update_extra_servers():
    """
    Reads providers.yaml, fetches all subscriptions dynamically.
    If a provider fails, falls back to existing nodes.
    Saves to extra_servers.yaml only if there are technical changes.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    providers_file = os.path.join(base_dir, '.providers.yaml')
    output_file = os.path.join(base_dir, 'extra_servers.yaml')

    if not os.path.exists(providers_file):
        return False

    # 1. Load existing extra_servers.yaml if it exists for fallback purposes
    existing_servers = {}
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_servers = yaml.safe_load(f) or {}
        except Exception:
            pass

    with open(providers_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    providers_config = config.get('providers', {})
    extra_servers = {}

    for provider_name, settings in providers_config.items():
        is_base64 = settings.get('type') == 'base64'
        urls = settings.get('urls', [])
        provider_proxies = []
        
        for url in urls:
            nodes = fetch_and_parse(url, is_base64=is_base64, prefix=provider_name)
            if nodes:
                provider_proxies.extend(nodes)
                
        # 2. Fallback logic: if nothing was downloaded, use existing nodes
        if provider_proxies:
            extra_servers[provider_name] = provider_proxies
        else:
            if provider_name in existing_servers:
                extra_servers[provider_name] = existing_servers[provider_name]
                log(f"⚠️ Provider [{provider_name}] fetch failed. Using previous nodes.")

    # 3. Smart comparison
    def get_hashable_state(servers_dict):
        state = {}
        for provider, proxies in servers_dict.items():
            cleaned_proxies = []
            for p in proxies:
                p_copy = p.copy()
                p_copy.pop('name', None)
                servername = p_copy.get('servername')
                if servername and isinstance(servername, str):
                    parts = servername.split('.')
                    if len(parts) > 2 and not all(part.isdigit() for part in parts):
                        p_copy['servername'] = '.'.join(parts[1:])
                if 'reality-opts' in p_copy and isinstance(p_copy['reality-opts'], dict):
                    opts_copy = p_copy['reality-opts'].copy()
                    opts_copy.pop('short-id', None)
                    p_copy['reality-opts'] = opts_copy
                cleaned_proxies.append(json.dumps(p_copy, sort_keys=True))
            state[provider] = sorted(cleaned_proxies)
        return state

    if get_hashable_state(extra_servers) == get_hashable_state(existing_servers):
        return False

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(extra_servers, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        log(f"❌ Failed to save extra_servers.yaml: {e}")
        return False

if __name__ == "__main__":
    update_extra_servers()