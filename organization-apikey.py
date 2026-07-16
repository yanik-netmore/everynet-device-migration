#!/usr/bin/env python3

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create an API key for an Everynet organization."
    )
    parser.add_argument("-c", "--config", required=True,
                        help="Path to config JSON (must contain fqdn, username, password).")
    parser.add_argument("--org", required=True,
                        help="Organization ID to create the key for.")
    parser.add_argument("--user_id", required=True,
                        help="User ID to associate with the key.")
    parser.add_argument("--name", required=True,
                        help="Name for the key; stored as 'MIGRATION: <name>'.")
    return parser.parse_args()


def load_config(path):
    with open(path, "r") as fp:
        return json.load(fp)


def login(fqdn, email, password):
    url = f"https://{fqdn}/api/v1.0/auth"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": f"https://{fqdn}",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": f"https://{fqdn}/login",
        "sec-ch-ua": '"Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        ),
    }
    body = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode(resp.headers.get_content_charset() or "utf-8"))
    token = data.get("access_token")
    if not token:
        raise ValueError("Login response did not contain an access_token.")
    return token


def create_key(fqdn, access_token, org, user_id, description):
    url = f"https://{fqdn}/api/v1.0/keys"
    payload = {
        "description": description,
        "user_id": user_id,
        "permissions": {
            "devices":      {"*": ["read", "create", "update", "delete"]},
            "gateways":     {"*": []},
            "filters":      {"*": ["read", "create", "update", "delete"]},
            "users":        {"*": ["read", "create", "update", "delete"]},
            "keys":         {"*": ["read", "create", "update", "delete"]},
            "applications": {"*": []},
            "connections":  {"*": ["read", "delete"]},
        },
        "org": org,
    }
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "cookie": f"session_token={access_token}",
        "origin": f"https://{fqdn}",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": f"https://{fqdn}/keys/new",
        "sec-ch-ua": '"Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        ),
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode(resp.headers.get_content_charset() or "utf-8"))


def main():
    args = parse_args()

    config = load_config(args.config)
    fqdn = config.get("fqdn")
    username = config.get("username")
    password = config.get("password")
    if not fqdn or not username or not password:
        print("Config must contain 'fqdn', 'username', and 'password'.", file=sys.stderr)
        return 2

    try:
        access_token = login(fqdn, username, password)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1

    try:
        result = create_key(fqdn, access_token, args.org, args.user_id, f"MIGRATION2: {args.name}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} {exc.reason}: {body}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, ValueError) as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    key = result.get("key", {})
    print(f"KeyID : {key.get('id', '')}")
    print(f"UserID: {key.get('user_id', '')}")
    print(f"OrgID : {key.get('org', '')}")
    print(f"Token : {key.get('access_token', '')}")
    print()
    snippet = {
        "orgID": key.get("org", ""),
        "name": args.name,
        "keyID": key.get("id", ""),
        "apiToken": key.get("access_token", ""),
    }
    # ~ print(json.dumps(snippet) + ",")
    print(json.dumps(snippet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
