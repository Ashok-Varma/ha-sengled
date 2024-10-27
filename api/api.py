"""API implementation for Sengled"""
import asyncio
from http import HTTPStatus
import json
import logging
import ssl
from typing import Any
from urllib import parse
import uuid

import aiohttp
import asyncio_mqtt as mqtt

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import DiscoveryInfoType

from ..const import DOMAIN
from .api_bulb import APIBulb

_LOGGER = logging.getLogger(__name__)


class AuthError(Exception):
    """Exception raised for authentication errors."""


class API:
    """API for Sengled"""

    _inception_url: parse.ParseResult | None = None
    _jbalancer_url: parse.ParseResult | None = None
    _jsession_id: str | None = None
    _lights: dict[str, APIBulb]
    _mqtt: mqtt.Client | None = None

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        self._hass = hass
        self._username = username
        self._password = password

        self._lights = {}
        self._lights_mutex = asyncio.Lock()
        self._cookiejar = aiohttp.CookieJar()
        self._http = aiohttp.ClientSession(cookie_jar=self._cookiejar)

    @staticmethod
    async def check_auth(username, password):
        """Check if authentication works."""
        await API(None, username, password)._async_login()

    async def _async_login(self):
        url = "https://ucenter.cloud.sengled.com/user/app/customer/v2/AuthenCross.json"
        # For Zigbee? login_path = "/zigbee/customer/login.json"
        payload = {
            "uuid": uuid.uuid4().hex[:-16],
            "user": self._username,
            "pwd": self._password,
            "osType": "android",
            "productCode": "life",
            "appCode": "life",
        }

        try:
            async with self._http.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != HTTPStatus.OK:
                    _LOGGER.error(f"Authentication failed with status: {resp.status} and headers: {resp.headers}")
                    raise AuthError(f"HTTP error {resp.status}")
                data = await resp.json()
                if data["ret"] != 0:
                    _LOGGER.error(f"Login failed: {data['msg']}")
                    raise AuthError(f"Login failed: {data['msg']}")
                self._jsession_id = data["jsessionId"]
            _LOGGER.info("API login complete")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Failed to login: {e}")
            raise AuthError(f"Login failed due to network issue: {e}")

    async def _async_get_server_info(self):
        """Get secondary server info from the primary."""
        url = "https://life2.cloud.sengled.com/life2/server/getServerInfo.json"
        try:
            async with self._http.post(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != HTTPStatus.OK:
                    _LOGGER.error(f"Failed to get server info: HTTP {resp.status}")
                    return
                data = await resp.json()
                _LOGGER.debug("Raw server info %r", data)
                self._jbalancer_url = parse.urlparse(data["jbalancerAddr"])
                self._inception_url = parse.urlparse(data["inceptionAddr"])
            _LOGGER.info("API server info acquired")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error fetching server info: {e}")

    async def _async_setup_mqtt(self):
        """Set up MQTT client."""
        for attempt in range(3):  # Retry logic
            try:
                client = mqtt.Client(
                    self._inception_url.hostname,
                    self._inception_url.port,
                    client_id=f"{self._jsession_id}@lifeApp",
                    tls_context=ssl.create_default_context(),
                    transport="websockets",
                    websocket_headers={
                        "Cookie": f"JSESSIONID={self._jsession_id}",
                        "X-Requested-With": "com.sengled.life2",
                    },
                    websocket_path=self._inception_url.path,
                )

                await client.connect()
                self._mqtt = client

                async with self._lights_mutex:
                    lights = tuple(self._lights.values())
                for light in lights:
                    await self._subscribe_light(light)

                _LOGGER.info("MQTT client ready")
                break
            except mqtt.error.MqttConnectError as e:
                _LOGGER.warning(f"MQTT connection attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

    async def _async_discover_lights(self) -> list[DiscoveryInfoType]:
        """Get a list of HASS-friendly discovered devices."""
        url = "https://life2.cloud.sengled.com/life2/device/list.json"
        try:
            async with self._http.post(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != HTTPStatus.OK:
                    _LOGGER.error(f"Failed to discover lights: HTTP {resp.status}")
                    return []
                data = await resp.json()
                for device in data["deviceList"]:
                    self._hass.helpers.discovery.load_platform(
                        Platform.LIGHT, DOMAIN, device, {}
                    )
                _LOGGER.info("API discovery complete")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error discovering lights: {e}")

    async def async_start(self):
        """Start the API's main event loop."""
        await self._async_login()
        await self._async_get_server_info()
        await self._async_discover_lights()

        while True:
            try:
                await self._async_setup_mqtt()
                await self._message_loop()
            except mqtt.error.MqttConnectError as conerr:
                _LOGGER.info(f"MQTT refused, reauthenticating {conerr}")
                await self._async_login()
            except mqtt.MqttError as error:
                _LOGGER.info(f"MQTT dropped, waiting to reconnect {error}")
                await asyncio.sleep(10)

    async def _message_loop(self):
        """Handle incoming MQTT messages."""
        async with self._mqtt.messages() as messages:
            async for message in messages:
                if message.topic.matches("wifielement/+/status"):
                    await self._handle_status(message)
                elif message.topic.matches("wifielement/+/update"):
                    pass
                else:
                    _LOGGER.warning(f"Dropping unknown message: {message.topic} {message.payload}")

    async def async_register_light(self, light):
        """Subscribe a light to its updates."""
        async with self._lights_mutex:
            self._lights[light.unique_id] = light
        await self._subscribe_light(light)

    async def _subscribe_light(self, light):
        """Subscribe a light to its MQTT topics."""
        if self._mqtt:
            for topic in light.mqtt_topics:
                await self._mqtt.subscribe(topic)

    async def async_mqtt_publish(self, topic: str, message: Any):
        """Send an MQTT update to central control."""
        try:
            await self._mqtt.publish(
                topic,
                payload=json.dumps(message),
            )
            _LOGGER.debug(f"MQTT publish: {topic} {message}")
        except mqtt.MqttError as e:
            _LOGGER.error(f"Failed to publish MQTT message: {e}")

    async def _handle_status(self, msg):
        """Handle a status message from upstream."""
        light_id = msg.topic.value.split("/")[1]
        async with self._lights_mutex:
            light = self._lights.get(light_id)
        if not light:
            _LOGGER.warning(f"Status received for unknown light: {light_id}")
            return

        try:
            payload = json.loads(msg.payload)
            if not isinstance(payload, list):
                _LOGGER.warning(f"Unexpected status payload: {payload}")
                return
            light.update_bulb(payload)
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Failed to decode MQTT message: {e}")

    async def shutdown(self):
        """Shutdown and clean up resources."""
        if self._mqtt:
            await self._mqtt.disconnect()
        await self._http.close()
        _LOGGER.info("API shutdown complete")
