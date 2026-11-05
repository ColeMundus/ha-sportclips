"""Account-free city/ZIP, geographic suggestion, then salon selection."""

from dataclasses import asdict
from typing import Any

import probatio as p
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import ProviderError, RequestGate, SportClipsClient
from .const import DOMAIN
from .models import Location, Salon


class PollingIntervalSelector(selector.NumberSelector):
    """Keep a native number form while rejecting fractional/coerced minutes."""

    def __call__(self, value: Any) -> float:
        if type(value) not in (int, float) or not float(value).is_integer():
            raise p.Invalid("Expected whole minutes")
        return super().__call__(value)


def polling_field() -> PollingIntervalSelector:
    """Build the shared setup/options selector."""
    return PollingIntervalSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=60,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="min",
        )
    )


class SportClipsOptionsFlow(OptionsFlow):
    """Configure polling for new or existing entries."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    "polling_interval": int(user_input["polling_interval"]),
                },
            )
        return self.async_show_form(
            step_id="init",
            data_schema=p.Schema(
                {
                    p.Required(
                        "polling_interval",
                        default=self.config_entry.options.get("polling_interval", 2),
                    ): polling_field(),
                }
            ),
        )


class SportClipsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one stable source-salon entry."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SportClipsOptionsFlow:
        """Edit the interval without changing salon identity."""
        return SportClipsOptionsFlow()

    def __init__(self) -> None:
        self.locations: list[Location] = []
        self.salons: list[Salon] = []

    def _client(self) -> SportClipsClient:
        gate = self.hass.data.setdefault(DOMAIN, {}).setdefault("gate", RequestGate())
        return SportClipsClient(async_get_clientsession(self.hass), gate)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None and not 1 <= len(user_input["search"].strip()) <= 128:
            errors["base"] = "invalid_search"
        elif user_input is not None:
            try:
                self.locations = await self._client().search(
                    user_input["search"].strip()
                )
            except ProviderError:
                errors["base"] = "cannot_connect"
            else:
                if self.locations:
                    return await self.async_step_location()
                errors["base"] = "no_locations"
        return self.async_show_form(
            step_id="user",
            data_schema=p.Schema({p.Required("search"): selector.TextSelector()}),
            errors=errors,
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                location = self.locations[int(user_input["location"])]
                self.salons = await self._client().discover(location)
            except ProviderError:
                errors["base"] = "cannot_connect"
            else:
                if self.salons:
                    return await self.async_step_salon()
                errors["base"] = "no_salons"
        return self.async_show_form(
            step_id="location",
            data_schema=p.Schema(
                {
                    p.Required("location"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=str(i), label=item.name)
                                for i, item in enumerate(self.locations)
                            ]
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_salon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            salon = next(s for s in self.salons if s.id == user_input["salon"])
            await self.async_set_unique_id(salon.id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=salon.name,
                data=asdict(salon),
                options={"polling_interval": int(user_input["polling_interval"])},
            )
        return self.async_show_form(
            step_id="salon",
            data_schema=p.Schema(
                {
                    p.Required("salon"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=item.id,
                                    label=f"{item.name} ({item.short_name})",
                                )
                                for item in self.salons
                            ]
                        )
                    ),
                    p.Required("polling_interval", default=2): polling_field(),
                }
            ),
        )
