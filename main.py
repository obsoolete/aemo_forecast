import requests
import csv
from datetime import datetime, timedelta

url = "https://visualisations.aemo.com.au/aemo/apps/api/report/5MIN"

payload = {
    "timeScale": ["30MIN"]
}

try:
    # Make the POST request
    response = requests.post(url, json=payload)
    response.raise_for_status()  # Raise error if status not 2xx

    data = response.json()  # Parse JSON response

    # Extract the "5MIN" array from the response
    entries = data.get("5MIN", [])

    # Filter entries: REGION == "NSW1" AND PERIODTYPE == "FORECAST"
    filtered = [
        entry for entry in entries
        if entry.get("REGION") == "NSW1" and entry.get("PERIODTYPE") == "FORECAST"
    ]

    # Build array of dictionaries with SETTLEMENTDATE and RRP converted to $/kWh
    time_rrp_array = [
        {
            "time": entry["SETTLEMENTDATE"],
            "rrp": entry["RRP"] / 1000.0  # Convert from $/MWh to $/kWh
        }
        for entry in filtered
    ]

    # Save to CSV
    csv_filename = "time_rrp_data.csv"

    with open(csv_filename, mode="w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["time", "rrp"])
        writer.writeheader()
        writer.writerows(time_rrp_array)

    print(f"Saved {len(time_rrp_array)} forecast points to {csv_filename}")

    # --------------------------------------------
    # Compute key stats
    # --------------------------------------------
    threshold = 1.0  # Threshold in $/kWh

    if not time_rrp_array:
        print("No forecast data available to compute statistics.")
    else:
        times = [datetime.fromisoformat(item["time"]) for item in time_rrp_array]
        forecast_start = min(times)
        forecast_end = max(times)

        if len(times) > 1:
            forecast_length = forecast_end - forecast_start
            forecast_length_hours = forecast_length.total_seconds() / 3600
            print(f"\nForecast starts at: {forecast_start}")
            print(f"Forecast ends at:   {forecast_end}")
            print(f"Forecast period length: {forecast_length} ({forecast_length_hours:.2f} hours)")
        else:
            print("\nForecast period length: Only one forecast point; no duration to calculate.")

        # Find first time RRP exceeds threshold
        first_above_threshold = None
        for item in time_rrp_array:
            if item["rrp"] > threshold:
                first_above_threshold = item["time"]
                break

        if first_above_threshold:
            print(f"First time RRP > ${threshold:.3f}/kWh: {first_above_threshold}")
        else:
            print(f"RRP never exceeds ${threshold:.3f}/kWh in the forecast period.")

        # Count periods RRP > threshold
        periods_above_threshold = sum(1 for item in time_rrp_array if item["rrp"] > threshold)
        total_time_above_threshold = timedelta(minutes=periods_above_threshold * 30)
        total_time_above_hours = total_time_above_threshold.total_seconds() / 3600

        print(f"Total time above ${threshold:.3f}/kWh threshold: {total_time_above_threshold} ({total_time_above_hours:.2f} hours, {periods_above_threshold} periods of 30 minutes)")

except requests.RequestException as e:
    print(f"Request failed: {e}")

except ValueError as e:
    print(f"Failed to parse JSON: {e}")

except IOError as e:
    print(f"Failed to write CSV file: {e}")
