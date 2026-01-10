import socket
import ssl

def check_domain_tls13(domain, port=443, timeout=3):
    """
    Checks if a domain supports TLS 1.3 and is reachable.
    Returns: True if successful, False otherwise.
    """
    try:
        # Create a default SSL context
        context = ssl.create_default_context()
        
        # We want to ensure it connects via TLS 1.3
        # Note: In modern Python, TLS 1.3 is enabled by default in default_context.
        # But we check the actual negotiated protocol version.
        
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                version = ssock.version()
                
                # Check if negotiated protocol is TLSv1.3
                if version == 'TLSv1.3':
                    return True
                else:
                    print(f"⚠️ {domain} uses {version}, not TLSv1.3")
                    return False
                    
    except socket.timeout:
        print(f"⚠️ {domain}: Connection timed out")
        return False
    except ssl.SSLError as e:
        print(f"⚠️ {domain}: SSL Error ({e})")
        return False
    except socket.gaierror:
        print(f"⚠️ {domain}: DNS resolution failed")
        return False
    except ConnectionRefusedError:
        print(f"⚠️ {domain}: Connection refused")
        return False
    except Exception as e:
        print(f"⚠️ {domain}: Error {e}")
        return False

# Self-test block
if __name__ == "__main__":
    test_domain = "www.google.com"
    print(f"Testing {test_domain}...")
    if check_domain_tls13(test_domain):
        print("✅ TLS 1.3 Supported!")
    else:
        print("❌ TLS 1.3 Failed.")