"""Platforma sensorów (czujników) dla integracji Ogrzewanie Podłogowe.

Generuje encje sensorów dla rozdzielaczy, stref podłogówki oraz pojedynczych pętli,
w tym estymacje długości rur, obliczenia hydrauliczne, właściwości wylewki
oraz stan bilansowania z kompletem atrybutów dla automatyzacji i zewnętrznych dodatków.

Wersja: 1.4.0
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTime,
)
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
    ATTR_LOOP_ID,
    ATTR_MANIFOLD_ID,
    ATTR_PIPE_TYPE,
    ATTR_ROTAMETER_FLOW_LH,
    ATTR_SCREED_THICKNESS,
    ATTR_SCREED_TYPE,
    ATTR_SPACING_CM,
    ATTR_ZONE_ID,
    CONF_LOOPS,
    CONF_MANIFOLDS,
    CONF_ZONES,
    DOMAIN,
    PIPE_TYPES,
    SCREED_TYPES,
    WATER_SPECIFIC_HEAT,
)
from .helpers import (
    clean_loop_name,
    get_loop_device_info,
    get_manifold_device_info,
    get_zone_device_info,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguracja platformy sensorów na podstawie wpisu."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    # 1. Sensory dla rozdzielaczy
    for manifold_id, m_data in data[CONF_MANIFOLDS].items():
        entities.append(ManifoldTotalFlowSensor(hass, entry, manifold_id, m_data))
        entities.append(ManifoldMaxPressureDropSensor(hass, entry, manifold_id, m_data))
        entities.append(ManifoldStatusSensor(hass, entry, manifold_id, m_data))

    # 2. Sensory dla stref (wylewka, bezwładność, zapotrzebowanie, metraż, przepływ całkowity)
    for zone_id, z_data in data[CONF_ZONES].items():
        entities.append(ZoneAreaSensor(hass, entry, zone_id, z_data))
        entities.append(ZoneTotalFlowSensor(hass, entry, zone_id, z_data))
        entities.append(ZoneHeatOutputSensor(hass, entry, zone_id, z_data))
        entities.append(ZoneRequiredFlowSensor(hass, entry, zone_id, z_data))
        entities.append(ZoneScreedInertiaSensor(hass, entry, zone_id, z_data))
        entities.append(ZoneScreedInfoSensor(hass, entry, zone_id, z_data))

    # 3. Sensory dla pętli podłogówki (estymowana długość, opory, prędkości, status)
    zones_data = data[CONF_ZONES]
    for loop_id, l_data in data[CONF_LOOPS].items():
        entities.append(LoopEstimatedLengthSensor(hass, entry, loop_id, l_data, zones_data))
        entities.append(LoopPressureDropSensor(hass, entry, loop_id, l_data, zones_data))
        entities.append(LoopFlowVelocitySensor(hass, entry, loop_id, l_data, zones_data))
        entities.append(LoopBalancingStatusSensor(hass, entry, loop_id, l_data, zones_data))

    async_add_entities(entities)


class BaseHeatingEntity(SensorEntity):
    """Bazowa encja podłogówki powiązana z urządzeniem i odświeżaniem."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, unique_id: str) -> None:
        """Inicjalizacja encji."""
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{unique_id}"

    async def async_added_to_hass(self) -> None:
        """Zarejestruj nasłuchiwanie na sygnał aktualizacji danych."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.entry.entry_id}_update",
                self._handle_coordinator_update,
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Wywoływane po aktualizacji danych."""
        self.async_write_ha_state()

    @property
    def current_data(self) -> Dict[str, Any]:
        """Pobiera aktualny słownik danych integracji."""
        return self.hass.data[DOMAIN][self.entry.entry_id]


