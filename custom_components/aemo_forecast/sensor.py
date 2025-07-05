
"""Platform for AEMO Forecast sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfTime
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SPIKE_WINDOWS, ABOVE_THRESHOLD_DURATION, NEXT_SPIKE_WINDOW, NEXT_SPIKE_WINDOW_PRICE, TOTAL_FORECAST_DURATION, MAX_PRICE, MAX_PRICE_TIME, MIN_PRICE, MIN_PRICE_TIME

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AEMOForecastDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AEMO Forecast sensors from a config entry."""

    coordinator = hass.data[DOMAIN]['coordinator']

    async_add_entities(
        [

            AEMOForecastSpikeWindowsSensor(coordinator),
            AEMOForecastAboveThresholdDurationSensor(coordinator),
            AEMOForecastNextSpikeWindowSensor(coordinator),
            AEMOForecastTotalForecastDurationSensor(coordinator),
            AEMOForecastMaxPriceSensor(coordinator),
            AEMOForecastMinPriceSensor(coordinator),
        ]
    )

class AEMOForecastSensor(CoordinatorEntity, SensorEntity):
    """Representation of a AEMOForecast Sensor."""

    def __init__(self, coordinator: AEMOForecastDataUpdateCoordinator, data_key: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.data_key = data_key
        self._attr_should_poll = False  # DataUpdateCoordinator handles updates
        self._last_value = None  # Store the last known value

    @property
    def native_value(self):
        """Return the state of the sensor."""
        item = self.coordinator.data
        if item:
            value = item.get(self.data_key)
            if value is not None:
                self._last_value = value
        
        return value

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        last_update = self.coordinator.lastUpdate

        return {
            "lastUpdate": last_update.isoformat() if last_update else None,
        }


class AEMOForecastSpikeWindowsSensor(AEMOForecastSensor):
    """Sensor which shows the number of spike 30min windows in the forecast."""

    _attr_native_unit_of_measurement = "half-hour windows"

    def __init__(self, coordinator):
        """Initialize the spike windows sensor."""
        super().__init__(coordinator, SPIKE_WINDOWS)
        self._attr_name = "AEMO Forecast Spike Windows"
        self._attr_unique_id = f"aemo_forecast_{coordinator.state_id}_{SPIKE_WINDOWS}"

class AEMOForecastAboveThresholdDurationSensor(AEMOForecastSensor):
    """Sensor which shows the duration above threshold in the forecast."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator):
        """Initialize the above threshold duration sensor."""
        super().__init__(coordinator, ABOVE_THRESHOLD_DURATION)
        self._attr_name = "AEMO Forecast Forecast Above Threshold Duration"
        self._attr_unique_id = f"aemo_forecast_{coordinator.state_id}_{ABOVE_THRESHOLD_DURATION}"

class AEMOForecastNextSpikeWindowSensor(AEMOForecastSensor):
    """Sensor which shows the next spike window in the forecast."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator):
        """Initialize the next spike window sensor."""
        super().__init__(coordinator, NEXT_SPIKE_WINDOW)
        self._attr_name = "AEMO Forecast Next Spike Window"
        self._attr_unique_id = f"aemo_forecast_{coordinator.state_id}_{NEXT_SPIKE_WINDOW}"
    
    @property
    def extra_state_attributes(self):
        # Start with the base attributes defined in LocalvoltsSensor
        attributes = super().extra_state_attributes

        price_at_next_spike = self.coordinator.data.get(NEXT_SPIKE_WINDOW_PRICE)
        if price_at_next_spike is not None:
            attributes[NEXT_SPIKE_WINDOW_PRICE] = price_at_next_spike
            attributes[f"{NEXT_SPIKE_WINDOW_PRICE}_unit"] = "$/kWh"
        else:
            attributes[NEXT_SPIKE_WINDOW_PRICE] = None
            attributes[f"{NEXT_SPIKE_WINDOW_PRICE}_unit"] = None

        return attributes

class AEMOForecastTotalForecastDurationSensor(AEMOForecastSensor):
    """Sensor which shows the total forecast duration."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator):
        """Initialize the total forecast duration sensor."""
        super().__init__(coordinator, TOTAL_FORECAST_DURATION)
        self._attr_name = "AEMO Forecast Total Forecast Duration"
        self._attr_unique_id = f"aemo_forecast_{coordinator.state_id}_{TOTAL_FORECAST_DURATION}"

class AEMOForecastMaxPriceSensor(AEMOForecastSensor):
    """Sensor which shows the maximum price in the forecast."""

    _attr_native_unit_of_measurement = "$/kWh"
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator):
        """Initialize the maximum price sensor."""
        super().__init__(coordinator, MAX_PRICE)
        self._attr_name = "AEMO Forecast Maximum Forecasted Price"
        self._attr_unique_id = f"aemo_forecast_{coordinator.state_id}_{MAX_PRICE}"
    
    @property
    def extra_state_attributes(self):
        # Start with the base attributes defined in LocalvoltsSensor
        attributes = super().extra_state_attributes
        # Add the 'demandInterval' attribute if it's available in the coordinator data
        time_of_max = self.coordinator.data.get(MAX_PRICE_TIME)
        if time_of_max is not None:
            attributes[MAX_PRICE_TIME] = time_of_max
        return attributes

class AEMOForecastMinPriceSensor(AEMOForecastSensor):
    """Sensor which shows the minimum price in the forecast."""

    _attr_native_unit_of_measurement = "$/kWh"
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator):
        """Initialize the minimum price sensor."""
        super().__init__(coordinator, MIN_PRICE)
        self._attr_name = "AEMO Forecast Minimum Forecasted Price"
        self._attr_unique_id = f"aemo_forecast_{coordinator.state_id}_{MIN_PRICE}"
    
    @property
    def extra_state_attributes(self):
        # Start with the base attributes defined in LocalvoltsSensor
        attributes = super().extra_state_attributes
        # Add the 'demandInterval' attribute if it's available in the coordinator data
        time_of_min = self.coordinator.data.get(MIN_PRICE_TIME)
        if time_of_min is not None:
            attributes[MIN_PRICE_TIME] = time_of_min
        return attributes