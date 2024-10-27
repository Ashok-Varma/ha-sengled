"""Implementations for the Elements series."""
from __future__ import annotations

import math
import logging
import time
from typing import Any, Final

from .api import API
from .api_bulb import APIBulb

_LOGGER = logging.getLogger(__name__)

# Define constants
PACKET_BRIGHTNESS: Final = "brightness"
PACKET_COLOR_MODE: Final = "colorMode"
PACKET_COLOR_TEMP: Final = "colorTemperature"
PACKET_EFFECT: Final = "effectStatus"
PACKET_MODEL: Final = "typeCode"
PACKET_ONLINE: Final = "online"
PACKET_RGB_COLOR: Final = "color"
PACKET_SW_VERSION: Final = "version"
PACKET_SWITCH: Final = "switch"
PACKET_VALUE_OFF: Final = "0"
PACKET_VALUE_ON: Final = "1"

HA_COLOR_MODE_BRIGHTNESS = "brightness"
HA_COLOR_MODE_COLOR_TEMP = "color_temp"
HA_COLOR_MODE_RGB = "rgb"


def _hassify_discovery(packet: dict[str, Any]) -> dict[str, str]:
    result = {}
    for key, value in packet.items():
        if key in {"attributeList"}:
            continue

        # Handle None values explicitly
        if value is None:
            _LOGGER.debug("Skipping key with None value: %s", key)
            continue

        if isinstance(value, (list, tuple, str)):
            result[key] = value
        else:
            _LOGGER.warning("Weird value while hass-ifying: %s = %r", key, value)

    # Process attributes in attributeList
    for item in packet.get("attributeList", []):
        result[item["name"]] = item["value"]

    return result



def _decode_color_temp(value_pct: str, min_mireds: int, max_mireds: int) -> int:
    """Convert Sengled's brightness percentage to mireds given the light's range."""
    try:
        return math.ceil(
            max_mireds - ((int(value_pct) / 100.0) * (max_mireds - min_mireds))
        )
    except ValueError as e:
        _LOGGER.error(f"Invalid value for color temperature: {value_pct}")
        raise e


def _encode_color_temp(value_mireds: int, min_mireds: int, max_mireds: int) -> str:
    """Convert color temperature from Home Assistant to Sengled format."""
    try:
        return str(math.ceil((max_mireds - value_mireds) / (max_mireds - min_mireds) * 100))
    except ZeroDivisionError as e:
        _LOGGER.error(f"Invalid mired range for color temperature: {min_mireds}-{max_mireds}")
        raise e


