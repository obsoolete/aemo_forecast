import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, CONF_STATE_ID
from . import validate_state_id

_LOGGER = logging.getLogger(__name__)

# Define the schema with placeholders for default values
def build_data_schema(existing_data):
    return vol.Schema(
        {
            vol.Required(CONF_STATE_ID, default=existing_data.get(CONF_STATE_ID, "NSW")): vol.In(["NSW", "QLD", "SA", "TAS", "VIC"]),
        }
    )

class AEMOForecastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the AEMO Forecast integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        # If this is a reconfiguration, pre-populate with existing data
        existing_entry = next(iter(self._async_current_entries()), None)
        existing_data = existing_entry.data if existing_entry else {}

        if user_input is not None:
            # Validate the inputs
            if not validate_state_id(user_input[CONF_STATE_ID]):
                errors[CONF_STATE_ID] = "invalid_state_id"

            if not errors:
                title = f"AEMO Forecast: {user_input[CONF_STATE_ID]}"
                # Save the configuration and create the entry
                return self.async_create_entry(title=title, data=user_input)
                
        # Show the form if there are errors or if the user input is None
        return self.async_show_form(
            step_id="user", data_schema=build_data_schema(existing_data), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AEMOForecastOptionsFlowHandler(config_entry)

class AEMOForecastOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the AEMO Forecast integration."""

    def __init__(self, config_entry):
        """Initialize AEMO Forecast options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the options step."""
        errors = {}

        if user_input is not None:
            # Save the updated options
            return self.async_create_entry(title="", data=user_input)

        # Pre-populate with existing options
        options = self.config_entry.options
        return self.async_show_form(
            step_id="user", data_schema=build_data_schema(options), errors=errors
        )