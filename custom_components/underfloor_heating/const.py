"""Stałe i definicje dla integracji Home Assistant Underfloor Heating (Zarządzanie Ogrzewaniem Podłogowym).

Wersja: 1.0.0
"""

from typing import Final

# Domena integracji w Home Assistant
DOMAIN: Final = "underfloor_heating"

# Wersja wtyczki
INTEGRATION_VERSION: Final = "1.0.5"

# Domyślne wartości konfiguracyjne
DEFAULT_NAME: Final = "Podłogówka"
DEFAULT_PIPE_TYPE: Final = "pex_16x2"
DEFAULT_PIPE_SPACING_CM: Final = 15.0
DEFAULT_APPROACH_LENGTH_M: Final = 4.0
DEFAULT_DELTA_T: Final = 5.0  # Różnica temperatur zasilania i powrotu w Kelwinach (K)
DEFAULT_SUPPLY_TEMP: Final = 35.0  # Domyślna temperatura zasilania w °C
DEFAULT_TARGET_ROOM_TEMP: Final = 21.0  # Domyślna temperatura strefy w °C

# Typy rur podłogowych z wewnętrzną średnicą (w metrach) i współczynnikiem chropowatości bezwzględnej (k w mm)
PIPE_TYPES: Final = {
    "pex_16x2": {
        "name": "PEX/PE-RT 16x2.0 mm",
        "outer_diameter_mm": 16.0,
        "wall_thickness_mm": 2.0,
        "inner_diameter_mm": 12.0,
        "max_recommended_length_m": 100.0,
        "absolute_roughness_mm": 0.007,
    },
    "pex_17x2": {
        "name": "PEX/PE-RT 17x2.0 mm",
        "outer_diameter_mm": 17.0,
        "wall_thickness_mm": 2.0,
        "inner_diameter_mm": 13.0,
        "max_recommended_length_m": 120.0,
        "absolute_roughness_mm": 0.007,
    },
    "pex_20x2": {
        "name": "PEX/PE-RT 20x2.0 mm",
        "outer_diameter_mm": 20.0,
        "wall_thickness_mm": 2.0,
        "inner_diameter_mm": 16.0,
        "max_recommended_length_m": 150.0,
        "absolute_roughness_mm": 0.007,
    },
}

# Typy wylewek: przewodność cieplna lambda (W/mK), gęstość rho (kg/m3), ciepło właściwe cp (J/kg*K)
SCREED_TYPES: Final = {
    "cement": {
        "name": "Wylewka cementowa tradycyjna",
        "conductivity": 1.4,  # W/(m*K)
        "density": 2000.0,  # kg/m3
        "specific_heat": 1000.0,  # J/(kg*K)
        "min_thickness_mm": 50.0,
        "recommended_thickness_mm": 65.0,
    },
    "anhydrite": {
        "name": "Wylewka anhydrytowa płynna",
        "conductivity": 1.9,  # W/(m*K)
        "density": 2150.0,  # kg/m3
        "specific_heat": 1000.0,  # J/(kg*K)
        "min_thickness_mm": 35.0,
        "recommended_thickness_mm": 45.0,
    },
    "dry_screed": {
        "name": "Sucha zabudowa (np. płyty gipsowo-włóknowe)",
        "conductivity": 0.32,  # W/(m*K)
        "density": 1150.0,  # kg/m3
        "specific_heat": 1100.0,  # J/(kg*K)
        "min_thickness_mm": 20.0,
        "recommended_thickness_mm": 25.0,
    },
}

# Typy wykończenia podłogi (opór cieplny R w m2*K/W)
FLOOR_COVERINGS: Final = {
    "tiles": {"name": "Płytki ceramiczne / gres", "thermal_resistance": 0.015},
    "vinyl_glue": {"name": "Panele winylowe klejone", "thermal_resistance": 0.025},
    "laminate": {"name": "Panele laminowane na podkładzie", "thermal_resistance": 0.075},
    "wood_parquet": {"name": "Parkiet drewniany klejony (10-14mm)", "thermal_resistance": 0.100},
    "carpet": {"name": "Wykładzina dywanowa cienka", "thermal_resistance": 0.120},
}

# Właściwości fizyczne nośnika ciepła (woda w temp ~35°C)
WATER_DENSITY: Final = 994.0  # kg/m3 przy 35°C
WATER_SPECIFIC_HEAT: Final = 4178.0  # J/(kg*K)
WATER_KINEMATIC_VISCOSITY: Final = 0.724e-6  # m2/s przy 35°C

# Klucze konfiguracji
CONF_MANIFOLDS: Final = "manifolds"
CONF_ZONES: Final = "zones"
CONF_LOOPS: Final = "loops"

# Klucze parametrów
ATTR_MANIFOLD_ID: Final = "manifold_id"
ATTR_ZONE_ID: Final = "zone_id"
ATTR_LOOP_ID: Final = "loop_id"
ATTR_NAME: Final = "name"
ATTR_AREA: Final = "area_m2"
ATTR_LOOPS_COUNT: Final = "loops_count"
ATTR_PIPE_TYPE: Final = "pipe_type"
ATTR_SPACING_CM: Final = "spacing_cm"
ATTR_APPROACH_LENGTH: Final = "approach_length_m"
ATTR_ESTIMATED_LENGTH: Final = "estimated_length_m"
ATTR_SCREED_TYPE: Final = "screed_type"
ATTR_SCREED_THICKNESS: Final = "screed_thickness_mm"
ATTR_FLOOR_COVERING: Final = "floor_covering"
ATTR_TARGET_TEMP: Final = "target_temp"
ATTR_ROTAMETER_FLOW_LH: Final = "rotameter_flow_lh"
ATTR_ROTAMETER_FLOW_LMIN: Final = "rotameter_flow_lmin"
ATTR_REQUIRED_FLOW_LH: Final = "required_flow_lh"
ATTR_REQUIRED_FLOW_LMIN: Final = "required_flow_lmin"
ATTR_PRESSURE_DROP_KPA: Final = "pressure_drop_kpa"
ATTR_FLOW_VELOCITY_MS: Final = "flow_velocity_ms"
ATTR_HEAT_OUTPUT_W: Final = "heat_output_w"
ATTR_THERMAL_INERTIA_HOURS: Final = "thermal_inertia_hours"
ATTR_STATUS: Final = "status"
ATTR_STATUS_DETAILS: Final = "status_details"
ATTR_WARNINGS: Final = "warnings"

# Statusy bilansowania hydraulicznego
STATUS_OPTIMAL: Final = "optymalny"
STATUS_ACCEPTABLE: Final = "akceptowalny"
STATUS_UNDERFLOW: Final = "zdławiony"
STATUS_OVERFLOW: Final = "przewymiarowany"
STATUS_CRITICAL: Final = "krytyczny"

