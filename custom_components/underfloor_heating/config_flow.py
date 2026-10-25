"""Kreator konfiguracji (Config Flow & Options Flow) dla integracji Ogrzewanie Podłogowe.

Umożliwia pełne konfigurowanie rozdzielaczy, stref grzewczych, typów wylewek
oraz pętli podłogówki z poziomu interfejsu graficznego Home Assistant.

Wersja: 1.0.0
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .calculations import estimate_loop_length
from .const import (
    ATTR_APPROACH_LENGTH,
    ATTR_AREA,
    ATTR_FLOOR_COVERING,
    ATTR_NAME,
    ATTR_PIPE_TYPE,
    ATTR_ROTAMETER_FLOW_LH,
    ATTR_SCREED_THICKNESS,
    ATTR_SCREED_TYPE,
    ATTR_SPACING_CM,
    CONF_LOOPS,
    CONF_MANIFOLDS,
    CONF_ZONES,
    DEFAULT_APPROACH_LENGTH_M,
    DEFAULT_NAME,
    DEFAULT_PIPE_SPACING_CM,
    DEFAULT_PIPE_TYPE,
    DOMAIN,
    FLOOR_COVERINGS,
    PIPE_TYPES,
    SCREED_TYPES,
)

_LOGGER = logging.getLogger(__name__)


class UnderfloorHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obsługa kreatora dodawania integracji Underfloor Heating."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Pierwszy krok konfiguracji integracji."""
        errors: dict[str, str] = {}

        if user_input is not None:
            title = user_input.get(ATTR_NAME, DEFAULT_NAME)

            # Przykładowe początkowe dane (rozdzielacz domyślny i pierwsza strefa)
            default_manifold_id = "rozdzielacz_parter"
            default_zone_id = "salon"
            default_loop_id = "petla_salon_1"

            initial_data = {
                CONF_MANIFOLDS: {
                    default_manifold_id: {
                        "name": "Rozdzielacz Parter",
                        "location": "Kotłownia / Parter",
                        "sections_count": 8,
                    }
                },
                CONF_ZONES: {
                    default_zone_id: {
                        "name": "Salon z jadalnią",
                        "area_m2": 36.0,
                        "screed_type": "anhydrite",
                        "screed_thickness_mm": 50.0,
                        "floor_covering": "tiles",
                        "heat_load_w_m2": 45.0,
                        "target_temp": 21.5,
                    }
                },
                CONF_LOOPS: {
                    default_loop_id: {
                        "name": "Salon Pętla 1",
                        "manifold_id": default_manifold_id,
                        "zone_id": default_zone_id,
                        "section_number": 1,
                        "pipe_type": "pex_16x2",
                        "spacing_cm": 15.0,
                        "approach_length_m": 4.0,
                        "loops_in_zone": 2,
                        ATTR_ROTAMETER_FLOW_LH: 110.0,
                    },
                    "petla_salon_2": {
                        "name": "Salon Pętla 2",
                        "manifold_id": default_manifold_id,
                        "zone_id": default_zone_id,
                        "section_number": 2,
                        "pipe_type": "pex_16x2",
                        "spacing_cm": 15.0,
                        "approach_length_m": 5.0,
                        "loops_in_zone": 2,
                        ATTR_ROTAMETER_FLOW_LH: 115.0,
                    },
                },
            }

            return self.async_create_entry(title=title, data=initial_data)

        schema = vol.Schema(
            {
                vol.Required(ATTR_NAME, default=DEFAULT_NAME): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Pobiera menedżer opcji dla istniejącej integracji."""
        return UnderfloorHeatingOptionsFlowHandler(config_entry)


class UnderfloorHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Zarządzanie dodawaniem i edycją rozdzielaczy, stref i pętli."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Inicjalizacja procedury edycji opcji."""
        self.config_entry = config_entry
        self.options = copy.deepcopy(dict(config_entry.options or config_entry.data))
        self.options.setdefault(CONF_MANIFOLDS, {})
        self.options.setdefault(CONF_ZONES, {})
        self.options.setdefault(CONF_LOOPS, {})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Główne menu edycji konfiguracji podłogówki."""
        actions = {
            "add_manifold": "Dodaj nowy rozdzielacz",
            "add_zone": "Dodaj nową strefę / pomieszczenie (wylewka, pow.)",
            "add_loop": "Dodaj nową pętlę podłogówki do rozdzielacza",
            "view_summary": "Zapisz i zastosuj zmiany",
        }

        if user_input is not None:
            choice = user_input.get("action")
            if choice == "add_manifold":
                return await self.async_step_add_manifold()
            if choice == "add_zone":
                return await self.async_step_add_zone()
            if choice == "add_loop":
                return await self.async_step_add_loop()
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required("action", default="add_loop"): vol.In(actions),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_add_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz dodawania rozdzielacza."""
        errors: dict[str, str] = {}
        if user_input is not None:
            m_id = user_input["id"].strip().lower().replace(" ", "_")
            self.options[CONF_MANIFOLDS][m_id] = {
                "name": user_input["name"],
                "location": user_input.get("location", ""),
                "sections_count": int(user_input.get("sections_count", 8)),
            }
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("id", default="rozdzielacz_pietro"): str,
                vol.Required("name", default="Rozdzielacz Piętro"): str,
                vol.Optional("location", default="Garderoba / Piętro"): str,
                vol.Required("sections_count", default=8): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="add_manifold", data_schema=schema, errors=errors)

    async def async_step_add_zone(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz dodawania strefy podłogówki (z wylewką i parametrami)."""
        errors: dict[str, str] = {}
        screed_choices = {k: v["name"] for k, v in SCREED_TYPES.items()}
        covering_choices = {k: v["name"] for k, v in FLOOR_COVERINGS.items()}

        if user_input is not None:
            z_id = user_input["id"].strip().lower().replace(" ", "_")
            self.options[CONF_ZONES][z_id] = {
                "name": user_input["name"],
                "area_m2": float(user_input["area_m2"]),
                "screed_type": user_input["screed_type"],
                "screed_thickness_mm": float(user_input["screed_thickness_mm"]),
                "floor_covering": user_input["floor_covering"],
                "heat_load_w_m2": float(user_input.get("heat_load_w_m2", 45.0)),
                "target_temp": float(user_input.get("target_temp", 21.0)),
            }
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("id", default="lazienka_pietro"): str,
                vol.Required("name", default="Łazienka Piętro"): str,
                vol.Required("area_m2", default=10.0): vol.Coerce(float),
                vol.Required("screed_type", default="cement"): vol.In(screed_choices),
                vol.Required("screed_thickness_mm", default=65.0): vol.Coerce(float),
                vol.Required("floor_covering", default="tiles"): vol.In(covering_choices),
                vol.Optional("heat_load_w_m2", default=60.0): vol.Coerce(float),
                vol.Optional("target_temp", default=24.0): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="add_zone", data_schema=schema, errors=errors)

    async def async_step_add_loop(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz dodawania pojedynczej pętli podłogówki do rozdzielacza."""
        errors: dict[str, str] = {}

        manifolds = {m_id: data["name"] for m_id, data in self.options[CONF_MANIFOLDS].items()}
        zones = {z_id: data["name"] for z_id, data in self.options[CONF_ZONES].items()}
        pipe_choices = {k: v["name"] for k, v in PIPE_TYPES.items()}

        if not manifolds or not zones:
            errors["base"] = "Najpierw musisz dodać co najmniej jeden rozdzielacz i jedną strefę."
            return await self.async_step_init()

        if user_input is not None:
            l_id = user_input["id"].strip().lower().replace(" ", "_")
            self.options[CONF_LOOPS][l_id] = {
                "name": user_input["name"],
                "manifold_id": user_input["manifold_id"],
                "zone_id": user_input["zone_id"],
                "section_number": int(user_input.get("section_number", 1)),
                "pipe_type": user_input["pipe_type"],
                "spacing_cm": float(user_input["spacing_cm"]),
                "approach_length_m": float(user_input["approach_length_m"]),
                "loops_in_zone": int(user_input.get("loops_in_zone", 1)),
                ATTR_ROTAMETER_FLOW_LH: float(user_input.get(ATTR_ROTAMETER_FLOW_LH, 90.0)),
            }
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("id", default="petla_lazienka_1"): str,
                vol.Required("name", default="Łazienka Pętla 1"): str,
                vol.Required("manifold_id"): vol.In(manifolds),
                vol.Required("zone_id"): vol.In(zones),
                vol.Required("section_number", default=1): vol.Coerce(int),
                vol.Required("pipe_type", default=DEFAULT_PIPE_TYPE): vol.In(pipe_choices),
                vol.Required("spacing_cm", default=10.0): vol.Coerce(float),
                vol.Required("approach_length_m", default=3.0): vol.Coerce(float),
                vol.Required("loops_in_zone", default=1): vol.Coerce(int),
                vol.Required(ATTR_ROTAMETER_FLOW_LH, default=95.0): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="add_loop", data_schema=schema, errors=errors)

