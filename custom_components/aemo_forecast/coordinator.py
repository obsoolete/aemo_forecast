"""Coordinator for AEMO Forecast integration."""

import logging
from typing import Any
from datetime import datetime, timedelta, timezone
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

# NEM time is always AEST (UTC+10), with no daylight saving
NEM_TZ = timezone(timedelta(hours=10))


CONFIG_URL = "https://dashboards.public.aemo.com.au/config.json"
PRICE_URL = "https://dashboards.public.aemo.com.au/NEM/v1/PWS/NEMDashboard/priceAndDemand"


def _parse_nem_time(value: str) -> datetime:
    """Parse an AEMO timestamp, assuming fixed UTC+10 when no offset is given."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=NEM_TZ)
    return parsed

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
        self._api_key: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="AEMO Forecast Data",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_fetch_api_key(self) -> str:
        """Fetch the public x-api-key used by the AEMO dashboard."""
        session = async_get_clientsession(self.hass)
        async with session.get(CONFIG_URL) as response:
            response.raise_for_status()
            config: Any = await response.json(content_type=None)

        key = config.get("xApiKey") if isinstance(config, dict) else None
        if not key:
            raise UpdateFailed("AEMO config did not contain an API key")
        return key

    async def _async_fetch_prices(self, api_key: str) -> tuple[int, Any]:
        """Request price data, returning the HTTP status and parsed body."""
        session = async_get_clientsession(self.hass)
        async with session.get(
            PRICE_URL,
            params={"timescale": "30MIN"},
            headers={"x-api-key": api_key},
        ) as response:
            if response.status in (401, 403):
                return response.status, None
            response.raise_for_status()
            return response.status, await response.json(content_type=None)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API endpoint."""

        try:
            if self._api_key is None:
                self._api_key = await self._async_fetch_api_key()

            status, data = await self._async_fetch_prices(self._api_key)
            if status in (401, 403):
                # Key may have been rotated; refresh once and retry
                self._api_key = await self._async_fetch_api_key()
                status, data = await self._async_fetch_prices(self._api_key)
                if status in (401, 403):
                    self._api_key = None
                    raise UpdateFailed(f"AEMO API rejected the API key (HTTP {status})")
        except aiohttp.ClientError as e:
            _LOGGER.error("Failed to fetch data: %s", str(e))
            raise UpdateFailed(f"Error communicating with API: {e}") from e

        entries = (data or {}).get("data", {}).get("items")
        if not entries:
            _LOGGER.warning("No data received")
            raise UpdateFailed("No data received")

        region = f"{self.state_id}1"
        filtered = [
            entry for entry in entries
            if entry.get("regionId") == region and entry.get("periodType") == "FORECAST"
        ]

        time_rrp_array = [
            {
                "time": _parse_nem_time(entry["settlementDate"]).isoformat(),
                "rrp": entry["rrp"] / 1000.0  # Convert from $/MWh to $/kWh
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