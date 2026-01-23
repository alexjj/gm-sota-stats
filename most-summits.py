import json
import csv
from collections import defaultdict
from datetime import datetime

# ---------- CONFIG ----------
INPUT_FILE = "gm_sota_data.json"
OUTPUT_FILE = "sota_multi_summit_days.csv"
POINT_VALUES = [1, 2, 4, 6, 8, 10]
# ----------------------------


def load_data(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalise_date(date_str):
    """
    Convert '2025-08-17T00:00:00Z' -> '2025-08-17'
    """
    return datetime.fromisoformat(
        date_str.replace("Z", "+00:00")
    ).date().isoformat()


def main():
    data = load_data(INPUT_FILE)

    # (date, callsign) -> { summit_code: points }
    activations_by_day = defaultdict(dict)

    for region in data.get("regions", {}).values():
        for summit_code, summit_data in region.get("summits", {}).items():

            summit_points = summit_data["summit"]["points"]

            for act in summit_data.get("activations", []):
                date = normalise_date(act["activationDate"])
                callsign = act.get("Callsign") or act.get("ownCallsign")

                if not callsign:
                    continue

                key = (date, callsign)
                # Avoid double-counting the same summit
                activations_by_day[key][summit_code] = summit_points

    rows = []
    for (date, callsign), summits in activations_by_day.items():

        # Initialise point buckets
        point_counts = {p: 0 for p in POINT_VALUES}

        for pts in summits.values():
            if pts in point_counts:
                point_counts[pts] += 1

        total_points = sum(summits.values())

        row = {
            "date": date,
            "callsign": callsign,
            "number_of_summits": len(summits),
            "total_points": total_points,
            "summits": ", ".join(sorted(summits.keys()))
        }

        # Add point columns
        for p in POINT_VALUES:
            row[f"{p}pt"] = point_counts[p]

        rows.append(row)

    # Sort: most summits, then most points, then date
    rows.sort(
        key=lambda r: (
            -r["number_of_summits"],
            -r["total_points"],
            r["date"]
        )
    )

    # CSV field order
    fieldnames = (
        ["date", "callsign", "number_of_summits", "total_points"]
        + [f"{p}pt" for p in POINT_VALUES]
        + ["summits"]
    )

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written {len(rows)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
