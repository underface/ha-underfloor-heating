"""Platforma sensorów binarnych (binary_sensor) dla integracji Ogrzewanie Podłogowe.

Dostarcza jednoznaczne stany logiczne (zrównoważenie pętli, wykrycie problemów,
stan rozdzielacza) dla automatyzacji, powiadomień i innych aplikacji HA.

Wersja: 1.0.0
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .calculations import (
    calculate_hydraulics,
    calculate_thermal_properties,
    diagnose_loop,
    diagnose_manifold,
    estimate_loop_length,
)
from .const import (
    ATTR_APPROACH_LENGTH,
    ATTR_AREA,
    ATTR_FLOOR_COVERING,
    ATTR_PIPE_TYPE,
    ATTR_SCREED_THICKNESS,
    ATTR_SCREED_TYPE,
    ATTR_SPACING_CM,
    CONF_LOOPS,
    CONF_MANIFOLDS,
    CONF_ZONES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguracja platformy sensorów binarnych."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = []

    # Sensory binarne dla rozdzielaczy
    for manifold_id, m_data in data[CONF_MANIFOLDS].items():
        entities.append(ManifoldBalancedBinarySensor(hass, entry, manifold_id, m_data))

    # Sensory binarne dla pętli
    for loop_id, l_data in data[CONF_LOOPS].items():
        entities.append(LoopBalancedBinarySensor(hass, entry, loop_id, l_data))
        entities.append(LoopIssueBinarySensor(hass, entry, loop_id, l_data))

    async_add_entities(entities)


class BaseHeatingBinaryEntity(BinarySensorEntity):
    """Bazowa encja binary_sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, unique_id: str) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{unique_id}"

    async def async_added_to_hass(self) -> None:
        """Subskrypcja zmian danych."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.entry.entry_id}_update",
                self._handle_coordinator_update,
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def current_data(self) -> dict[str, Any]:
        return self.hass.data[DOMAIN][self.entry.entry_id]


class ManifoldBalancedBinarySensor(BaseHeatingBinaryEntity):
    """Informuje, czy wszystkie pętle na rozdzielaczu są poprawnie zrównoważone."""

    _attr_name = "Zrównoważenie hydrauliczne"
    _attr_icon = "mdi:check-network"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, manifold_id: str, m_data: dict) -> None:
        super().__init__(hass, entry, f"manifold_{manifold_id}_is_balanced")
        self.manifold_id = manifold_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"manifold_{manifold_id}")},
            name=m_data.get("name", manifold_id),
        )

    @property
    def is_on(self) -> bool:
        data = self.current_data
        for loop_id, l_info in data[CONF_LOOPS].items():
            if l_info.get("manifold_id") == self.manifold_id:
                flow_lh = data["rotameter_flows"].get(loop_id, 0.0)
                zone = data[CONF_ZONES].get(l_info.get("zone_id"), {})
                loops_in_zone = max(l_info.get("loops_in_zone", 1), 1)
                length = estimate_loop_length(
                    zone.get(ATTR_AREA, 15.0),
                    loops_in_zone,
                    l_info.get(ATTR_SPACING_CM, 15.0),
                    l_info.get(ATTR_APPROACH_LENGTH, 4.0),
                )
                hyd = calculate_hydraulics(flow_lh, length, l_info.get(ATTR_PIPE_TYPE, "pex_16x2"))
                therm = calculate_thermal_properties(
                    zone.get(ATTR_AREA, 15.0),
                    zone.get(ATTR_SCREED_TYPE, "cement"),
                    zone.get(ATTR_SCREED_THICKNESS, 65.0),
                    zone.get(ATTR_FLOOR_COVERING, "tiles"),
                    zone.get("heat_load_w_m2", 45.0),
                )
                req_flow = therm["required_flow_lh"] / float(loops_in_zone)
                diag = diagnose_loop(
                    flow_lh,
                    req_flow,
                    length,
                    l_info.get(ATTR_PIPE_TYPE, "pex_16x2"),
                    hyd["pressure_drop_kpa"],
                    hyd["flow_velocity_ms"],
                )
                if not diag["is_balanced"]:
                    return False
        return True


class LoopBalancedBinarySensor(BaseHeatingBinaryEntity):
    """Informuje, czy dana pętla mieści się w dopuszczalnym zrównoważeniu przepływu."""

    _attr_name = "Pętla zrównoważona"
    _attr_icon = "mdi:scale-balance"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict) -> None:
        super().__init__(hass, entry, f"loop_{loop_id}_is_balanced")
        self.loop_id = loop_id
        self.l_data = l_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"loop_{loop_id}")},
            via_device=(DOMAIN, f"manifold_{l_data.get('manifold_id')}"),
        )

    @property
    def is_on(self) -> bool:
        data = self.current_data
        loop = data[CONF_LOOPS].get(self.loop_id, self.l_data)
        zone = data[CONF_ZONES].get(loop.get("zone_id"), {})
        loops_in_zone = max(loop.get("loops_in_zone", 1), 1)

        length = estimate_loop_length(
            zone.get(ATTR_AREA, 15.0),
            loops_in_zone,
            loop.get(ATTR_SPACING_CM, 15.0),
            loop.get(ATTR_APPROACH_LENGTH, 4.0),
        )
        flow_lh = data["rotameter_flows"].get(self.loop_id, 0.0)
        hyd = calculate_hydraulics(flow_lh, length, loop.get(ATTR_PIPE_TYPE, "pex_16x2"))
        therm = calculate_thermal_properties(
            zone.get(ATTR_AREA, 15.0),
            zone.get(ATTR_SCREED_TYPE, "cement"),
            zone.get(ATTR_SCREED_THICKNESS, 65.0),
            zone.get(ATTR_FLOOR_COVERING, "tiles"),
            zone.get("heat_load_w_m2", 45.0),
        )
        req_flow = therm["required_flow_lh"] / float(loops_in_zone)
        diag = diagnose_loop(
            flow_lh,
            req_flow,
            length,
            loop.get(ATTR_PIPE_TYPE, "pex_16x2"),
            hyd["pressure_drop_kpa"],
            hyd["flow_velocity_ms"],
        )
        return bool(diag["is_balanced"])


class LoopIssueBinarySensor(BaseHeatingBinaryEntity):
    """Wykrywa anomalie i problemy fizyczne/hydrauliczne pętli."""

    _attr_name = "Wykryto problem pętli"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict) -> None:
        super().__init__(hass, entry, f"loop_{loop_id}_has_issue")
        self.loop_id = loop_id
        self.l_data = l_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"loop_{loop_id}")},
            via_device=(DOMAIN, f"manifold_{l_data.get('manifold_id')}"),
        )

    @property
    def is_on(self) -> bool:
        attrs = self.extra_state_attributes
        return len(attrs.get("warnings", [])) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.current_data
        loop = data[CONF_LOOPS].get(self.loop_id, self.l_data)
        zone = data[CONF_ZONES].get(loop.get("zone_id"), {})
        loops_in_zone = max(loop.get("loops_in_zone", 1), 1)

        length = estimate_loop_length(
            zone.get(ATTR_AREA, 15.0),
            loops_in_zone,
            loop.get(ATTR_SPACING_CM, 15.0),
            loop.get(ATTR_APPROACH_LENGTH, 4.0),
        )
        flow_lh = data["rotameter_flows"].get(self.loop_id, 0.0)
        hyd = calculate_hydraulics(flow_lh, length, loop.get(ATTR_PIPE_TYPE, "pex_16x2"))
        therm = calculate_thermal_properties(
            zone.get(ATTR_AREA, 15.0),
            zone.get(ATTR_SCREED_TYPE, "cement"),
            zone.get(ATTR_SCREED_THICKNESS, 65.0),
            zone.get(ATTR_FLOOR_COVERING, "tiles"),
            zone.get("heat_load_w_m2", 45.0),
        )
        req_flow = therm["required_flow_lh"] / float(loops_in_zone)
        diag = diagnose_loop(
            flow_lh,
            req_flow,
            length,
            loop.get(ATTR_PIPE_TYPE, "pex_16x2"),
            hyd["pressure_drop_kpa"],
            hyd["flow_velocity_ms"],
        )
        return {
            "warnings": diag["warnings"],
            "warning_count": len(diag["warnings"]),
            "status": diag["status"],
        }

