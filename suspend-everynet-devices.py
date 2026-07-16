import argparse
import json
from pathlib import Path
from time import sleep

import pandas as pd
import requests

DEFAULT_CONFIG_FILE = Path(__file__).with_name("andorra.json")
REQUIRED_CONFIG_KEYS = (
    "fqdn",
    "username",
    "password",
    "suspend_list",
    "suspend_retries",
    "suspend_progress",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=str(DEFAULT_CONFIG_FILE),
        help="Path to the JSON config file",
    )
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    config_file = Path(config_path).resolve()
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    missing_keys = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
    if missing_keys:
        raise KeyError(f"Missing required config keys: {', '.join(missing_keys)}")

    config_dir = config_file.parent
    config["suspend_list"] = str((config_dir / config["suspend_list"]).resolve())
    config["suspend_progress"] = str((config_dir / config["suspend_progress"]).resolve())
    config["suspend_retries"] = int(config["suspend_retries"])
    return config


def get_last_index(progress_file: str) -> int:
    progress_file = Path(progress_file)
    if progress_file.exists():
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except ValueError:
            return 0
    return 0


def save_last_index(progress_file: str, index: int):
    with open(progress_file, "w", encoding="utf-8") as f:
        f.write(str(index))


def fetch_devices_from_csv(csv_path: str) -> list:
    """
    Fetch devices from a CSV file.
    
    Args:
        csv_path: Path to the CSV file containing DevEUI column
    
    Returns:
        List of device dev_eui strings
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    df = pd.read_csv(csv_file)
    
    # Extract DevEUI column
    if "DevEUI" not in df.columns:
        raise ValueError("CSV file must contain 'DevEUI' column")

    dev_eui_list = df["DevEUI"].dropna().astype(str).tolist()
    print(f"Total devices loaded from CSV: {len(dev_eui_list)}")
    return dev_eui_list


def login(session: requests.Session, fqdn: str, username: str, password: str) -> bool:
    """
    Login to the Everynet API and store the session cookie.
    
    Args:
        session: requests Session object to store cookies
        fqdn: Everynet hostname
        username: Login username
        password: Login password
    
    Returns:
        True if login successful, False otherwise
    """
    login_url = f"https://{fqdn}/api/v1.0/auth"
    payload = {
        "email": username,
        "password": password
    }
    
    response = session.post(login_url, json=payload)
    
    if response.status_code == 200 and "session_token" in session.cookies:
        print("Login successful!")
        return True
    else:
        print(f"Login failed! Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return False


def patch(
    session: requests.Session,
    fqdn: str,
    deveui: list,
    start_index: int,
    max_retries: int,
    progress_file: str,
):
    url = f"https://{fqdn}/api/v1.0/devices/"
    payload = {
        "block_uplink" : True
    }
    
    total_devices = len(deveui)
    a = start_index
    
    for dev in deveui[start_index:]:
        success = False
        for attempt in range(1, max_retries + 1):
            try:
                response = session.patch(url+dev, json=payload, timeout=10)
                
                if response.status_code == 200:
                    print(f"[{a}/{total_devices}] Patched device {dev} successfully.")
                    success = True
                    break
                else:
                    print(f"[{a}/{total_devices}] Failed to patch device {dev}. Status: {response.status_code}. Attempt {attempt}/{max_retries}")
                    sleep(2)  # wait before retry
            except requests.exceptions.RequestException as e:
                print(f"[{a}/{total_devices}] Request failed for device {dev}: {e}. Attempt {attempt}/{max_retries}")
                sleep(2)
                
        if not success:
            print(f"Failed to patch device {dev} after {max_retries} attempts. Stopping.")
            break
            
        a += 1
        save_last_index(progress_file, a)
        sleep(0.01)  # Sleep to avoid hitting rate limits




def main():
    args = parse_args()
    config = load_config(args.config)
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Step 1: Login
    print("=" * 50)
    print("Step 1: Logging in...")
    print("=" * 50)
    if not login(session, config["fqdn"], config["username"], config["password"]):
        print("Failed to login. Exiting.")
        return
    
    # Step 2: Load devices from CSV
    print("\n" + "=" * 50)
    print("Step 2: Loading devices from CSV...")
    print("=" * 50)
    devices = fetch_devices_from_csv(config["suspend_list"])
    
    # Step 3: Patch devices
    start_index = get_last_index(config["suspend_progress"])
    print("\n" + "=" * 50)
    print(f"Step 3: Patching devices starting from index {start_index}...")
    print("=" * 50)
    patch(
        session,
        config["fqdn"],
        devices,
        start_index,
        config["suspend_retries"],
        config["suspend_progress"],
    )
    
    

if __name__ == "__main__":
    main()
