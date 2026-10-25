"""Kreator konfiguracji (Config Flow & Options Flow) dla integracji Ogrzewanie Podłogowe.

Umożliwia pełne konfigurowanie i modyfikację rozdzielaczy, stref grzewczych,
typów wylewek oraz pętli podłogówki zarówno przy pierwszym uruchomieniu,
jak i w dowolnym momencie po dodaniu integracji w Home Assistant.

Wersja: 1.0.4
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
            init_mode = user_input.get("initial_setup_mode", "demo")

            if init_mode == "demo":
                default_manifold_id = "parter"
                default_zone_id = "biuro"

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
                            "name": "Biuro",
                            "area_m2": 25.0,
                            "screed_type": "anhydrite",
                            "screed_thickness_mm": 50.0,
                            "floor_covering": "tiles",
                            "heat_load_w_m2": 45.0,
                            "target_temp": 21.5,
                        }
                    },
                    CONF_LOOPS: {
                        "petla_biuro_1": {
                            "name": "Biuro Pętla 1",
                            "manifold_id": default_manifold_id,
                            "zone_id": default_zone_id,
                            "section_number": 1,
                            "pipe_type": "pex_16x2",
                            "spacing_cm": 15.0,
                            "approach_length_m": 4.0,
                            "loops_in_zone": 2,
                            ATTR_ROTAMETER_FLOW_LH: 110.0,
                        },
                        "petla_biuro_2": {
                            "name": "Biuro Pętla 2",
                            "manifold_id": default_manifold_id,
                            "zone_id": default_zone_id,
                            "section_number": 2,
                            "pipe_type": "pex_16x2",
                            "spacing_cm": 15.0,
                            "approach_length_m": 5.0,
                            "loops_in_zone": 2,
                            ATTR_ROTAMETER_FLOW_LH: 110.0,
                        },
                    },
                }
                return self.async_create_entry(title=title, data=initial_data)
            else:
                return self.async_create_entry(
                    title=title,
                    data={CONF_MANIFOLDS: {}, CONF_ZONES: {}, CONF_LOOPS: {}},
                )

        schema = vol.Schema(
            {
                vol.Required(ATTR_NAME, default=DEFAULT_NAME): str,
                vol.Required("initial_setup_mode", default="demo"): vol.In(
                    {
                        "demo": "Utwórz przykładowy rozdzielacz i strefę (zalecane na start)",
                        "empty": "Czysta instalacja (skonfiguruję ręcznie od podstaw)",
                    }
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Pobiera menedżer opcji dla istniejącej integracji."""
        return UnderfloorHeatingOptionsFlowHandler(config_entry)


class UnderfloorHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Zarządzanie dodawaniem, edycją i usuwaniem rozdzielaczy, stref i pętli w dowolnym momencie."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Inicjalizacja procedury edycji opcji."""
        try:
            super().__init__(config_entry)
        except TypeError:
            super().__init__()
        self._config_entry = config_entry
        self.options = copy.deepcopy(dict(config_entry.options or config_entry.data))
        self.options.setdefault(CONF_MANIFOLDS, {})
        self.options.setdefault(CONF_ZONES, {})
        self.options.setdefault(CONF_LOOPS, {})
        self._selected_item_id: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Główne menu edycji konfiguracji podłogówki."""
        actions = {
            "add_loop": "➕ Dodaj nową pętlę podłogówki",
            "edit_loop": "🔧 Edytuj parametry pętli (rozstaw, rotametr, rura)",
            "remove_loop": "🗑️ Usuń pętlę podłogówki",
            "add_zone": "🏠 Dodaj nową strefę (pomieszczenie, metraż m², wylewka)",
            "edit_zone": "✏️ Edytuj strefę (zmień powierzchnię m², wylewkę)",
            "remove_zone": "🗑️ Usuń strefę / pomieszczenie",
            "add_manifold": "🎛️ Dodaj nowy rozdzielacz",
            "edit_manifold": "⚙️ Edytuj rozdzielacz",
            "remove_manifold": "🗑️ Usuń rozdzielacz",
            "view_summary": "💾 Zapisz i zastosuj wszystkie zmiany",
        }

        if user_input is not None:
            choice = user_input.get("action")
            if choice == "add_loop":
                return await self.async_step_add_loop()
            if choice == "edit_loop":
                return await self.async_step_select_edit_loop()
            if choice == "remove_loop":
                return await self.async_step_remove_loop()
            if choice == "add_zone":
                return await self.async_step_add_zone()
            if choice == "edit_zone":
                return await self.async_step_select_edit_zone()
            if choice == "remove_zone":
                return await self.async_step_remove_zone()
            if choice == "add_manifold":
                return await self.async_step_add_manifold()
            if choice == "edit_manifold":
                return await self.async_step_select_edit_manifold()
            if choice == "remove_manifold":
                return await self.async_step_remove_manifold()
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required("action", default="edit_zone"): vol.In(actions),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    # ================= STREFY / POMIESZCZENIA =================

    async def async_step_add_zone(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz dodawania strefy podłogówki (z wylewką i metrażem)."""
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
                vol.Required("id", default="salon_parter"): str,
                vol.Required("name", default="Salon"): str,
                vol.Required("area_m2", default=35.0): vol.Coerce(float),
                vol.Required("screed_type", default="anhydrite"): vol.In(screed_choices),
                vol.Required("screed_thickness_mm", default=50.0): vol.Coerce(float),
                vol.Required("floor_covering", default="tiles"): vol.In(covering_choices),
                vol.Optional("heat_load_w_m2", default=45.0): vol.Coerce(float),
                vol.Optional("target_temp", default=21.5): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="add_zone", data_schema=schema, errors=errors)

    async def async_step_select_edit_zone(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybór strefy do edycji metrażu lub wylewki."""
        zones = {z_id: f"{z['name']} (obecnie: {z.get('area_m2', 0)} m²)" for z_id, z in self.options[CONF_ZONES].items()}
        if not zones:
            return await self.async_step_init()

        if user_input is not None:
            self._selected_item_id = user_input["zone_id"]
            return await self.async_step_edit_zone_details()

        schema = vol.Schema({vol.Required("zone_id"): vol.In(zones)})
        return self.async_show_form(step_id="select_edit_zone", data_schema=schema)

    async def async_step_edit_zone_details(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz edycji parametrów wybranej strefy (powierzchnia, wylewka itp.)."""
        z_id = self._selected_item_id
        z_data = self.options[CONF_ZONES].get(z_id, {})
        screed_choices = {k: v["name"] for k, v in SCREED_TYPES.items()}
        covering_choices = {k: v["name"] for k, v in FLOOR_COVERINGS.items()}

        if user_input is not None:
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
                vol.Required("name", default=z_data.get("name", z_id)): str,
                vol.Required("area_m2", default=float(z_data.get("area_m2", 20.0))): vol.Coerce(float),
                vol.Required("screed_type", default=z_data.get("screed_type", "cement")): vol.In(screed_choices),
                vol.Required("screed_thickness_mm", default=float(z_data.get("screed_thickness_mm", 65.0))): vol.Coerce(float),
                vol.Required("floor_covering", default=z_data.get("floor_covering", "tiles")): vol.In(covering_choices),
                vol.Optional("heat_load_w_m2", default=float(z_data.get("heat_load_w_m2", 45.0))): vol.Coerce(float),
                vol.Optional("target_temp", default=float(z_data.get("target_temp", 21.0))): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="edit_zone_details", data_schema=schema)

    async def async_step_remove_zone(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Usunięcie strefy."""
        zones = {z_id: f"{z['name']} ({z.get('area_m2', 0)} m²)" for z_id, z in self.options[CONF_ZONES].items()}
        if not zones:
            return await self.async_step_init()

        if user_input is not None:
            z_id = user_input["zone_id"]
            self.options[CONF_ZONES].pop(z_id, None)
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("zone_id"): vol.In(zones)})
        return self.async_show_form(step_id="remove_zone", data_schema=schema)

    # ================= PĘTLE PODŁOGÓWKI =================

    async def async_step_add_loop(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz dodawania pętli podłogówki."""
        errors: dict[str, str] = {}
        manifolds = {m_id: data["name"] for m_id, data in self.options[CONF_MANIFOLDS].items()}
        zones = {z_id: f"{data['name']} ({data.get('area_m2', 0)} m²)" for z_id, data in self.options[CONF_ZONES].items()}
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
                vol.Required("id", default=f"petla_{len(self.options[CONF_LOOPS]) + 1}"): str,
                vol.Required("name", default=f"Pętla {len(self.options[CONF_LOOPS]) + 1}"): str,
                vol.Required("manifold_id"): vol.In(manifolds),
                vol.Required("zone_id"): vol.In(zones),
                vol.Required("section_number", default=len(self.options[CONF_LOOPS]) + 1): vol.Coerce(int),
                vol.Required("pipe_type", default=DEFAULT_PIPE_TYPE): vol.In(pipe_choices),
                vol.Required("spacing_cm", default=DEFAULT_PIPE_SPACING_CM): vol.Coerce(float),
                vol.Required("approach_length_m", default=DEFAULT_APPROACH_LENGTH_M): vol.Coerce(float),
                vol.Required("loops_in_zone", default=1): vol.Coerce(int),
                vol.Required(ATTR_ROTAMETER_FLOW_LH, default=95.0): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="add_loop", data_schema=schema, errors=errors)

    async def async_step_select_edit_loop(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybór pętli do edycji parametrów."""
        loops = {l_id: f"{l['name']} (Sekcja {l.get('section_number', '?')})" for l_id, l in self.options[CONF_LOOPS].items()}
        if not loops:
            return await self.async_step_init()

        if user_input is not None:
            self._selected_item_id = user_input["loop_id"]
            return await self.async_step_edit_loop_details()

        schema = vol.Schema({vol.Required("loop_id"): vol.In(loops)})
        return self.async_show_form(step_id="select_edit_loop", data_schema=schema)

    async def async_step_edit_loop_details(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Edycja parametrów pętli (rozstaw, rura, podejście, rotametr)."""
        l_id = self._selected_item_id
        l_data = self.options[CONF_LOOPS].get(l_id, {})
        manifolds = {m_id: data["name"] for m_id, data in self.options[CONF_MANIFOLDS].items()}
        zones = {z_id: f"{data['name']} ({data.get('area_m2', 0)} m²)" for z_id, data in self.options[CONF_ZONES].items()}
        pipe_choices = {k: v["name"] for k, v in PIPE_TYPES.items()}

        if user_input is not None:
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
                vol.Required("name", default=l_data.get("name", l_id)): str,
                vol.Required("manifold_id", default=l_data.get("manifold_id")): vol.In(manifolds),
                vol.Required("zone_id", default=l_data.get("zone_id")): vol.In(zones),
                vol.Required("section_number", default=int(l_data.get("section_number", 1))): vol.Coerce(int),
                vol.Required("pipe_type", default=l_data.get("pipe_type", DEFAULT_PIPE_TYPE)): vol.In(pipe_choices),
                vol.Required("spacing_cm", default=float(l_data.get("spacing_cm", 15.0))): vol.Coerce(float),
                vol.Required("approach_length_m", default=float(l_data.get("approach_length_m", 4.0))): vol.Coerce(float),
                vol.Required("loops_in_zone", default=int(l_data.get("loops_in_zone", 1))): vol.Coerce(int),
                vol.Required(ATTR_ROTAMETER_FLOW_LH, default=float(l_data.get(ATTR_ROTAMETER_FLOW_LH, 90.0))): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="edit_loop_details", data_schema=schema)

    async def async_step_remove_loop(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Usunięcie pętli."""
        loops = {l_id: f"{l['name']} (Sekcja {l.get('section_number', '?')})" for l_id, l in self.options[CONF_LOOPS].items()}
        if not loops:
            return await self.async_step_init()

        if user_input is not None:
            l_id = user_input["loop_id"]
            self.options[CONF_LOOPS].pop(l_id, None)
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("loop_id"): vol.In(loops)})
        return self.async_show_form(step_id="remove_loop", data_schema=schema)

    # ================= ROZDZIELACZE =================

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

    async def async_step_select_edit_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybór rozdzielacza do edycji."""
        manifolds = {m_id: f"{m['name']} ({m.get('sections_count', 8)} sekcji)" for m_id, m in self.options[CONF_MANIFOLDS].items()}
        if not manifolds:
            return await self.async_step_init()

        if user_input is not None:
            self._selected_item_id = user_input["manifold_id"]
            return await self.async_step_edit_manifold_details()

        schema = vol.Schema({vol.Required("manifold_id"): vol.In(manifolds)})
        return self.async_show_form(step_id="select_edit_manifold", data_schema=schema)

    async def async_step_edit_manifold_details(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Edycja parametrów rozdzielacza."""
        m_id = self._selected_item_id
        m_data = self.options[CONF_MANIFOLDS].get(m_id, {})

        if user_input is not None:
            self.options[CONF_MANIFOLDS][m_id] = {
                "name": user_input["name"],
                "location": user_input.get("location", ""),
                "sections_count": int(user_input.get("sections_count", 8)),
            }
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("name", default=m_data.get("name", m_id)): str,
                vol.Optional("location", default=m_data.get("location", "")): str,
                vol.Required("sections_count", default=int(m_data.get("sections_count", 8))): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="edit_manifold_details", data_schema=schema)

    async def async_step_remove_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Usunięcie rozdzielacza."""
        manifolds = {m_id: m['name'] for m_id, m in self.options[CONF_MANIFOLDS].items()}
        if not manifolds:
            return await self.async_step_init()

        if user_input is not None:
            m_id = user_input["manifold_id"]
            self.options[CONF_MANIFOLDS].pop(m_id, None)
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("manifold_id"): vol.In(manifolds)})
        return self.async_show_form(step_id="remove_manifold", data_schema=schema)
