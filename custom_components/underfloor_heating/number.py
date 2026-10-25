"""Platforma encji numerycznych (number) dla integracji Ogrzewanie Podłogowe.

Umożliwia odczyt i sterowanie nastawą rotametru w l/h (oraz l/min) dla każdej
pętli podłogówki z poziomu interfejsu Home Assistant oraz automatyzacji.

Wersja: 1.0.0
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_LOOP_ID,
    ATTR_ROTAMETER_FLOW_LH,
    CONF_LOOPS,
    CONF_MANIFOLDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguracja encji numerycznych rotametrów."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = []

    for loop_id, l_data in data[CONF_LOOPS].items():
        # Główny suwak w litrach na godzinę (l/h)
        entities.append(RotameterFlowNumberLH(hass, entry, loop_id, l_data))
        # Pomocniczy suwak w litrach na minutę (l/min) - standardowy odczyt ze skali rotametru
        entities.append(RotameterFlowNumberLMin(hass, entry, loop_id, l_data))

    async_add_entities(entities)


class BaseRotameterNumber(NumberEntity):
    """Bazowa klasa encji numerycznej dla rotametru."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict, suffix: str) -> None:
        self.hass = hass
        self.entry = entry
        self.loop_id = loop_id
        self.l_data = l_data
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_number_{loop_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"loop_{loop_id}")},
            name=f"Pętla: {l_data.get('name', loop_id)}",
            manufacturer="Antigravity",
            model="Pętla Ogrzewania Podłogowego",
            via_device=(DOMAIN, f"manifold_{l_data.get('manifold_id')}"),
        )

    async def async_added_to_hass(self) -> None:
        """Subskrypcja aktualizacji stanu."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.entry.entry_id}_update",
                self._handle_coordinator_update,
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Odświeżenie encji w HA."""
        self.async_write_ha_state()

    @property
    def current_data(self) -> dict[str, Any]:
        """Pobiera dane integracji."""
        return self.hass.data[DOMAIN][self.entry.entry_id]


class RotameterFlowNumberLH(BaseRotameterNumber):
    """Encja rotametru wyrażona w litrach na godzinę (l/h)."""

    _attr_name = "Nastawa rotametru"
    _attr_native_unit_of_measurement = "l/h"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 400.0
    _attr_native_step = 1.0
    _attr_icon = "mdi:water-pump"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict) -> None:
        super().__init__(hass, entry, loop_id, l_data, "flow_lh")

    @property
    def native_value(self) -> float:
        flows = self.current_data.get("rotameter_flows", {})
        return float(flows.get(self.loop_id, self.l_data.get(ATTR_ROTAMETER_FLOW_LH, 90.0)))

    async def async_set_native_value(self, value: float) -> None:
        """Zapis nowej wartości przepływu w l/h."""
        _LOGGER.info("Zmiana nastawy rotametru l/h dla pętli %s: %s", self.loop_id, value)
        self.current_data["rotameter_flows"][self.loop_id] = float(value)
        async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}_update")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        flow_lh = self.native_value
        return {
            "flow_l_min": round(flow_lh / 60.0, 2),
            "loop_id": self.loop_id,
            "section_number": self.l_data.get("section_number", 1),
            "manifold_id": self.l_data.get("manifold_id"),
        }


class RotameterFlowNumberLMin(BaseRotameterNumber):
    """Encja rotametru wyrażona w litrach na minutę (l/min) - zgodna ze szklaną rurką rotametru."""

    _attr_name = "Nastawa rotametru (skala)"
    _attr_native_unit_of_measurement = "l/min"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 6.0
    _attr_native_step = 0.1
    _attr_icon = "mdi:gauge"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict) -> None:
        super().__init__(hass, entry, loop_id, l_data, "flow_lmin")

    @property
    def native_value(self) -> float:
        flows = self.current_data.get("rotameter_flows", {})
        flow_lh = float(flows.get(self.loop_id, self.l_data.get(ATTR_ROTAMETER_FLOW_LH, 90.0)))
        return round(flow_lh / 60.0, 2)

    async def async_set_native_value(self, value: float) -> None:
        """Zapis nowej wartości przepływu w l/min (przeliczane na l/h)."""
        flow_lh = round(float(value) * 60.0, 1)
        _LOGGER.info("Zmiana nastawy rotametru l/min dla pętli %s: %s (%s l/h)", self.loop_id, value, flow_lh)
        self.current_data["rotameter_flows"][self.loop_id] = flow_lh
        async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}_update")