class ManifoldTotalFlowSensor(BaseHeatingEntity):
    """Sensor sumarycznego przepływu na rozdzielaczu."""

    _attr_name = "Sumaryczny przepływ"
    _attr_native_unit_of_measurement = "l/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:waves"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, manifold_id: str, m_data: dict) -> None:
        super().__init__(hass, entry, f"manifold_{manifold_id}_total_flow")
        self.manifold_id = manifold_id
        self.m_data = m_data
        self._attr_device_info = get_manifold_device_info(manifold_id, m_data)

    @property
    def native_value(self) -> float:
        data = self.current_data
        total_flow = 0.0
        for loop_id, l_info in data[CONF_LOOPS].items():
            if l_info.get("manifold_id") == self.manifold_id:
                total_flow += data["rotameter_flows"].get(loop_id, 0.0)
        return round(total_flow, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.native_value
        return {
            "flow_l_min": round(val / 60.0, 2),
            "manifold_id": self.manifold_id,
        }


class ManifoldMaxPressureDropSensor(BaseHeatingEntity):
    """Sensor maksymalnego spadku ciśnienia na rozdzielaczu."""

    _attr_name = "Maksymalny spadek ciśnienia"
    _attr_native_unit_of_measurement = UnitOfPressure.KPA
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, manifold_id: str, m_data: dict) -> None:
        super().__init__(hass, entry, f"manifold_{manifold_id}_max_dp")
        self.manifold_id = manifold_id
        self._attr_device_info = get_manifold_device_info(manifold_id, m_data)

    @property
    def native_value(self) -> float:
        data = self.current_data
        max_dp = 0.0
        for loop_id, l_info in data[CONF_LOOPS].items():
            if l_info.get("manifold_id") == self.manifold_id:
                flow_lh = data["rotameter_flows"].get(loop_id, 0.0)
                zone = data[CONF_ZONES].get(l_info.get("zone_id"), {})
                area = l_info.get("area_m2") or zone.get(ATTR_AREA, 15.0)
                loops_cnt = 1 if l_info.get("area_m2") else l_info.get("loops_in_zone", 1)
                length = estimate_loop_length(
                    area,
                    loops_cnt,
                    l_info.get(ATTR_SPACING_CM, 15.0),
                    l_info.get(ATTR_APPROACH_LENGTH, 4.0),
                )
                hyd = calculate_hydraulics(flow_lh, length, l_info.get(ATTR_PIPE_TYPE, "pex_16x2"))
                if hyd["pressure_drop_kpa"] > max_dp:
                    max_dp = hyd["pressure_drop_kpa"]
        return max_dp


class ManifoldStatusSensor(BaseHeatingEntity):
    """Sensor statusu równoważenia całego rozdzielacza."""

    _attr_name = "Status hydrauliczny"
    _attr_icon = "mdi:check-decagram"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, manifold_id: str, m_data: dict) -> None:
        super().__init__(hass, entry, f"manifold_{manifold_id}_status")
        self.manifold_id = manifold_id
        self._attr_device_info = get_manifold_device_info(manifold_id, m_data)

    @property
    def native_value(self) -> str:
        attrs = self.extra_state_attributes
        return "Zrównoważony" if attrs.get("is_balanced", True) else "Wymaga regulacji"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.current_data
        loop_diags = []
        for loop_id, l_info in data[CONF_LOOPS].items():
            if l_info.get("manifold_id") == self.manifold_id:
                flow_lh = data["rotameter_flows"].get(loop_id, 0.0)
                zone = data[CONF_ZONES].get(l_info.get("zone_id"), {})
                area = l_info.get("area_m2") or zone.get(ATTR_AREA, 15.0)
                loops_in_zone = 1 if l_info.get("area_m2") else max(l_info.get("loops_in_zone", 1), 1)
                length = estimate_loop_length(
                    area,
                    loops_in_zone,
                    l_info.get(ATTR_SPACING_CM, 15.0),
                    l_info.get(ATTR_APPROACH_LENGTH, 4.0),
                )
                screed_type = l_info.get("screed_type") or zone.get(ATTR_SCREED_TYPE, "cement")
                screed_thick = l_info.get("screed_thickness_mm") or zone.get(ATTR_SCREED_THICKNESS, 50.0)
                hyd = calculate_hydraulics(flow_lh, length, l_info.get(ATTR_PIPE_TYPE, "pex_16x2"))
                therm = calculate_thermal_properties(
                    area,
                    screed_type,
                    screed_thick,
                    zone.get(ATTR_FLOOR_COVERING, "tiles"),
                    zone.get("heat_load_w_m2", 45.0),
                )
                req_flow_per_loop = therm["required_flow_lh"] / float(loops_in_zone)
                diag = diagnose_loop(
                    flow_lh,
                    req_flow_per_loop,
                    length,
                    l_info.get(ATTR_PIPE_TYPE, "pex_16x2"),
                    hyd["pressure_drop_kpa"],
                    hyd["flow_velocity_ms"],
                )
                diag["loop_id"] = loop_id
                diag["current_flow_lh"] = flow_lh
                diag["required_flow_lh"] = req_flow_per_loop
                diag["pressure_drop_kpa"] = hyd["pressure_drop_kpa"]
                loop_diags.append(diag)

        diag_m = diagnose_manifold(loop_diags)
        return diag_m


