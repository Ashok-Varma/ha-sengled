"""Zigbee bulb implementations."""
from __future__ import annotations
from typing import Any, List


class ZigbeeBulb:
    """A white Zigbee bulb base class."""

    def __init__(self, discovery: dict[str, Any]) -> None:
        """Initialize a Zigbee bulb."""
        self._data = discovery

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the Zigbee bulb."""
        return self._data["deviceUuid"]

    @property
    def name(self) -> str:
        """Return the name of the Zigbee bulb."""
        return self._data["name"]

    @property
    def available(self) -> bool:
        """Return whether the bulb is available (online)."""
        return self._data.get("online", "0") == "1"

    async def set_brightness(self, value: int) -> None:
        """Set the brightness of the Zigbee bulb."""
        raise NotImplementedError("ZigbeeBulb must implement set_brightness")

    async def set_power(self, to_on: bool = True) -> None:
        """Turn the Zigbee bulb on or off."""
        raise NotImplementedError("ZigbeeBulb must implement set_power")

    @property
    def mqtt_topics(self) -> List[str]:
        """Return the MQTT topics for the Zigbee bulb."""
        raise NotImplementedError("ZigbeeBulb must implement mqtt_topics")


class ZigbeeColorBulb(ZigbeeBulb):
    """A color-capable Zigbee bulb."""

    async def set_color(self, rgb: tuple[int, int, int]) -> None:
        """Set the color of the Zigbee bulb."""
        raise NotImplementedError("ZigbeeColorBulb must implement set_color")

    async def set_effect(self, effect: str, enable: bool) -> None:
        """Set a special effect for the Zigbee bulb."""
        raise NotImplementedError("ZigbeeColorBulb must implement set_effect")

    async def set_temperature(self, temp_mireds: int) -> None:
        """Set the color temperature of the Zigbee bulb."""
        raise NotImplementedError("ZigbeeColorBulb must implement set_temperature")

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the current RGB color of the Zigbee bulb."""
        raise NotImplementedError("ZigbeeColorBulb must implement rgb_color")
