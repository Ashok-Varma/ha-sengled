"""The interface expected by API."""
from typing import Any, List, Tuple


class APIBulb:
    """Base class that defines the expected interface for a Sengled Bulb."""

    def update_bulb(self, payload: Any) -> None:
        """Deliver an update packet to the bulb."""
        # This method must be implemented by subclasses to update the bulb's state based on the payload.
        raise NotImplementedError("Bulbs must implement update_bulb")

    async def set_brightness(self, value: int) -> None:
        """Set the brightness of the bulb."""
        # This method must be implemented by subclasses to change the bulb's brightness.
        raise NotImplementedError("Bulbs must implement set_brightness")

    async def set_color(self, value: Tuple[int, int, int]) -> None:
        """Set the RGB color of the bulb."""
        # This method must be implemented by subclasses to change the color of a color-capable bulb.
        raise NotImplementedError("Bulbs must implement set_color")

    async def set_effect(self, effect: str, enable: bool) -> None:
        """Set a special effect on the bulb."""
        # This method must be implemented by subclasses to enable or disable a specific effect.
        raise NotImplementedError("Bulbs must implement set_effect")

    async def set_power(self, to_on: bool = True) -> None:
        """Set the power state of the bulb (on or off)."""
        # This method must be implemented by subclasses to turn the bulb on or off.
        raise NotImplementedError("Bulbs must implement set_power")

    async def set_temperature(self, value: int) -> None:
        """Set the color temperature of the bulb."""
        # This method must be implemented by subclasses to adjust the color temperature (in mireds).
        raise NotImplementedError("Bulbs must implement set_temperature")

    @property
    def mqtt_topics(self) -> List[str]:
        """Return a list of MQTT topics relevant to the bulb."""
        # This method must be implemented by subclasses to define the MQTT topics the bulb listens to.
        raise NotImplementedError("Bulbs must implement mqtt_topics")
