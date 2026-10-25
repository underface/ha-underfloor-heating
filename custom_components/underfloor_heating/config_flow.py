"""Kreator konfiguracji w naturalnej hierarchii: Rozdzielacz > Strefa > Pętle.

Umożliwia proste i intuicyjne dodawanie oraz edycję ogrzewania podłogowego:
1. Rozdzielacz (kondygnacja / szafka)
2. Strefa (pomieszczenie, metraż m², typ i grubość jastrychu, liczba pętli)
3. Pętle strefy (automatyczne wygenerowanie z podaniem nastaw przepływu rotametrów l/h)

Wersja: 1.0.5
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .calculations import calculate_thermal_properties, estimate_loop_length
from .const import (
    ATTR_APPROACH_LENGTH,
    ATTR_AREA,
    ATTR_FLOOR_COVERING,
    ATTR_LOOP_ID,
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
    """Kreator pierwszego dodawania integracji."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Krok 1: Podstawowa nazwa instalacji."""
        errors: dict[str, str] = {}

        if user_input is not None:
            title = user_input.get(ATTR_NAME, DEFAULT_NAME)
            init_mode = user_input.get("initial_setup_mode", "demo")

            if init_mode == "demo":
                default_manifold_id = "parter"
                default_zone_id = "salon"

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
                            "name": "Salon",
                            "manifold_id": default_manifold_id,
                            "area_m2": 37.0,
                            "screed_type": "cement",
                            "screed_thickness_mm": 50.0,
                            "loops_count": 2,
                            "floor_covering": "laminate",
                            "heat_load_w_m2": 45.0,
                            "target_temp": 21.5,
                        }
                    },
                    CONF_LOOPS: {
                        "petla_salon_1": {
                            "name": "Salon - Pętla 1",
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
                            "name": "Salon - Pętla 2",
                            "manifold_id": default_manifold_id,
                            "zone_id": default_zone_id,
                            "section_number": 2,
                            "pipe_type": "pex_16x2",
                            "spacing_cm": 15.0,
                            "approach_length_m": 4.0,
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
                        "demo": "Utwórz domyślny rozdzielacz i strefę",
                        "empty": "Czysta instalacja (skonfiguruję własne strefy)",
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
    """Zarządzanie hierarchią: Rozdzielacz > Strefa > Pętle."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        try:
            super().__init__(config_entry)
        except TypeError:
            super().__init__()
        self._config_entry = config_entry
        self.options = copy.deepcopy(dict(config_entry.options or config_entry.data))
        self.options.setdefault(CONF_MANIFOLDS, {})
        self.options.setdefault(CONF_ZONES, {})
        self.options.setdefault(CONF_LOOPS, {})

        # Pamięć podręczna kreatora strefy
        self._temp_zone_data: dict[str, Any] = {}
        self._selected_zone_id: str | None = None
        self._selected_manifold_id: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Główne, proste menu zarządzania instalacją."""
        actions = {
            "add_zone": "➕ Dodaj strefę (metraż, jastrych, liczba pętli, przepływy)",
            "edit_zone": "✏️ Edytuj strefę (zmień metraż, jastrych, pętle lub przepływy)",
            "remove_zone": "🗑️ Usuń strefę",
            "add_manifold": "🎛️ Dodaj nowy rozdzielacz",
            "edit_manifold": "⚙️ Edytuj rozdzielacz",
            "remove_manifold": "🗑️ Usuń rozdzielacz",
            "save": "💾 Zapisz i zastosuj zmiany",
        }

        if user_input is not None:
            choice = user_input.get("action")
            if choice == "add_zone":
                return await self.async_step_zone_wizard()
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
                vol.Required("action", default="add_zone"): vol.In(actions),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    # ================= KREATOR STREFY (Rozdzielacz > Strefa > Pętle) =================

    async def async_step_zone_wizard(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Krok 1 dodawania strefy: Wybór rozdzielacza, metraż, typ i grubość jastrychu oraz liczba pętli."""
        errors: dict[str, str] = {}
        manifolds = {m_id: m_data["name"] for m_id, m_data in self.options[CONF_MANIFOLDS].items()}

        # Jeśli brak rozdzielacza, najpierw utwórz rozdzielacz
        if not manifolds:
            self.options[CONF_MANIFOLDS]["parter"] = {
                "name": "Rozdzielacz Parter",
                "location": "Kotłownia / Parter",
                "sections_count": 8,
            }
            manifolds = {"parter": "Rozdzielacz Parter"}

        screed_choices = {k: v["name"] for k, v in SCREED_TYPES.items()}
        spacing_choices = {10.0: "10 cm (zagęszczony)", 15.0: "15 cm (standard)", 20.0: "20 cm (rzadki)"}

        if user_input is not None:
            zone_name = user_input["name"].strip()
            z_id = zone_name.lower().replace(" ", "_").replace("ł", "l").replace("ą", "a").replace("ę", "e").replace("ó", "o")
            # Unikalność ID
            base_id = z_id
            counter = 1
            while z_id in self.options[CONF_ZONES]:
                z_id = f"{base_id}_{counter}"
                counter += 1

            self._temp_zone_data = {
                "id": z_id,
                "name": zone_name,
                "manifold_id": user_input["manifold_id"],
                "area_m2": float(user_input["area_m2"]),
                "screed_type": user_input["screed_type"],
                "screed_thickness_mm": float(user_input["screed_thickness_mm"]),
                "loops_count": int(user_input["loops_count"]),
                "spacing_cm": float(user_input.get("spacing_cm", 15.0)),
                "approach_length_m": float(user_input.get("approach_length_m", 4.0)),
                "floor_covering": "tiles",
                "heat_load_w_m2": 45.0,
                "target_temp": 21.5,
            }

            # Przejście do kroku podania przepływów dla pętli
            return await self.async_step_zone_loops_flows()

        schema = vol.Schema(
            {
                vol.Required("manifold_id", default=list(manifolds.keys())[0]): vol.In(manifolds),
                vol.Required("name", default="Salon"): str,
                vol.Required("area_m2", default=37.0): vol.Coerce(float),
                vol.Required("screed_type", default="cement"): vol.In(screed_choices),
                vol.Required("screed_thickness_mm", default=50.0): vol.Coerce(float),
                vol.Required("loops_count", default=2): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Optional("spacing_cm", default=15.0): vol.In(spacing_choices),
                vol.Optional("approach_length_m", default=4.0): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="zone_wizard", data_schema=schema, errors=errors)

    async def async_step_zone_loops_flows(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Krok 2: Wskazanie przepływu rotametrów dla każdej z pętli nowej strefy."""
        z = self._temp_zone_data
        loops_cnt = z.get("loops_count", 1)
        area = z.get("area_m2", 20.0)

        # Wyliczenie sugerowanego przepływu projektowego na pętlę
        therm = calculate_thermal_properties(area, z.get("screed_type", "cement"), z.get("screed_thickness_mm", 50.0))
        suggested_flow_lh = round(therm["required_flow_lh"] / float(loops_cnt), 0)

        if user_input is not None:
            z_id = z["id"]
            # 1. Zapis strefy
            self.options[CONF_ZONES][z_id] = {
                "name": z["name"],
                "manifold_id": z["manifold_id"],
                "area_m2": z["area_m2"],
                "screed_type": z["screed_type"],
                "screed_thickness_mm": z["screed_thickness_mm"],
                "loops_count": loops_cnt,
                "floor_covering": z.get("floor_covering", "tiles"),
                "heat_load_w_m2": 45.0,
                "target_temp": 21.5,
            }

            # 2. Utworzenie pętli
            for i in range(1, loops_cnt + 1):
                loop_id = f"petla_{z_id}_{i}"
                flow_val = float(user_input.get(f"flow_loop_{i}", suggested_flow_lh))
                self.options[CONF_LOOPS][loop_id] = {
                    "name": f"{z['name']} - Pętla {i}",
                    "manifold_id": z["manifold_id"],
                    "zone_id": z_id,
                    "section_number": len([l for l in self.options[CONF_LOOPS].values() if l.get("manifold_id") == z["manifold_id"]]) + 1,
                    "pipe_type": DEFAULT_PIPE_TYPE,
                    "spacing_cm": z.get("spacing_cm", 15.0),
                    "approach_length_m": z.get("approach_length_m", 4.0),
                    "loops_in_zone": loops_cnt,
                    ATTR_ROTAMETER_FLOW_LH: flow_val,
                }

            return await self.async_step_init()

        # Budowa dynamicznego formularza z przepływami dla każdej pętli
        fields = {}
        for i in range(1, loops_cnt + 1):
            fields[vol.Required(f"flow_loop_{i}", default=suggested_flow_lh)] = vol.Coerce(float)

        schema = vol.Schema(fields)
        return self.async_show_form(
            step_id="zone_loops_flows",
            data_schema=schema,
            description_placeholders={
                "zone_name": z["name"],
                "suggested_flow": f"{suggested_flow_lh} l/h ({round(suggested_flow_lh/60.0, 2)} l/min)",
                "loops_count": str(loops_cnt),
            },
        )

    # ================= EDYCJA STREFY I PĘTLI =================

    async def async_step_select_edit_zone(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybór strefy do edycji."""
        zones = {z_id: f"{z['name']} ({z.get('area_m2', 0)} m², {z.get('loops_count', len([l for l in self.options[CONF_LOOPS].values() if l.get('zone_id') == z_id]))} pętli)" for z_id, z in self.options[CONF_ZONES].items()}
        if not zones:
            return await self.async_step_init()

        if user_input is not None:
            self._selected_zone_id = user_input["zone_id"]
            return await self.async_step_edit_zone_form()

        schema = vol.Schema({vol.Required("zone_id"): vol.In(zones)})
        return self.async_show_form(step_id="select_edit_zone", data_schema=schema)

    async def async_step_edit_zone_form(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz edycji strefy: zmiana metrażu, jastrychu, grubości, rozstawu i przepływów."""
        z_id = self._selected_zone_id
        z_data = self.options[CONF_ZONES].get(z_id, {})
        screed_choices = {k: v["name"] for k, v in SCREED_TYPES.items()}
        manifolds = {m_id: m_data["name"] for m_id, m_data in self.options[CONF_MANIFOLDS].items()}

        # Znajdź pętle należące do tej strefy
        existing_loops = [l_id for l_id, l in self.options[CONF_LOOPS].items() if l.get("zone_id") == z_id]
        current_loops_cnt = max(len(existing_loops), int(z_data.get("loops_count", 1)))

        if user_input is not None:
            new_area = float(user_input["area_m2"])
            new_screed = user_input["screed_type"]
            new_thickness = float(user_input["screed_thickness_mm"])
            new_loops_cnt = int(user_input["loops_count"])
            new_manifold = user_input["manifold_id"]

            # Aktualizacja danych strefy
            self.options[CONF_ZONES][z_id].update({
                "name": user_input["name"],
                "manifold_id": new_manifold,
                "area_m2": new_area,
                "screed_type": new_screed,
                "screed_thickness_mm": new_thickness,
                "loops_count": new_loops_cnt,
            })

            # Dopasowanie liczby pętli
            if new_loops_cnt != len(existing_loops):
                # Jeśli zwiększono liczbę pętli, dodaj brakujące
                if new_loops_cnt > len(existing_loops):
                    for i in range(len(existing_loops) + 1, new_loops_cnt + 1):
                        new_loop_id = f"petla_{z_id}_{i}"
                        self.options[CONF_LOOPS][new_loop_id] = {
                            "name": f"{user_input['name']} - Pętla {i}",
                            "manifold_id": new_manifold,
                            "zone_id": z_id,
                            "section_number": i,
                            "pipe_type": DEFAULT_PIPE_TYPE,
                            "spacing_cm": 15.0,
                            "approach_length_m": 4.0,
                            "loops_in_zone": new_loops_cnt,
                            ATTR_ROTAMETER_FLOW_LH: 100.0,
                        }
                # Jeśli zmniejszono, usuń nadmiarowe
                elif new_loops_cnt < len(existing_loops):
                    for l_to_del in existing_loops[new_loops_cnt:]:
                        self.options[CONF_LOOPS].pop(l_to_del, None)

            # Aktualizacja liczby pętli we wszystkich pętlach strefy
            for l_id, l in self.options[CONF_LOOPS].items():
                if l.get("zone_id") == z_id:
                    l["loops_in_zone"] = new_loops_cnt
                    l["manifold_id"] = new_manifold

            return await self.async_step_edit_loops_flows_for_zone()

        schema = vol.Schema(
            {
                vol.Required("manifold_id", default=z_data.get("manifold_id", list(manifolds.keys())[0])): vol.In(manifolds),
                vol.Required("name", default=z_data.get("name", "Strefa")): str,
                vol.Required("area_m2", default=float(z_data.get("area_m2", 25.0))): vol.Coerce(float),
                vol.Required("screed_type", default=z_data.get("screed_type", "cement")): vol.In(screed_choices),
                vol.Required("screed_thickness_mm", default=float(z_data.get("screed_thickness_mm", 50.0))): vol.Coerce(float),
                vol.Required("loops_count", default=current_loops_cnt): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
            }
        )
        return self.async_show_form(step_id="edit_zone_form", data_schema=schema)

    async def async_step_edit_loops_flows_for_zone(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Krok edycji przepływów rotametrów dla strefy."""
        z_id = self._selected_zone_id
        z = self.options[CONF_ZONES].get(z_id, {})
        zone_loops = {l_id: l for l_id, l in self.options[CONF_LOOPS].items() if l.get("zone_id") == z_id}

        if user_input is not None:
            for l_id, l in zone_loops.items():
                if l_id in user_input:
                    l[ATTR_ROTAMETER_FLOW_LH] = float(user_input[l_id])
            return await self.async_step_init()

        fields = {}
        for l_id, l in zone_loops.items():
            curr_flow = float(l.get(ATTR_ROTAMETER_FLOW_LH, 90.0))
            fields[vol.Required(l_id, default=curr_flow)] = vol.Coerce(float)

        schema = vol.Schema(fields)
        return self.async_show_form(
            step_id="edit_loops_flows_for_zone",
            data_schema=schema,
            description_placeholders={"zone_name": z.get("name", "Strefa")},
        )

    async def async_step_remove_zone(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Usunięcie strefy wraz ze wszystkimi jej pętlami."""
        zones = {z_id: f"{z['name']} ({z.get('area_m2', 0)} m²)" for z_id, z in self.options[CONF_ZONES].items()}
        if not zones:
            return await self.async_step_init()

        if user_input is not None:
            z_id = user_input["zone_id"]
            # Usuń pętle strefy
            loops_to_del = [l_id for l_id, l in self.options[CONF_LOOPS].items() if l.get("zone_id") == z_id]
            for l_id in loops_to_del:
                self.options[CONF_LOOPS].pop(l_id, None)
            # Usuń strefę
            self.options[CONF_ZONES].pop(z_id, None)
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("zone_id"): vol.In(zones)})
        return self.async_show_form(step_id="remove_zone", data_schema=schema)

    # ================= ROZDZIELACZE =================

    async def async_step_add_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Formularz dodawania rozdzielacza."""
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
                vol.Required("id", default=f"rozdzielacz_{len(self.options[CONF_MANIFOLDS]) + 1}"): str,
                vol.Required("name", default=f"Rozdzielacz {len(self.options[CONF_MANIFOLDS]) + 1}"): str,
                vol.Optional("location", default="Kotłownia"): str,
                vol.Required("sections_count", default=8): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="add_manifold", data_schema=schema)

    async def async_step_select_edit_manifold(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Wybór rozdzielacza do edycji."""
        manifolds = {m_id: m_data["name"] for m_id, m_data in self.options[CONF_MANIFOLDS].items()}
        if not manifolds:
            return await self.async_step_init()

        if user_input is not None:
            self._selected_manifold_id = user_input["manifold_id"]
            return await self.async_step_edit_manifold_details()

        schema = vol.Schema({vol.Required("manifold_id"): vol.In(manifolds)})
        return self.async_show_form(step_id="select_edit_manifold", data_schema=schema)

    async def async_step_edit_manifold_details(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Edycja parametrów rozdzielacza."""
        m_id = self._selected_manifold_id
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
        manifolds = {m_id: m_data["name"] for m_id, m_data in self.options[CONF_MANIFOLDS].items()}
        if not manifolds:
            return await self.async_step_init()

        if user_input is not None:
            m_id = user_input["manifold_id"]
            self.options[CONF_MANIFOLDS].pop(m_id, None)
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("manifold_id"): vol.In(manifolds)})
        return self.async_show_form(step_id="remove_manifold", data_schema=schema)
