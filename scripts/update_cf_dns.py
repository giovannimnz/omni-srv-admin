import os, json, urllib.request

env = {}
with open("/tmp/cf_env") as f:
    for line in f:
        if line.startswith("export ") and "=" in line:
            k, v = line[7:].strip().split("=", 1)
            env[k] = v.strip("\"'")

ip_map = {
    "137.131.190.161": "64.181.172.236",
    "129.148.47.32":   "163.176.55.228",
    "136.248.126.12":  "150.230.71.10",
    "147.15.40.118":   "168.138.136.251"
}

headers = {
    "X-Auth-Email": env.get("CF_AUTH_EMAIL"),
    "X-Auth-Key": env.get("CF_GLOBAL_API_KEY"),
    "Content-Type": "application/json"
}

zone_id = env.get("CF_ZONE_ID_ATIUS")

url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=A&per_page=100"
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as resp:
        records = json.loads(resp.read().decode())["result"]
except Exception as e:
    print("Cloudflare GET error:", e)
    records = []

print(f"Total A records in zone: {len(records)}")
for r in records:
    old_ip = r["content"]
    if old_ip in ip_map:
        new_ip = ip_map[old_ip]
        print(f"Updating {r['name']} ({r['id']}): {old_ip} -> {new_ip} (proxied: {r['proxied']})")
        update_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{r['id']}"
        update_data = json.dumps({
            "type": "A",
            "name": r["name"],
            "content": new_ip,
            "ttl": r["ttl"],
            "proxied": r["proxied"]
        }).encode()
        up_req = urllib.request.Request(update_url, data=update_data, headers=headers, method="PATCH")
        try:
            with urllib.request.urlopen(up_req) as up_resp:
                res = json.loads(up_resp.read().decode())
                print(f"  -> Success: {res.get('success')}")
        except Exception as e:
            print(f"  -> Error updating {r['name']}: {e}")

if os.path.exists("/tmp/cf_env"):
    os.remove("/tmp/cf_env")
