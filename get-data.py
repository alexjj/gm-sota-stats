import requests
import json
from datetime import datetime, UTC
from pathlib import Path
import time

BASE_URL = "https://api-db2.sota.org.uk"
API_URL = f"{BASE_URL}/api"
ASSOCIATION_CODE = "GM"
OUTPUT_FILE = Path("gm_sota_data.json")

# Be polite to the API
REQUEST_DELAY = 0.2  # seconds


def get_json(url):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


# ----------------------
# Fetch lookup data
# ----------------------

def fetch_activator_roll():
    """
    Returns a dict mapping UserID -> Callsign
    """
    print("Fetching activator roll...")
    url = f"{BASE_URL}/rolls/activator/-1/0/all/all"
    data = get_json(url)

    lookup = {}
    for entry in data:
        user_id = entry.get("UserID")
        callsign = entry.get("Callsign")
        if user_id is not None and callsign:
            lookup[user_id] = callsign

    print(f"Loaded {len(lookup)} activators into lookup table")
    return lookup


# ----------------------
# Fetch GW structure
# ----------------------

def fetch_regions():
    url = f"{API_URL}/associations/{ASSOCIATION_CODE}"
    data = get_json(url)
    return data["regions"]


def fetch_region_details(region_code):
    url = f"{API_URL}/regions/{ASSOCIATION_CODE}/{region_code}"
    return get_json(url)


def fetch_activations(summit_code):
    url = f"{API_URL}/activations/{summit_code}"
    return get_json(url)


def main():
    activator_lookup = fetch_activator_roll()

    print("Fetching GW regions...")
    regions = fetch_regions()

    output = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds") + "Z",
        "association": ASSOCIATION_CODE,
        "regions": {}
    }

    for region in regions:
        region_code = region["regionCode"]
        print(f"Processing region {region_code}...")

        region_data = fetch_region_details(region_code)

        region_entry = {
            "region": region_data["region"],
            "summits": {}
        }

        for summit in region_data["summits"]:
            summit_code = summit["summitCode"]
            print(f"  Fetching activations for {summit_code}...")

            try:
                activations = fetch_activations(summit_code)
            except Exception as e:
                print(f"    ERROR fetching {summit_code}: {e}")
                activations = []

            # Enrich activations with canonical Callsign
            enriched_activations = []
            for act in activations:
                user_id = act.get("userId")

                canonical_callsign = activator_lookup.get(user_id)

                # Fallback: strip /P or suffix from ownCallsign
                if not canonical_callsign and act.get("ownCallsign"):
                    canonical_callsign = act["ownCallsign"].split("/")[0]

                enriched = {
                    **act,
                    "Callsign": canonical_callsign
                }

                enriched_activations.append(enriched)

            region_entry["summits"][summit_code] = {
                "summit": summit,
                "activations": enriched_activations
            }

            time.sleep(REQUEST_DELAY)

        output["regions"][region_code] = region_entry

    print(f"Writing output to {OUTPUT_FILE}")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("Done.")


if __name__ == "__main__":
    main()
