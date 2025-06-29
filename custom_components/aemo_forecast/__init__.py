"""The AEMO Forecast integration."""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

import logging
import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from .coordinator import AEMOForecastDataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_STATE_ID,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_STATE_ID): vol.In(["NSW", "QLD", "SA", "TAS", "VIC"]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up the AEMO Forecast integration from a config entry."""
    _LOGGER.debug("Setting up the AEMO Forecast component from config entry.")

    # Initialize coordinator
    coordinator = AEMOForecastDataUpdateCoordinator(hass, config_entry)

    try:
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            _LOGGER.error("Initial data fetch failed")
            return False
    except Exception as err:
        _LOGGER.error("Error initializing coordinator: %s", err)
        return False

    # Store data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]['coordinator'] = coordinator

    # Load the sensor platform
    await hass.config_entries.async_forward_entry_setups(config_entry, ["sensor"])
    await hass.config_entries.async_forward_entry_setups(config_entry, ["number"])

    return True


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the AEMO Forecast component."""
    _LOGGER.debug("Setting up the AEMO Forecast component.")
    # No action needed for YAML configuration, as we are using config entries now
    return True

def validate_state_id(state_id):
    """Validate the state id key."""
    valid_state_ids = ["NSW", "QLD", "SA", "TAS", "VIC"]

    # Check if the API key is of the expected length and a valid hexadecimal
    if state_id in valid_state_ids:
        return True
    else:
        _LOGGER.error("Invalid state ID.")
        return False
