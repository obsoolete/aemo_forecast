"""Coordinator for AEMO Forecast integration."""

import datetime
import logging
import json
from typing import Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.config_entries import ConfigEntry

import aiohttp

from .const import CONF_STATE_ID, SPIKE_WINDOWS, ABOVE_THRESHOLD_DURATION, NEXT_SPIKE_WINDOW, NEXT_SPIKE_WINDOW_PRICE, TOTAL_FORECAST_DURATION, MAX_PRICE, MAX_PRICE_TIME, MIN_PRICE, MIN_PRICE_TIME, THRESHOLD_PRICE

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)  # Update every 5 minutes

class AEMOForecastDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to manage fetching data from AEMOForecast API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry

        self.state_id = config_entry.data[CONF_STATE_ID]
        
        # Initialize attributes for storing number data
        self.numbers: dict[str, float] = {}
        self.numbers[THRESHOLD_PRICE] = config_entry.options.get(THRESHOLD_PRICE, 1.0)
        
        self.data: dict[str, Any] = {}


        super().__init__(
            hass,
            _LOGGER,
            name="AEMO Forecast Data",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API endpoint."""
        
        url: str = "https://visualisations.aemo.com.au/aemo/apps/api/report/5MIN"
        payload : dict[str, list[str]] = {"timeScale": ["30MIN"]}

        try:
            session = async_get_clientsession(self.hass)
            async with session.post(url, data=json.dumps(payload)) as response:
                if response.status == 401:
                    _LOGGER.critical("Unauthorized access")
                    raise UpdateFailed("Unauthorized access")
                elif response.status == 403:
                    _LOGGER.critical("Forbidden")
                    raise UpdateFailed("Forbidden")

                response.raise_for_status()
                data: Any = await response.json()
                
                # Check if the response contains a key called "5MIN"
                if "5MIN" not in data:
                    _LOGGER.warning("No data received")
                    raise UpdateFailed("No data received")               
        
        
        except aiohttp.ClientError as e:
            _LOGGER.error("Failed to fetch data: %s", str(e))
            raise UpdateFailed(f"Error communicating with API: {e}") from e

        # Process data
        # Extract the "5MIN" array from the response
        entries = data.get("5MIN", [])

        # Filter entries: REGION == "NSW1" AND PERIODTYPE == "FORECAST"
        filtered = [
            entry for entry in entries
            if entry.get("REGION") == f"{self.state_id}1" and entry.get("PERIODTYPE") == "FORECAST"
        ]

        # Build array of dictionaries with SETTLEMENTDATE and RRP converted to $/kWh
        time_rrp_array = [
            {
                "time": entry["SETTLEMENTDATE"],
                "rrp": entry["RRP"] / 1000.0  # Convert from $/MWh to $/kWh
            }
            for entry in filtered
        ]

        self.data = {}
        self.data["time_rrp_array"] = time_rrp_array

        # --------------------------------------------
        # Compute key stats
        # --------------------------------------------
        if THRESHOLD_PRICE not in self.numbers:
            _LOGGER.warning("Threshold price not set, using default value of 1.0 $/kWh")
            self.numbers[THRESHOLD_PRICE] = 1.0

        threshold = self.numbers[THRESHOLD_PRICE]  # Threshold in $/kWh

        if not time_rrp_array:
            _LOGGER.warning("No forecast data available to compute statistics.")
            raise UpdateFailed("No forecast data available")
        else:
            times = [datetime.fromisoformat(item["time"]) for item in time_rrp_array]
            self.data["forecast_start"] = min(times)
            self.data["forecast_end"] = max(times)

            # Determine total forecast duration
            if len(times) > 1:
                self.data[TOTAL_FORECAST_DURATION] = (self.data["forecast_end"] - self.data["forecast_start"]).total_seconds() / 60 # Duration in minutes
            else:
                _LOGGER.warning("Only one time entry found in forecast data.")

            # Find first time RRP exceeds threshold
            self.data[NEXT_SPIKE_WINDOW] = None
            self.data[NEXT_SPIKE_WINDOW_PRICE] = None
            for item in time_rrp_array:
                if item["rrp"] > threshold:
                    time = datetime.fromisoformat(item["time"])
                    time_with_timezone = time.astimezone(ZoneInfo("Australia/Sydney"))
                    self.data[NEXT_SPIKE_WINDOW] = time_with_timezone
                    self.data[NEXT_SPIKE_WINDOW_PRICE] = item["rrp"]
                    break
            
            # Determine the maximum price in the forecast
            max_rrp = max(time_rrp_array, key=lambda x: x["rrp"], default=None)
            if not max_rrp:
                _LOGGER.warning("No maximum price found in forecast data.")
                raise UpdateFailed("No maximum price found in forecast data")

            # Determine the minimum price in the forecast
            min_rrp = min(time_rrp_array, key=lambda x: x["rrp"], default=None)
            if not min_rrp:
                _LOGGER.warning("No minimum price found in forecast data.")
                raise UpdateFailed("No minimum price found in forecast data")
            
            self.data[MAX_PRICE] = max_rrp["rrp"]
            self.data[MAX_PRICE_TIME] = max_rrp["time"]
            self.data[MIN_PRICE] = min_rrp["rrp"]
            self.data[MIN_PRICE_TIME] = min_rrp["time"]

            # Count periods RRP > threshold
            self.data[SPIKE_WINDOWS] = sum(1 for item in time_rrp_array if item["rrp"] > threshold)
            self.data[ABOVE_THRESHOLD_DURATION] = self.data[SPIKE_WINDOWS] * 30 # Duration in minutes

        self.lastUpdate = datetime.now()

        # Return self.data to comply with DataUpdateCoordinator requirements
        return self.data