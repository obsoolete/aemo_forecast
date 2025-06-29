from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, THRESHOLD_PRICE

from .coordinator import AEMOForecastDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the threshold price number entity."""
    coordinator = hass.data[DOMAIN]['coordinator']
    
    async_add_entities(
        [

            AEMOForecastThresholdPrice(coordinator),
        ]
    )


class AEMOForecastNumber(NumberEntity, CoordinatorEntity):
    """Representation of a AEMOForecast number."""

    def __init__(self, coordinator: AEMOForecastDataUpdateCoordinator, name: str, data_key: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.data_key = data_key
        self._attr_name = name

        if data_key not in coordinator.numbers:
            self.coordinator.numbers[data_key] = 1.0
        self._value = self.coordinator.numbers[self.data_key]
        
        self._attr_should_poll = False  # DataUpdateCoordinator handles updates
        self._last_value = None  # Store the last known value
        self.coordinator.numbers[self.data_key] = self._value

    @property
    def native_value(self):
        return self.coordinator.numbers[self.data_key]

    async def async_set_native_value(self, value: float):
        self.coordinator.numbers[self.data_key] = value
        self.async_write_ha_state()


class AEMOForecastThresholdPrice(AEMOForecastNumber):
    _attr_native_min_value = 0.1
    _attr_native_max_value = 18.5
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "$/kWh"
    
    def __init__(self, coordinator: AEMOForecastDataUpdateCoordinator):
        super().__init__(coordinator, "AEMO Forecast Threshold Price", THRESHOLD_PRICE)
        self._attr_unique_id = f"aemo_forecast_{coordinator.state_id}_{THRESHOLD_PRICE}"

    async def async_set_native_value(self, value: float):
        self.coordinator.numbers[self.data_key] = value

        # Update config entry
        config_entry = self.coordinator.config_entry
        new_options = dict(config_entry.options)
        new_options[THRESHOLD_PRICE] = value
        self.coordinator.hass.config_entries.async_update_entry(
            config_entry,
            options=new_options,
        )

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()  # Trigger a data update