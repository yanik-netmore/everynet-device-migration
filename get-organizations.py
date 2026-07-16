#!/usr/bin/env python3

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

LIMIT = 300
OUTPUT_PATTERN = "organizations-{index:02d}.json"
AGGREGATE_OUTPUT = "organizations.json"


def build_headers(fqdn: str) -> dict:
    return {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": f"https://{fqdn}/organizations",
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


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as fp:
        return json.load(fp)


def login(fqdn: str, email: str, password: str) -> str:
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
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        data = json.loads(response.read().decode(charset))
    access_token = data.get("access_token")
    if not access_token:
        raise ValueError("Login response did not contain an access_token.")
    print(f"Logged in as {data.get('email')} (token: {access_token[:12]}...)")
    return access_token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Everynet organizations pages in batches."
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Path to config JSON file (must contain fqdn, username, password).",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output JSON files.",
    )
    parser.add_argument(
        "--start-offset",
        type=int,
        default=0,
        help="Starting offset. Defaults to 0.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=LIMIT,
        help="Batch size. Defaults to 300.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional hard limit for fetched pages.",
    )
    return parser.parse_args()


def build_request(base_url: str, offset: int, limit: int, access_token: str, fqdn: str) -> urllib.request.Request:
    params = urllib.parse.urlencode({"offset": offset, "limit": limit, "access_token": access_token})
    headers = build_headers(fqdn)
    return urllib.request.Request(f"{base_url}?{params}", headers=headers)


def fetch_json(request: urllib.request.Request) -> Any:
    with urllib.request.urlopen(request) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        #print(response.read().decode(charset))
        return json.loads(response.read().decode(charset))


def batch_size(payload: Any) -> int | None:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("results", "items", "connections", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
    return None


def write_payload(output_dir: Path, index: int, payload: Any) -> Path:
    path = output_dir / OUTPUT_PATTERN.format(index=index)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def extract_organizations(payload: Any) -> list[Any]:
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object payload.")
    gateways = payload.get("organizations")
    if not isinstance(gateways, list):
        raise ValueError("Expected payload['gateways'] to be a list.")
    return gateways


def write_aggregate(output_dir: Path, gateways: list[Any]) -> Path:
    path = output_dir / AGGREGATE_OUTPUT
    path.write_text(json.dumps(gateways, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()

    config = load_config(args.config)
    fqdn = config.get("fqdn")
    username = config.get("username")
    password = config.get("password")
    if not fqdn or not username or not password:
        print("Config must contain 'fqdn', 'username', and 'password'.", file=sys.stderr)
        return 2

    base_url = f"https://{fqdn}/api/v1.0/organizations"

    try:
        access_token = login(fqdn, username, password)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_gateways: list[Any] = []
    page_index = 1
    offset = args.start_offset

    while True:
        if args.max_pages is not None and page_index > args.max_pages:
            break

        print(f"offset: {offset} limit: {args.limit}")
        request = build_request(base_url=base_url, offset=offset, limit=args.limit, access_token=access_token, fqdn=fqdn)
        try:
            payload = fetch_json(request)
        except urllib.error.HTTPError as exc:
            print(f"HTTP error for offset {offset}: {exc.code} {exc.reason}", file=sys.stderr)
            return 1
        except urllib.error.URLError as exc:
            print(f"Request failed for offset {offset}: {exc.reason}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON for offset {offset}: {exc}", file=sys.stderr)
            return 1

        count = batch_size(payload)
        if count == 0:
            print("Break")
            break

        path = write_payload(output_dir, page_index, payload)
        try:
            all_gateways.extend(extract_organizations(payload))
        except ValueError as exc:
            print(f"Invalid payload for offset {offset}: {exc}", file=sys.stderr)
            return 1
        print(f"Saved {path} (offset={offset})")

        if count is None or count < args.limit:
            break

        offset += args.limit
        page_index += 1

    aggregate_path = write_aggregate(output_dir, all_gateways)
    print(f"Saved {aggregate_path} ({len(all_gateways)} organizations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