class ElementsBulb(APIBulb):
    """A Wifi Elements bulb."""

    _data: dict[str, str]
    _api: API  # Expected from mixed-in class

    def __init__(self, discovery: dict[str, Any]) -> None:
        """Initialize the ElementsBulb."""
        _LOGGER.debug(f"{self.__class__.__name__} init {discovery}")
        self._data = _hassify_discovery(discovery)

    @property
    def unique_id(self) -> str:
        return self._data["deviceUuid"]

    @property
    def name(self) -> str:
        return self._data["name"]

    @property
    def available(self) -> bool:
        """Check if the light is available."""
        return self._data[PACKET_ONLINE] == PACKET_VALUE_ON

    @property
    def is_on(self) -> bool:
        return self._data[PACKET_SWITCH] == PACKET_VALUE_ON

    @property
    def brightness(self) -> int | None:
        """Convert brightness from 0-100 to 0-255 range."""
        try:
            return math.ceil(int(self._data[PACKET_BRIGHTNESS]) / 100 * 255)
        except (KeyError, ValueError) as e:
            _LOGGER.warning(f"Invalid brightness value: {e}")
            return None

    @property
    def color_mode(self) -> str | None:
        """Return the current color mode."""
        return {
            "1": HA_COLOR_MODE_RGB,
            "2": HA_COLOR_MODE_COLOR_TEMP
        }.get(self._data.get(PACKET_COLOR_MODE), HA_COLOR_MODE_BRIGHTNESS)

    @property
    def sw_version(self) -> str:
        return self._data[PACKET_SW_VERSION]

    @property
    def model(self) -> str:
        return self._data[PACKET_MODEL]

    @property
    def mqtt_topics(self) -> list[str]:
        """Return MQTT topics for the light."""
        return [
            f"wifielement/{self.unique_id}/status",
        ]

    async def set_power(self, to_on: bool = True):
        """Set the power on/off."""
        value = PACKET_VALUE_ON if to_on else PACKET_VALUE_OFF
        await self._async_send_updates({"type": PACKET_SWITCH, "value": value})

    async def set_brightness(self, value: int):
        """Set the brightness level (0-255)."""
        try:
            await self._async_send_updates(
                {"type": PACKET_BRIGHTNESS, "value": str(math.ceil(value / 255 * 100))}
            )
        except ValueError as e:
            _LOGGER.error(f"Failed to set brightness: {e}")

    async def _async_send_updates(self, *messages: dict[str, Any]):
        """Send updates to the light via MQTT."""
        extras = {"dn": self.unique_id, "time": int(time.time() * 1000)}
        try:
            await self._api.async_mqtt_publish(
                f"wifielement/{self.unique_id}/update",
                [message | extras for message in messages],
            )
        except Exception as e:
            _LOGGER.error(f"Failed to send updates to light {self.unique_id}: {e}")

    def update_bulb(self, payload: list[dict[str, Any]]):
        """Update the bulb's state based on the payload."""
        packet = {}
        try:
            for item in payload:
                if not item:
                    continue
                packet[item["type"]] = item["value"]
            _LOGGER.debug(f"Applying update to {self.name}: {packet}")
            self._data.update(packet)
        except (KeyError, ValueError) as e:
            _LOGGER.warning(f"Failed to update bulb {self.unique_id}: {e}")


class ElementsColorBulb(ElementsBulb):
    """A Wifi Elements color bulb."""

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature."""
        packet_temp = self._data.get(PACKET_COLOR_TEMP)
        if not packet_temp:
            return None
        return _decode_color_temp(packet_temp, self.min_mireds, self.max_mireds)

    @property
    def effect_list(self) -> list[str] | None:
        """Return available effects."""
        return [
            "christmas",
            "colorCycle",
            "festival",
            "halloween",
            "randomColor",
            "rhythm",
            "none",
        ]

    @property
    def max_mireds(self) -> int:
        return 400

    @property
    def min_mireds(self) -> int:
        return 154

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color."""
        try:
            return tuple(int(rgb) for rgb in self._data[PACKET_RGB_COLOR].split(":"))
        except (ValueError, KeyError) as e:
            _LOGGER.warning(f"Invalid RGB color value: {e}")
            return None

    async def set_color(self, value: tuple[int, int, int]):
        """Set the RGB color."""
        try:
            await self._async_send_updates(
                {"type": PACKET_RGB_COLOR, "value": ":".join(str(v) for v in value)}
            )
        except Exception as e:
            _LOGGER.error(f"Failed to set color for {self.unique_id}: {e}")

    async def set_effect(self, effect: str, enable: bool):
        """Set a special effect."""
        try:
            await self._async_send_updates(
                {"type": effect, "value": PACKET_VALUE_ON if enable else PACKET_VALUE_OFF}
            )
        except Exception as e:
            _LOGGER.error(f"Failed to set effect {effect} for {self.unique_id}: {e}")

    async def set_temperature(self, temp_mireds: int):
        """Set the color temperature in mireds."""
        try:
            await self._async_send_updates(
                {
                    "type": PACKET_COLOR_TEMP,
                    "value": _encode_color_temp(temp_mireds, self.min_mireds, self.max_mireds),
                }
            )
        except Exception as e:
            _LOGGER.error(f"Failed to set color temperature for {self.unique_id}: {e}")