class ZoneAreaSensor(BaseHeatingEntity):
    """Sensor powierzchni strefy / pomieszczenia w m²."""

    _attr_name = "Powierzchnia"
    _attr_native_unit_of_measurement = "m²"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:floor-plan"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, zone_id: str, z_data: dict) -> None:
        super().__init__(hass, entry, f"zone_{zone_id}_area")
        self.zone_id = zone_id
        self.z_data = z_data
        self._attr_device_info = get_zone_device_info(zone_id, z_data)

    @property
    def native_value(self) -> float:
        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        return float(z.get(ATTR_AREA, 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        area = float(z.get(ATTR_AREA, 0.0))
        loops_cnt = z.get("loops_count", len(z.get("loops", []))) or 1
        return {
            "zone_id": self.zone_id,
            "loops_count": loops_cnt,
            "loops": z.get("loops", []),
            "avg_loop_area_m2": round(area / loops_cnt, 2),
            "target_temp_c": z.get("target_temp", 21.0),
            "heat_load_w_m2": z.get("heat_load_w_m2", 45.0),
            "floor_covering": z.get(ATTR_FLOOR_COVERING, "tiles"),
        }


class ZoneTotalFlowSensor(BaseHeatingEntity):
    """Sensor sumarycznego przepływu wody dla całego pomieszczenia (strefy)."""

    _attr_name = "Sumaryczny przepływ wody"
    _attr_native_unit_of_measurement = "l/min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-pump"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, zone_id: str, z_data: dict) -> None:
        super().__init__(hass, entry, f"zone_{zone_id}_total_flow")
        self.zone_id = zone_id
        self.z_data = z_data
        self._attr_device_info = get_zone_device_info(zone_id, z_data)

    @property
    def native_value(self) -> float:
        """Sumaryczny przepływ we wszystkich pętlach pomieszczenia w l/min."""
        data = self.current_data
        total_lmin = 0.0
        z = data[CONF_ZONES].get(self.zone_id, self.z_data)
        zone_loops = z.get("loops", [])

        for loop_id, loop_data in data[CONF_LOOPS].items():
            if loop_data.get("zone_id") == self.zone_id or loop_id in zone_loops:
                flow_lh = data["rotameter_flows"].get(loop_id, loop_data.get(ATTR_ROTAMETER_FLOW_LH, 0.0))
                total_lmin += flow_lh / 60.0

        return round(total_lmin, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Dodatkowe jednostki: l/h, m³/h oraz rzeczywista moc oddawana."""
        val_lmin = self.native_value
        val_lh = round(val_lmin * 60.0, 1)
        val_m3h = round(val_lh / 1000.0, 3)

        # Rzeczywista moc cieplna ze strumienia wody przy standardowej delcie T = 6.0 K
        # Phi = (val_lh / 3600) * cp * delta_T
        power_w = round((val_lh / 3600.0) * WATER_SPECIFIC_HEAT * 6.0, 1) if val_lh > 0 else 0.0
        power_kw = round(power_w / 1000.0, 2)

        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        return {
            "flow_l_h": val_lh,
            "flow_m3_h": val_m3h,
            "loops_count": z.get("loops_count", len(z.get("loops", []))),
            "loops": z.get("loops", []),
            "actual_heat_power_w": power_w,
            "actual_heat_power_kw": power_kw,
            "delta_t_c": 6.0,
        }


class ZoneScreedInfoSensor(BaseHeatingEntity):
    """Sensor typu i grubości wylewki strefy."""

    _attr_name = "Typ i grubość wylewki"
    _attr_icon = "mdi:layers-triple"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, zone_id: str, z_data: dict) -> None:
        super().__init__(hass, entry, f"zone_{zone_id}_screed_info")
        self.zone_id = zone_id
        self.z_data = z_data
        self._attr_device_info = get_zone_device_info(zone_id, z_data)

    @property
    def native_value(self) -> str:
        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        screed_type = z.get(ATTR_SCREED_TYPE, "cement")
        thickness = z.get(ATTR_SCREED_THICKNESS, 50.0)
        type_name = SCREED_TYPES.get(screed_type, {}).get("name", screed_type)
        return f"{type_name} ({thickness} mm)"


class ZoneHeatOutputSensor(BaseHeatingEntity):
    """Sensor mocy grzewczej strefy w Watach."""

    _attr_name = "Zapotrzebowanie cieplne"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fire"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, zone_id: str, z_data: dict) -> None:
        super().__init__(hass, entry, f"zone_{zone_id}_heat_output")
        self.zone_id = zone_id
        self.z_data = z_data
        self._attr_device_info = get_zone_device_info(zone_id, z_data)

    @property
    def native_value(self) -> float:
        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        therm = calculate_thermal_properties(
            z.get(ATTR_AREA, 15.0),
            z.get(ATTR_SCREED_TYPE, "cement"),
            z.get(ATTR_SCREED_THICKNESS, 50.0),
            z.get(ATTR_FLOOR_COVERING, "tiles"),
            z.get("heat_load_w_m2", 45.0),
        )
        return therm["heat_output_w"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        w = self.native_value
        return {
            "heat_output_kw": round(w / 1000.0, 2),
            "heat_load_w_m2": z.get("heat_load_w_m2", 45.0),
            "area_m2": z.get(ATTR_AREA, 15.0),
            "zone_id": self.zone_id,
        }


class ZoneRequiredFlowSensor(BaseHeatingEntity):
    """Sensor wymaganego przepływu projektowego dla całej strefy."""

    _attr_name = "Wymagany przepływ projektowy"
    _attr_native_unit_of_measurement = "l/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:target"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, zone_id: str, z_data: dict) -> None:
        super().__init__(hass, entry, f"zone_{zone_id}_req_flow")
        self.zone_id = zone_id
        self.z_data = z_data
        self._attr_device_info = get_zone_device_info(zone_id, z_data)

    @property
    def native_value(self) -> float:
        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        therm = calculate_thermal_properties(
            z.get(ATTR_AREA, 15.0),
            z.get(ATTR_SCREED_TYPE, "cement"),
            z.get(ATTR_SCREED_THICKNESS, 50.0),
            z.get(ATTR_FLOOR_COVERING, "tiles"),
            z.get("heat_load_w_m2", 45.0),
        )
        return therm["required_flow_lh"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.native_value
        return {
            "required_flow_lmin": round(val / 60.0, 2),
            "required_flow_m3h": round(val / 1000.0, 3),
            "zone_id": self.zone_id,
        }


class ZoneScreedInertiaSensor(BaseHeatingEntity):
    """Sensor bezwładności termicznej i właściwości wylewki strefy."""

    _attr_name = "Bezwładność wylewki"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, zone_id: str, z_data: dict) -> None:
        super().__init__(hass, entry, f"zone_{zone_id}_screed_inertia")
        self.zone_id = zone_id
        self.z_data = z_data
        self._attr_device_info = get_zone_device_info(zone_id, z_data)

    @property
    def native_value(self) -> float:
        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        therm = calculate_thermal_properties(
            z.get(ATTR_AREA, 15.0),
            z.get(ATTR_SCREED_TYPE, "cement"),
            z.get(ATTR_SCREED_THICKNESS, 65.0),
            z.get(ATTR_FLOOR_COVERING, "tiles"),
            z.get("heat_load_w_m2", 45.0),
        )
        return therm["thermal_inertia_hours"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        z = self.current_data[CONF_ZONES].get(self.zone_id, self.z_data)
        therm = calculate_thermal_properties(
            z.get(ATTR_AREA, 15.0),
            z.get(ATTR_SCREED_TYPE, "cement"),
            z.get(ATTR_SCREED_THICKNESS, 65.0),
            z.get(ATTR_FLOOR_COVERING, "tiles"),
            z.get("heat_load_w_m2", 45.0),
        )
        screed_name = SCREED_TYPES.get(z.get(ATTR_SCREED_TYPE, "cement"), {}).get("name", "Wylewka")
        return {
            "screed_type": z.get(ATTR_SCREED_TYPE, "cement"),
            "screed_name": screed_name,
            "screed_thickness_mm": z.get(ATTR_SCREED_THICKNESS, 65.0),
            "floor_covering": z.get(ATTR_FLOOR_COVERING, "tiles"),
            "screed_mass_kg": therm["screed_mass_kg"],
            "heat_capacity_kwh_k": therm["heat_capacity_kwh_k"],
            "floor_thermal_resistance_m2k_w": therm["floor_thermal_resistance"],
        }


class LoopEstimatedLengthSensor(BaseHeatingEntity):
    """Sensor automatycznie wyliczający estymację długości pętli podłogówki."""

    _attr_name = "Estymowana długość pętli"
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:tape-measure"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict, zones_data: dict | None = None) -> None:
        super().__init__(hass, entry, f"loop_{loop_id}_length")
        self.loop_id = loop_id
        self.l_data = l_data
        self._attr_device_info = get_loop_device_info(loop_id, l_data, zones_data)

    @property
    def native_value(self) -> float:
        data = self.current_data
        loop = data[CONF_LOOPS].get(self.loop_id, self.l_data)
        zone = data[CONF_ZONES].get(loop.get(ATTR_ZONE_ID), {})
        area = loop.get("area_m2") or zone.get(ATTR_AREA, 15.0)
        loops_cnt = 1 if loop.get("area_m2") else loop.get("loops_in_zone", 1)

        return estimate_loop_length(
            area,
            loops_cnt,
            loop.get(ATTR_SPACING_CM, 15.0),
            loop.get(ATTR_APPROACH_LENGTH, 4.0),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.current_data
        loop = data[CONF_LOOPS].get(self.loop_id, self.l_data)
        zone = data[CONF_ZONES].get(loop.get(ATTR_ZONE_ID), {})
        pipe_info = PIPE_TYPES.get(loop.get(ATTR_PIPE_TYPE, "pex_16x2"), {})
        area = loop.get("area_m2") or zone.get(ATTR_AREA, 0.0)
        room_name = loop.get("zone_name") or zone.get("name", "")
        screed_type = loop.get("screed_type") or zone.get(ATTR_SCREED_TYPE, "cement")
        screed_thick = loop.get("screed_thickness_mm") or zone.get(ATTR_SCREED_THICKNESS, 50.0)
        return {
            "section_number": loop.get("section_number", 1),
            "room_name": room_name,
            "area_m2": area,
            "screed_type": screed_type,
            "screed_thickness_mm": screed_thick,
            "spacing_cm": loop.get(ATTR_SPACING_CM, 15.0),
            "approach_length_m": loop.get(ATTR_APPROACH_LENGTH, 4.0),
            "pipe_type": loop.get(ATTR_PIPE_TYPE, "pex_16x2"),
            "pipe_name": pipe_info.get("name", ""),
            "max_recommended_length_m": pipe_info.get("max_recommended_length_m", 100.0),
        }


class LoopPressureDropSensor(BaseHeatingEntity):
    """Sensor spadku ciśnienia na pojedynczej pętli."""

    _attr_name = "Spadek ciśnienia"
    _attr_native_unit_of_measurement = UnitOfPressure.KPA
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge-low"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict, zones_data: dict | None = None) -> None:
        super().__init__(hass, entry, f"loop_{loop_id}_pressure_drop")
        self.loop_id = loop_id
        self.l_data = l_data
        self._attr_device_info = get_loop_device_info(loop_id, l_data, zones_data)

    @property
    def native_value(self) -> float:
        data = self.current_data
        loop = data[CONF_LOOPS].get(self.loop_id, self.l_data)
        zone = data[CONF_ZONES].get(loop.get(ATTR_ZONE_ID), {})
        area = loop.get("area_m2") or zone.get(ATTR_AREA, 15.0)
        loops_cnt = 1 if loop.get("area_m2") else loop.get("loops_in_zone", 1)
        length = estimate_loop_length(
            area,
            loops_cnt,
            loop.get(ATTR_SPACING_CM, 15.0),
            loop.get(ATTR_APPROACH_LENGTH, 4.0),
        )
        flow_lh = data["rotameter_flows"].get(self.loop_id, 0.0)
        hyd = calculate_hydraulics(flow_lh, length, loop.get(ATTR_PIPE_TYPE, "pex_16x2"))
        return hyd["pressure_drop_kpa"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.native_value
        return {
            "pressure_drop_mbar": round(val * 10.0, 1),
        }


class LoopFlowVelocitySensor(BaseHeatingEntity):
    """Sensor prędkości przepływu cieczy w pętli."""

    _attr_name = "Prędkość czynnika"
    _attr_native_unit_of_measurement = UnitOfSpeed.METERS_PER_SECOND
    _attr_device_class = SensorDeviceClass.SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:speedometer"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict, zones_data: dict | None = None) -> None:
        super().__init__(hass, entry, f"loop_{loop_id}_velocity")
        self.loop_id = loop_id
        self.l_data = l_data
        self._attr_device_info = get_loop_device_info(loop_id, l_data, zones_data)

    @property
    def native_value(self) -> float:
        data = self.current_data
        loop = data[CONF_LOOPS].get(self.loop_id, self.l_data)
        zone = data[CONF_ZONES].get(loop.get(ATTR_ZONE_ID), {})
        area = loop.get("area_m2") or zone.get(ATTR_AREA, 15.0)
        loops_cnt = 1 if loop.get("area_m2") else loop.get("loops_in_zone", 1)
        length = estimate_loop_length(
            area,
            loops_cnt,
            loop.get(ATTR_SPACING_CM, 15.0),
            loop.get(ATTR_APPROACH_LENGTH, 4.0),
        )
        flow_lh = data["rotameter_flows"].get(self.loop_id, 0.0)
        hyd = calculate_hydraulics(flow_lh, length, loop.get(ATTR_PIPE_TYPE, "pex_16x2"))
        return hyd["flow_velocity_ms"]


class LoopBalancingStatusSensor(BaseHeatingEntity):
    """Sensor stanu zrównoważenia pętli podłogówki (dla innych aplikacji i diagnostyki)."""

    _attr_name = "Ocena regulacji pętli"
    _attr_icon = "mdi:scale-balance"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, loop_id: str, l_data: dict, zones_data: dict | None = None) -> None:
        super().__init__(hass, entry, f"loop_{loop_id}_status")
        self.loop_id = loop_id
        self.l_data = l_data
        self._attr_device_info = get_loop_device_info(loop_id, l_data, zones_data)

    @property
    def native_value(self) -> str:
        attrs = self.extra_state_attributes
        return str(attrs.get("status", "optymalny"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.current_data
        loop = data[CONF_LOOPS].get(self.loop_id, self.l_data)
        zone = data[CONF_ZONES].get(loop.get(ATTR_ZONE_ID), {})
        area = loop.get("area_m2") or zone.get(ATTR_AREA, 15.0)
        loops_cnt = 1 if loop.get("area_m2") else loop.get("loops_in_zone", 1)
        screed_type = loop.get("screed_type") or zone.get(ATTR_SCREED_TYPE, "cement")
        screed_thick = loop.get("screed_thickness_mm") or zone.get(ATTR_SCREED_THICKNESS, 50.0)

        length = estimate_loop_length(
            area,
            loops_cnt,
            loop.get(ATTR_SPACING_CM, 15.0),
            loop.get(ATTR_APPROACH_LENGTH, 4.0),
        )
        flow_lh = data["rotameter_flows"].get(self.loop_id, 0.0)
        hyd = calculate_hydraulics(flow_lh, length, loop.get(ATTR_PIPE_TYPE, "pex_16x2"))

        therm = calculate_thermal_properties(
            area,
            screed_type,
            screed_thick,
            loop.get(ATTR_FLOOR_COVERING, "tiles"),
            45.0,
        )
        req_flow_per_loop = therm["required_flow_lh"] / float(loops_cnt)

        diag = diagnose_loop(
            flow_lh,
            req_flow_per_loop,
            length,
            loop.get(ATTR_PIPE_TYPE, "pex_16x2"),
            hyd["pressure_drop_kpa"],
            hyd["flow_velocity_ms"],
        )

        return {
            "section_number": loop.get("section_number", 1),
            "room_name": loop.get("zone_name") or zone.get("name", ""),
            "current_flow_lh": flow_lh,
            "current_flow_lmin": round(flow_lh / 60.0, 2),
            "required_flow_lh": req_flow_per_loop,
            "required_flow_lmin": round(req_flow_per_loop / 60.0, 2),
            "deviation_pct": diag["deviation_pct"],
            "status": diag["status"],
            "status_details": diag["status_details"],
            "is_balanced": diag["is_balanced"],
            "warnings": diag["warnings"],
            "has_warnings": len(diag["warnings"]) > 0,
            "loop_length_m": length,
            "pressure_drop_kpa": hyd["pressure_drop_kpa"],
            "flow_velocity_ms": hyd["flow_velocity_ms"],
        }

