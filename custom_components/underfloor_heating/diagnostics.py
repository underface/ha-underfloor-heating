"""Eksport danych diagnostycznych dla integracji Ogrzewanie Podłogowe.

Umożliwia pobranie pełnego raportu hydraulicznego i termicznego instalacji
przez interfejs diagnostyki Home Assistant (Download Diagnostics) oraz API.

Wersja: 1.0.0
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

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
    ATTR_ROTAMETER_FLOW_LH,
    ATTR_SCREED_THICKNESS,
    ATTR_SCREED_TYPE,
    ATTR_SPACING_CM,
    CONF_LOOPS,
    CONF_MANIFOLDS,
    CONF_ZONES,
    DOMAIN,
    PIPE_TYPES,
    SCREED_TYPES,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Generuje kompletny raport inżynieryjny instalacji podłogówki."""
    data = hass.data[DOMAIN][entry.entry_id]

    report: dict[str, Any] = {
        "integration_version": "1.0.0",
        "entry_id": entry.entry_id,
        "manifolds": {},
        "zones": {},
        "loops": {},
        "summary": {},
    }

    total_installed_flow_lh = 0.0
    total_required_flow_lh = 0.0
    total_area_m2 = 0.0
    total_pipe_length_m = 0.0

    # Analiza stref
    for z_id, z_data in data[CONF_ZONES].items():
        area = float(z_data.get(ATTR_AREA, 0.0))
        total_area_m2 += area
        therm = calculate_thermal_properties(
            area,
            z_data.get(ATTR_SCREED_TYPE, "cement"),
            float(z_data.get(ATTR_SCREED_THICKNESS, 65.0)),
            z_data.get(ATTR_FLOOR_COVERING, "tiles"),
            float(z_data.get("heat_load_w_m2", 45.0)),
        )
        report["zones"][z_id] = {
            "name": z_data.get("name", z_id),
            "area_m2": area,
            "screed_info": {
                "type": z_data.get(ATTR_SCREED_TYPE, "cement"),
                "thickness_mm": z_data.get(ATTR_SCREED_THICKNESS, 65.0),
                "mass_kg": therm["screed_mass_kg"],
                "heat_capacity_kwh_k": therm["heat_capacity_kwh_k"],
                "thermal_inertia_hours": therm["thermal_inertia_hours"],
            },
            "floor_covering": z_data.get(ATTR_FLOOR_COVERING, "tiles"),
            "thermal_resistance_m2k_w": therm["floor_thermal_resistance"],
            "heat_output_w": therm["heat_output_w"],
            "required_flow_lh": therm["required_flow_lh"],
            "required_flow_lmin": therm["required_flow_lmin"],
        }

    # Analiza pętli
    for l_id, l_data in data[CONF_LOOPS].items():
        z_id = l_data.get("zone_id")
        z_data = data[CONF_ZONES].get(z_id, {})
        loops_in_zone = max(l_data.get("loops_in_zone", 1), 1)

        length = estimate_loop_length(
            float(z_data.get(ATTR_AREA, 15.0)),
            loops_in_zone,
            float(l_data.get(ATTR_SPACING_CM, 15.0)),
            float(l_data.get(ATTR_APPROACH_LENGTH, 4.0)),
        )
        total_pipe_length_m += length

        flow_lh = float(data["rotameter_flows"].get(l_id, l_data.get(ATTR_ROTAMETER_FLOW_LH, 90.0)))
        total_installed_flow_lh += flow_lh

        hyd = calculate_hydraulics(flow_lh, length, l_data.get(ATTR_PIPE_TYPE, "pex_16x2"))

        # Wymagany przepływ pętli
        zone_req = report["zones"].get(z_id, {}).get("required_flow_lh", 100.0)
        req_flow_per_loop = round(zone_req / float(loops_in_zone), 1)
        total_required_flow_lh += req_flow_per_loop

        diag = diagnose_loop(
            flow_lh,
            req_flow_per_loop,
            length,
            l_data.get(ATTR_PIPE_TYPE, "pex_16x2"),
            hyd["pressure_drop_kpa"],
            hyd["flow_velocity_ms"],
        )

        report["loops"][l_id] = {
            "name": l_data.get("name", l_id),
            "manifold_id": l_data.get("manifold_id"),
            "zone_id": z_id,
            "section_number": l_data.get("section_number", 1),
            "estimated_length_m": length,
            "pipe_type": l_data.get(ATTR_PIPE_TYPE, "pex_16x2"),
            "spacing_cm": l_data.get(ATTR_SPACING_CM, 15.0),
            "current_flow_lh": flow_lh,
            "current_flow_lmin": round(flow_lh / 60.0, 2),
            "required_flow_lh": req_flow_per_loop,
            "required_flow_lmin": round(req_flow_per_loop / 60.0, 2),
            "pressure_drop_kpa": hyd["pressure_drop_kpa"],
            "flow_velocity_ms": hyd["flow_velocity_ms"],
            "reynolds_number": hyd["reynolds_number"],
            "status": diag["status"],
            "status_details": diag["status_details"],
            "is_balanced": diag["is_balanced"],
            "warnings": diag["warnings"],
        }

    # Analiza rozdzielaczy
    for m_id, m_data in data[CONF_MANIFOLDS].items():
        loops_of_m = [diag for diag in report["loops"].values() if diag["manifold_id"] == m_id]
        diag_m = diagnose_manifold(loops_of_m)
        report["manifolds"][m_id] = {
            "name": m_data.get("name", m_id),
            "location": m_data.get("location", ""),
            "sections_count": m_data.get("sections_count", 8),
            "active_loops_count": len(loops_of_m),
            "diagnostics": diag_m,
        }

    report["summary"] = {
        "total_heated_area_m2": round(total_area_m2, 1),
        "total_pipe_length_m": round(total_pipe_length_m, 1),
        "total_installed_flow_lh": round(total_installed_flow_lh, 1),
        "total_required_flow_lh": round(total_required_flow_lh, 1),
        "manifolds_count": len(data[CONF_MANIFOLDS]),
        "zones_count": len(data[CONF_ZONES]),
        "loops_count": len(data[CONF_LOOPS]),
    }

    return report

