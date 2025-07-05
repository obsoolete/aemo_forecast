"""Constants for the AEMO Forecast integration."""

DOMAIN = "aemo_forecast"

CONF_STATE_ID = "state_id"

# Number keys
THRESHOLD_PRICE = "thresholdPrice"  # Threshold price in $/kWh

# Sensor keys
SPIKE_WINDOWS = "spike_windows"
ABOVE_THRESHOLD_DURATION = "above_threshold_duration"
TOTAL_FORECAST_DURATION = "total_forecast_duration"
NEXT_SPIKE_WINDOW = "next_spike_window"
NEXT_SPIKE_WINDOW_PRICE = "next_spike_window_price"
MAX_PRICE = "max_price"
MAX_PRICE_TIME = "max_price_time"
MIN_PRICE = "min_price"
MIN_PRICE_TIME = "min_price_time"
