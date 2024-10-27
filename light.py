"""Sengled light platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .api import ElementsBulb
from .const import ATTRIBUTION, DOMAIN, SUPPORTED_DEVICES

_LOGGER = logging.getLogger(__name__)


class ElementsLightEntity(ElementsBulb, LightEntity):
    """Represents a Sengled light bulb that supports brightness, color, and temperature control dynamically."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, api, discovery) -> None:
        """Initialize a basic light entity."""
        super().__init__(discovery)
        self._api = api

        # Determine supported features from 'supportAttributes'
        support_attributes = self._data.get("supportAttributes", "").split(",")
        self._supports_brightness = "brightness" in support_attributes
        self._supports_color = "color" in support_attributes
        self._supports_color_temp = "colorTemperature" in support_attributes

    def update_bulb(self, payload: dict) -> None:
        """Update bulb state."""
        super().update_bulb(payload)
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light with optional attributes."""
        _LOGGER.debug("Turn on %s with attributes %r", self.name, kwargs)
        if not kwargs:
            await self.set_power(True)
        if self._supports_brightness and ATTR_BRIGHTNESS in kwargs:
            await self.set_brightness(kwargs[ATTR_BRIGHTNESS])
        if self._supports_color and ATTR_RGB_COLOR in kwargs:
            await self.set_color(kwargs[ATTR_RGB_COLOR])
        if self._supports_color_temp and ATTR_COLOR_TEMP in kwargs:
            await self.set_temperature(kwargs[ATTR_COLOR_TEMP])
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            enable = effect != "none"
            await self.set_effect(effect, enable)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        _LOGGER.debug("Turn off %s with attributes %r", self.name, kwargs)
        await self.set_power(False)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for Home Assistant."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Sengled",
            model=self.model,
            sw_version=self.sw_version,
        )

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Return supported color modes based on device capabilities."""
        modes = set()
        if self._supports_color_temp:
            modes.add(ColorMode.COLOR_TEMP)
        if self._supports_color:
            modes.add(ColorMode.RGB)
        if self._supports_brightness:
            modes.add(ColorMode.BRIGHTNESS)
        return modes

    # TODO show effects only if available
    @property
    def supported_features(self) -> LightEntityFeature:
        """Return supported features based on device capabilities."""
        if self._supports_color:
            return LightEntityFeature.EFFECT
        return 0

    def __repr__(self) -> str:
        """String representation for debugging purposes."""
        return (
            f"<{self.__class__.__name__} name={self.name!r} "
            f"brightness={self.brightness!r} rgb={self.rgb_color!r} "
            f"mode={self.color_mode} supported_modes={self.supported_color_modes!r} "
            f"temp={self.color_temp!r}>"
        )


def pick_light(discovery: DiscoveryInfoType):
    """Select which light entity to use based on discovery info."""
    try:
        if discovery["typeCode"] in SUPPORTED_DEVICES:
            return ElementsLightEntity
    except KeyError:
        _LOGGER.error("Device type not found in discovery: %s", discovery)
        return None

    _LOGGER.info("%s Device Integration not tested, defaulting to generic Light.\nDetails : %s", discovery["typeCode"], discovery)
    return ElementsLightEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Sengled platform."""
    api = hass.data[DOMAIN]

    light_cls = pick_light(discovery_info)
    if not light_cls:
        _LOGGER.error("No valid light class found for discovery: %s", discovery_info)
        return

    light = light_cls(api, discovery_info)
    await api.async_register_light(light)
    add_entities([light])
    _LOGGER.info("Discovered and set up light: %r", light)
