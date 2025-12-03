#!/usr/bin/env python3
"""
測試 FHIR 伺服器是否支援 SMART on FHIR Standalone Launch
"""
import requests
import json

FHIR_SERVER = "https://bf4f17fd8327.ngrok-free.app/fhir"

print("=" * 60)
print("FHIR 伺服器 SMART 支援測試")
print("=" * 60)
print(f"測試伺服器: {FHIR_SERVER}\n")

# 測試 1: .well-known/smart-configuration
print("[TEST 1] SMART Configuration Endpoint")
print("-" * 60)
try:
    url = f"{FHIR_SERVER}/.well-known/smart-configuration"
    response = requests.get(url, headers={'Accept': 'application/json'}, timeout=10)
    print(f"URL: {url}")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        config = response.json()
        print("[OK] Supports SMART Configuration!")
        print(f"\nAuthorization Endpoint: {config.get('authorization_endpoint', 'N/A')}")
        print(f"Token Endpoint: {config.get('token_endpoint', 'N/A')}")
        print(f"Capabilities: {config.get('capabilities', [])}")
        smart_supported = True
    else:
        print(f"[FAIL] Not supported (Status: {response.status_code})")
        smart_supported = False
except Exception as e:
    print(f"[ERROR] Request failed: {e}")
    smart_supported = False

print()

# 測試 2: Metadata (CapabilityStatement)
print("[TEST 2] CapabilityStatement (metadata)")
print("-" * 60)
try:
    url = f"{FHIR_SERVER}/metadata"
    response = requests.get(url, headers={'Accept': 'application/fhir+json'}, timeout=10)
    print(f"URL: {url}")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        capability = response.json()
        print(f"[OK] Got CapabilityStatement")
        print(f"FHIR Version: {capability.get('fhirVersion', 'N/A')}")
        print(f"Server: {capability.get('software', {}).get('name', 'N/A')} {capability.get('software', {}).get('version', '')}")
        
        # 檢查 SMART 擴展
        oauth_found = False
        for rest in capability.get('rest', []):
            security = rest.get('security', {})
            for extension in security.get('extension', []):
                if 'oauth-uris' in extension.get('url', ''):
                    oauth_found = True
                    print("\n[OK] Found OAuth URIs extension:")
                    for sub_ext in extension.get('extension', []):
                        url_type = sub_ext.get('url', '')
                        value = sub_ext.get('valueUri', '')
                        if url_type == 'authorize':
                            print(f"  Authorization: {value}")
                        elif url_type == 'token':
                            print(f"  Token: {value}")
        
        if not oauth_found:
            print("\n[FAIL] No OAuth URIs extension found")
            print("   This server may not support SMART on FHIR")
    else:
        print(f"[FAIL] Cannot get CapabilityStatement (Status: {response.status_code})")
except Exception as e:
    print(f"[ERROR] Request failed: {e}")

print()

# 測試 3: 嘗試獲取患者列表（檢查是否是公開伺服器）
print("[TEST 3] Check if Public FHIR Server")
print("-" * 60)
try:
    url = f"{FHIR_SERVER}/Patient?_count=1"
    response = requests.get(url, headers={'Accept': 'application/fhir+json'}, timeout=10)
    print(f"URL: {url}")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        bundle = response.json()
        total = bundle.get('total', 0)
        print(f"[OK] This is a PUBLIC FHIR server!")
        print(f"   Total patients: {total}")
        print(f"   You can use TEST MODE without OAuth")
    elif response.status_code == 401:
        print(f"[AUTH] Requires authorization (401 Unauthorized)")
        print(f"   This server requires OAuth")
    else:
        print(f"[INFO] Status code: {response.status_code}")
except Exception as e:
    print(f"[ERROR] Request failed: {e}")

print()
print("=" * 60)
print("測試總結")
print("=" * 60)

if smart_supported:
    print("[OK] Server supports SMART on FHIR")
    print("[OK] Can use Standalone Launch")
    print("\nRecommended Actions:")
    print("1. Ensure your Client ID is registered on this server")
    print("2. Set REDIRECT_URI=http://localhost:8080/callback")
    print("3. Visit http://localhost:8080/standalone to launch")
else:
    print("[FAIL] Server does NOT support SMART on FHIR")
    print("\nRecommended Actions:")
    print("1. Use TEST MODE to access directly (if public server)")
    print("2. Visit http://localhost:8080/test-patients")
    print("3. Select 'Custom Server' and enter:")
    print(f"   - Server URL: {FHIR_SERVER}")
    print("   - Patient ID: Check Swagger UI for available patient IDs")

print("=" * 60)

