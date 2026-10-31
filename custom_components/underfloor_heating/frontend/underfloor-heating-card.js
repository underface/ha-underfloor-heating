/**
 * Underfloor Heating Manifold Lovelace Card (RWD)
 * Fotorealistyczna, interaktywna wizualizacja rozdzielacza hydraulicznego:
 * - Belka górna (zasilająca) ze stali nierdzewnej z pionowymi rotametrami i ruchomymi pływakami
 * - Belka dolna (powrotna) z siłownikami termoelektrycznymi (dioda LED)
 * - Zawory kulowe z tarczami termometrów 38°C i 32°C
 * - Kafelki obiegów z nazwą pomieszczenia, przepływem l/m, l/h, długością i przyciskami [-] [+]
 * - Interaktywny modal szybkiej edycji pętli i wyboru wylewki
 *
 * Wersja: 1.2.0
 */

const I18N = {
  pl: {
    manifold: "Rozdzielacz",
    balanced: "Zrównoważony",
    unbalanced: "Wymaga regulacji",
    supply: "ZASILANIE",
    return: "POWRÓT",
    total_flow: "Przepływ całkowity",
    edit_loop: "Edytuj pętlę",
    room: "Pomieszczenie",
    area: "Powierzchnia (m²)",
    flow: "Przepływ zadany (l/min)",
    screed: "Rodzaj posadzki",
    save: "Zapisz",
    cancel: "Anuluj",
    screed_default: "Domyślna rozdzielacza",
    screed_cement: "Wylewka cementowa tradycyjna",
    screed_anhydrite: "Wylewka anhydrytowa płynna",
    screed_dry: "Sucha zabudowa",
  },
  en: {
    manifold: "Manifold",
    balanced: "Balanced",
    unbalanced: "Needs adjustment",
    supply: "SUPPLY",
    return: "RETURN",
    total_flow: "Total flow",
    edit_loop: "Edit Loop",
    room: "Room Name",
    area: "Area (m²)",
    flow: "Target Flow (l/min)",
    screed: "Screed Type",
    save: "Save",
    cancel: "Cancel",
    screed_default: "Manifold Default",
    screed_cement: "Cement Screed",
    screed_anhydrite: "Anhydrite Liquid Screed",
    screed_dry: "Dry System",
  }
};

class UnderfloorHeatingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._lang = "pl";
    this._activeManifoldId = null;
    this._editingLoopIndex = null;
  }

  setConfig(config) {
    this._config = config || {};
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    const detected = (hass.locale && hass.locale.language) || hass.language || "pl";
    this._lang = detected.startsWith("pl") ? "pl" : "en";
    this.updateCard();
  }

  get t() {
    return I18N[this._lang] || I18N["pl"];
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          --bg-card: var(--ha-card-background, #0d1527);
          --text-main: var(--primary-text-color, #f8fafc);
          --text-muted: var(--secondary-text-color, #94a3b8);
          --border: var(--divider-color, #1e293b);
          --cyan-acc: #38bdf8;
          --cyan-dark: #0284c7;
          --brass: linear-gradient(180deg, #fef08a 0%, #ca8a04 45%, #854d0e 80%, #fef08a 100%);
          --steel: linear-gradient(180deg, #f8fafc 0%, #94a3b8 35%, #475569 70%, #cbd5e1 100%);
        }

        .card-container {
          background: #0d1726;
          color: var(--text-main);
          border-radius: 16px;
          padding: 16px 20px;
          border: 1px solid #1e293b;
          box-shadow: 0 10px 25px rgba(0,0,0,0.5);
          user-select: none;
        }

        /* NAGŁÓWEK KARTY */
        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
          margin-bottom: 20px;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .manifold-icon {
          width: 36px;
          height: 36px;
          background: rgba(2, 132, 199, 0.15);
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #38bdf8;
          font-size: 20px;
          font-weight: 800;
        }

        .header-title-box {
          display: flex;
          flex-direction: column;
        }

        .header-title {
          font-size: 1.15rem;
          font-weight: 800;
          color: #f8fafc;
          letter-spacing: -0.01em;
        }

        .header-subtitle {
          font-size: 0.8rem;
          color: #94a3b8;
          margin-top: 2px;
        }

        .tabs-group {
          display: flex;
          gap: 8px;
        }

        .tab-btn {
          padding: 6px 14px;
          border-radius: 8px;
          font-size: 0.8rem;
          font-weight: 700;
          border: none;
          cursor: pointer;
          transition: all 0.2s;
        }

        .tab-btn.active {
          background: #0284c7;
          color: #ffffff;
          box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4);
        }

        .tab-btn.inactive {
          background: #1e293b;
          color: #94a3b8;
        }
        .tab-btn.inactive:hover {
          background: #334155;
          color: #f8fafc;
        }

        /* WIZUALIZACJA BELKI HYDRAULICZNEJ */
        .manifold-station-wrapper {
          overflow-x: auto;
          padding-bottom: 12px;
          -webkit-overflow-scrolling: touch;
        }

        .manifold-viewport {
          min-width: 680px;
          position: relative;
          padding: 10px 0;
        }

        .station-layout {
          display: grid;
          grid-template-columns: 85px 1fr 40px;
          align-items: stretch;
          position: relative;
        }

        /* Uchwyty montażowe pionowe w tle */
        .bracket-1 {
          position: absolute;
          left: 210px;
          top: 0;
          bottom: 20px;
          width: 14px;
          background: rgba(71, 85, 105, 0.3);
          border-radius: 3px;
          z-index: 1;
        }
        .bracket-2 {
          position: absolute;
          right: 170px;
          top: 0;
          bottom: 20px;
          width: 14px;
          background: rgba(71, 85, 105, 0.3);
          border-radius: 3px;
          z-index: 1;
        }

        /* Zawory z termometrami po lewej */
        .valves-column {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 24px 0 20px 0;
          z-index: 2;
        }

        .valve-unit {
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .thermometer-dial {
          width: 44px;
          height: 44px;
          border-radius: 50%;
          background: #f8fafc;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 11px;
          font-weight: 800;
          color: #0f172a;
          box-shadow: 0 4px 10px rgba(0,0,0,0.5);
          position: relative;
          z-index: 3;
        }
        .dial-red { border: 3px solid #ef4444; }
        .dial-blue { border: 3px solid #0284c7; }

        .valve-brass-body {
          width: 46px;
          height: 22px;
          background: var(--brass);
          border-radius: 5px;
          margin-top: -12px;
          box-shadow: 0 2px 5px rgba(0,0,0,0.4);
          z-index: 2;
        }

        .valve-label {
          font-size: 10px;
          font-weight: 800;
          margin-top: 6px;
          letter-spacing: 0.05em;
        }
        .lbl-red { color: #f87171; }
        .lbl-blue { color: #38bdf8; }

        /* Belki i rury */
        .pipes-column {
          display: flex;
          flex-direction: column;
          gap: 65px;
          position: relative;
          padding: 30px 0;
          z-index: 2;
        }

        .steel-pipe {
          height: 38px;
          background: var(--steel);
          border-radius: 6px;
          border: 1px solid #475569;
          box-shadow: inset 0 2px 2px rgba(255,255,255,0.7), 0 6px 12px rgba(0,0,0,0.4);
          position: relative;
        }

        .rotameters-layer {
          position: absolute;
          top: -46px;
          left: 10px;
          right: 10px;
          display: flex;
          justify-content: space-around;
        }

        .actuators-layer {
          position: absolute;
          top: 36px;
          left: 10px;
          right: 10px;
          display: flex;
          justify-content: space-around;
        }

        /* Szklany rotametr */
        .rotameter-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          width: 80px;
          flex-shrink: 0;
        }

        .rot-blue-cap {
          width: 22px;
          height: 9px;
          background: #0284c7;
          border-radius: 3px 3px 0 0;
        }

        .rot-glass-cylinder {
          width: 18px;
          height: 60px;
          background: rgba(15, 23, 42, 0.85);
          border: 1px solid #475569;
          border-radius: 3px;
          position: relative;
          overflow: hidden;
          box-shadow: inset 0 0 6px rgba(56, 189, 248, 0.2);
        }

        .rot-water-fill {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          background: linear-gradient(180deg, #38bdf8 0%, #0284c7 100%);
          transition: height 0.3s;
        }

        .rot-red-float {
          position: absolute;
          left: 1px;
          right: 1px;
          height: 4px;
          background: #ef4444;
          border-radius: 1px;
          box-shadow: 0 1px 2px rgba(0,0,0,0.6);
          transition: bottom 0.3s;
        }

        .rot-brass-nut {
          width: 18px;
          height: 8px;
          background: var(--brass);
          border-radius: 1px 1px 3px 3px;
        }

        .nipple-red {
          width: 7px;
          height: 18px;
          background: #ef4444;
          border-radius: 2px;
          margin-top: 1px;
        }

        /* Siłowniki białe */
        .actuator-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          width: 80px;
          flex-shrink: 0;
        }

        .actuator-body {
          width: 26px;
          height: 46px;
          background: linear-gradient(180deg, #f8fafc 0%, #cbd5e1 100%);
          border: 1px solid #94a3b8;
          border-radius: 6px;
          display: flex;
          align-items: flex-start;
          justify-content: center;
          padding-top: 6px;
          box-shadow: 0 3px 6px rgba(0,0,0,0.3);
        }

        .actuator-led {
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: #22c55e;
          box-shadow: 0 0 4px #22c55e;
        }

        .actuator-nut {
          width: 18px;
          height: 8px;
          background: var(--brass);
          border-radius: 2px;
        }

        /* Prawa strona: odpowietrzniki */
        .vents-column {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 24px 0;
          align-items: center;
          z-index: 2;
        }

        .vent-tap {
          width: 18px;
          height: 38px;
          background: var(--brass);
          border-radius: 3px;
        }

        /* KAFELKI SEKCJI POD BELKAMI */
        .loops-cards-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(105px, 1fr));
          gap: 12px;
          margin-top: 55px;
          padding-top: 15px;
          border-top: 1px solid #1e293b;
        }

        .loop-card {
          background: #091120;
          border: 1px solid #1e293b;
          border-radius: 10px;
          padding: 10px 8px;
          text-align: center;
          transition: transform 0.15s, border-color 0.15s;
          cursor: pointer;
        }
        .loop-card:hover {
          border-color: #38bdf8;
          transform: translateY(-2px);
        }

        .loop-room-name {
          font-size: 0.85rem;
          font-weight: 700;
          color: #f8fafc;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .loop-flow-display {
          font-size: 1.15rem;
          font-weight: 800;
          color: #38bdf8;
          margin: 4px 0 2px 0;
        }

        .loop-subinfo {
          font-size: 0.7rem;
          color: #94a3b8;
        }

        .stepper-controls {
          display: flex;
          justify-content: center;
          gap: 6px;
          margin-top: 8px;
        }

        .stepper-btn {
          width: 28px;
          height: 22px;
          background: #1e293b;
          border: 1px solid #334155;
          color: #f8fafc;
          border-radius: 5px;
          font-weight: 800;
          font-size: 13px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
        }
        .stepper-btn:hover {
          background: #0284c7;
          border-color: #38bdf8;
          color: #ffffff;
        }

        /* MODAL EDYCJI PĘTLI */
        .modal-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0, 0, 0, 0.75);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 9999;
        }

        .modal-content {
          background: #0f172a;
          border: 1px solid #334155;
          border-radius: 14px;
          padding: 22px;
          width: 90%;
          max-width: 420px;
          box-shadow: 0 16px 36px rgba(0,0,0,0.6);
        }

        .modal-header {
          font-size: 1.1rem;
          font-weight: 800;
          color: #38bdf8;
          margin-bottom: 14px;
          padding-bottom: 8px;
          border-bottom: 1px solid #334155;
        }

        .form-row {
          margin-bottom: 12px;
        }

        .form-row label {
          display: block;
          font-size: 0.75rem;
          color: #94a3b8;
          font-weight: 700;
          margin-bottom: 4px;
          text-transform: uppercase;
        }

        .form-row input, .form-row select {
          width: 100%;
          box-sizing: border-box;
          padding: 9px 12px;
          background: #090e1c;
          border: 1px solid #334155;
          border-radius: 8px;
          color: #f8fafc;
          font-size: 0.95rem;
          outline: none;
        }
        .form-row input:focus, .form-row select:focus {
          border-color: #38bdf8;
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          margin-top: 18px;
        }

        .btn-modal {
          padding: 8px 16px;
          border-radius: 8px;
          font-size: 0.85rem;
          font-weight: 700;
          cursor: pointer;
          border: none;
        }
        .btn-save { background: #0284c7; color: white; }
        .btn-save:hover { background: #0369a1; }
        .btn-cancel { background: #334155; color: #cbd5e1; }
        .btn-cancel:hover { background: #475569; }
      </style>

      <div class="card-container">
        <!-- Nagłówek -->
        <div class="card-header">
          <div class="header-left">
            <div class="manifold-icon">#</div>
            <div class="header-title-box">
              <div class="header-title" id="card-title">Rozdzielacz Parter (6 obiegów)</div>
              <div class="header-subtitle" id="card-subtitle">
                Kotłownia / Parter • Przepływ całkowity: <b id="sum-flow-txt" style="color:#38bdf8">8.2 l/min</b> (<span id="sum-flow-lh-txt">492</span> l/h) • ΔT: <span style="color:#fbbf24">6.0°C</span> • Maks. Δp: <span style="color:#34d399">14.8 kPa</span>
              </div>
            </div>
          </div>
          <div class="tabs-group" id="manifold-tabs"></div>
        </div>

        <!-- Wizualizacja Rozdzielacza -->
        <div class="manifold-station-wrapper">
          <div class="manifold-viewport">
            <!-- Uchwyty montażowe -->
            <div class="bracket-1"></div>
            <div class="bracket-2"></div>

            <div class="station-layout">
              <!-- Lewe zawory z termometrami -->
              <div class="valves-column">
                <div class="valve-unit">
                  <div class="thermometer-dial dial-red">38°C</div>
                  <div class="valve-brass-body"></div>
                  <div class="valve-label lbl-red">ZASILANIE</div>
                </div>
                <div class="valve-unit">
                  <div class="thermometer-dial dial-blue">32°C</div>
                  <div class="valve-brass-body"></div>
                  <div class="valve-label lbl-blue">POWRÓT</div>
                </div>
              </div>

              <!-- Belki stalowe -->
              <div class="pipes-column">
                <!-- Górna belka: zasilanie -->
                <div class="steel-pipe">
                  <div class="rotameters-layer" id="rotameters-layer"></div>
                </div>
                <!-- Dolna belka: powrót -->
                <div class="steel-pipe">
                  <div class="actuators-layer" id="actuators-layer"></div>
                </div>
              </div>

              <!-- Prawe odpowietrzniki -->
              <div class="vents-column">
                <div class="vent-tap" title="Odpowietrznik"></div>
                <div class="vent-tap" title="Zawór spustowy"></div>
              </div>
            </div>

            <!-- Kafelki pętli na dole -->
            <div class="loops-cards-grid" id="loops-cards-grid"></div>
          </div>
        </div>
      </div>

      <!-- Modal edycji pętli -->
      <div class="modal-overlay" id="edit-modal" style="display:none;">
        <div class="modal-content">
          <div class="modal-header" id="modal-heading">Edytuj pętlę</div>
          <div class="form-row">
            <label>Nazwa pomieszczenia</label>
            <input type="text" id="modal-inp-room">
          </div>
          <div class="form-row">
            <label>Powierzchnia strefy (m²)</label>
            <input type="number" id="modal-inp-area" step="0.5" min="1">
          </div>
          <div class="form-row">
            <label>Przepływ zadany (l/min)</label>
            <input type="number" id="modal-inp-flow" step="0.1" min="0.1" max="6.0">
          </div>
          <div class="form-row">
            <label>Rodzaj wylewki / posadzki</label>
            <select id="modal-inp-screed">
              <option value="default">Domyślna rozdzielacza</option>
              <option value="cement">Wylewka cementowa tradycyjna</option>
              <option value="anhydrite">Wylewka anhydrytowa płynna</option>
              <option value="dry_screed">Sucha zabudowa (płyty gipsowe)</option>
            </select>
          </div>
          <div class="modal-actions">
            <button class="btn-modal btn-cancel" id="modal-btn-cancel">Anuluj</button>
            <button class="btn-modal btn-save" id="modal-btn-save">Zapisz</button>
          </div>
        </div>
      </div>
    `;

    // Podpięcie modala
    const modalCancel = this.shadowRoot.getElementById("modal-btn-cancel");
    const modalSave = this.shadowRoot.getElementById("modal-btn-save");
    if (modalCancel) modalCancel.onclick = () => this._closeModal();
    if (modalSave) modalSave.onclick = () => this._saveModal();

    this.updateCard();
  }

  updateCard() {
    if (!this.shadowRoot) return;

    const states = (this._hass && this._hass.states) || {};
    const manifolds = {};
    const loops = [];

    // Zbieranie rozdzielaczy i pętli z Home Assistant
    Object.keys(states).forEach(entityId => {
      const stateObj = states[entityId];
      if (!stateObj) return;

      if (entityId.includes("manifold_") && entityId.includes("_total_flow")) {
        const mId = stateObj.attributes.manifold_id || entityId.split("manifold_")[1].split("_total_flow")[0];
        manifolds[mId] = {
          id: mId,
          name: stateObj.attributes.friendly_name?.replace(" Sumaryczny przepływ", "") || mId,
          sections_count: stateObj.attributes.sections_count || 6,
          total_flow_lh: parseFloat(stateObj.state) || 0,
        };
      }

      if (entityId.includes("rotameter_flow_lmin") || (entityId.includes("loop_") && entityId.includes("_status"))) {
        const attrs = stateObj.attributes || {};
        if (attrs.section_number !== undefined || attrs.loop_id) {
          loops.push({
            entity_id: entityId,
            loop_id: attrs.loop_id,
            section: attrs.section_number || 1,
            room: attrs.room_name || attrs.zone_name || `Pętla ${attrs.section_number || 1}`,
            flow_lmin: parseFloat(stateObj.state) || parseFloat(attrs.current_flow_lmin) || 1.5,
            flow_lh: parseFloat(attrs.current_flow_lh) || (parseFloat(stateObj.state) * 60) || 90,
            req_lmin: parseFloat(attrs.required_flow_lmin) || 1.5,
            length_m: parseFloat(attrs.loop_length_m) || 75.0,
            dp_kpa: parseFloat(attrs.pressure_drop_kpa) || 8.5,
            screed: attrs.screed_type || "default",
            area_m2: parseFloat(attrs.area_m2) || 15.0,
            manifold_id: attrs.manifold_id || "parter",
          });
        }
      }
    });

    // Jeśli integracja dopiero wystartowała lub brak encji, wczytaj 6 obiegów ze zdjęcia
    if (Object.keys(manifolds).length === 0) {
      manifolds["parter"] = { id: "parter", name: "Rozdzielacz Parter", sections_count: 6, total_flow_lh: 492 };
      manifolds["pietro"] = { id: "pietro", name: "Rozdzielacz Piętro", sections_count: 5, total_flow_lh: 380 };

      const defaultDemo = [
        { sec: 1, room: "Salon 1", lmin: 1.8, area: 18.0, len: 78, screed: "default" },
        { sec: 2, room: "Salon 2", lmin: 1.5, area: 16.5, len: 72, screed: "default" },
        { sec: 3, room: "Kuchnia", lmin: 1.2, area: 12.0, len: 64, screed: "default" },
        { sec: 4, room: "Łazienka", lmin: 1.6, area: 9.0, len: 55, screed: "default" },
        { sec: 5, room: "Korytarz", lmin: 1.0, area: 7.5, len: 42, screed: "default" },
        { sec: 6, room: "Gabinet", lmin: 1.1, area: 11.0, len: 58, screed: "default" },
      ];

      defaultDemo.forEach(d => {
        loops.push({
          entity_id: `number.petla_parter_${d.sec}_rotameter_flow_lmin`,
          loop_id: `petla_parter_${d.sec}`,
          section: d.sec,
          room: d.room,
          flow_lmin: d.lmin,
          flow_lh: Math.round(d.lmin * 60),
          length_m: d.len,
          area_m2: d.area,
          screed: d.screed,
          manifold_id: "parter",
        });
      });
    }

    if (!this._activeManifoldId || !manifolds[this._activeManifoldId]) {
      this._activeManifoldId = Object.keys(manifolds)[0];
    }

    const currentM = manifolds[this._activeManifoldId];
    this._currentLoops = loops.filter(l => l.manifold_id === this._activeManifoldId || !l.manifold_id);
    this._currentLoops.sort((a, b) => a.section - b.section);

    // Zakładki rozdzielaczy (np. Parter (6) / Piętro (5))
    const tabsContainer = this.shadowRoot.getElementById("manifold-tabs");
    if (tabsContainer) {
      tabsContainer.innerHTML = Object.values(manifolds).map(m => `
        <button class="tab-btn ${m.id === this._activeManifoldId ? 'active' : 'inactive'}" data-mid="${m.id}">
          ${m.name.replace("Rozdzielacz ", "")} (${m.sections_count || 6})
        </button>
      `).join("");

      tabsContainer.querySelectorAll(".tab-btn").forEach(btn => {
        btn.onclick = () => {
          this._activeManifoldId = btn.getAttribute("data-mid");
          this.updateCard();
        };
      });
    }

    // Podsumowanie rozdzielacza
    const totalFlowLh = this._currentLoops.reduce((acc, l) => acc + (l.flow_lh || 0), 0);
    const totalFlowLmin = (totalFlowLh / 60.0).toFixed(1);

    const titleEl = this.shadowRoot.getElementById("card-title");
    const flowTxt = this.shadowRoot.getElementById("sum-flow-txt");
    const flowLhTxt = this.shadowRoot.getElementById("sum-flow-lh-txt");

    if (titleEl && currentM) titleEl.textContent = `${currentM.name} (${this._currentLoops.length} obiegów)`;
    if (flowTxt) flowTxt.textContent = `${totalFlowLmin} l/min`;
    if (flowLhTxt) flowLhTxt.textContent = `${Math.round(totalFlowLh)}`;

    // Rysowanie rotametrów na górnej belce
    const rotLayer = this.shadowRoot.getElementById("rotameters-layer");
    if (rotLayer) {
      rotLayer.innerHTML = this._currentLoops.map(loop => {
        const fillPct = Math.min(Math.max((loop.flow_lmin / 4.0) * 100, 10), 92);
        return `
          <div class="rotameter-item" title="${loop.room}: ${loop.flow_lmin.toFixed(1)} l/min">
            <div class="rot-blue-cap"></div>
            <div class="rot-glass-cylinder">
              <div class="rot-water-fill" style="height: ${fillPct}%;"></div>
              <div class="rot-red-float" style="bottom: ${fillPct}%;"></div>
            </div>
            <div class="rot-brass-nut"></div>
            <div class="nipple-red"></div>
          </div>
        `;
      }).join("");
    }

    // Rysowanie siłowników na dolnej belce
    const actLayer = this.shadowRoot.getElementById("actuators-layer");
    if (actLayer) {
      actLayer.innerHTML = this._currentLoops.map(() => `
        <div class="actuator-item">
          <div class="actuator-nut"></div>
          <div class="actuator-body">
            <div class="actuator-led"></div>
          </div>
          <div class="nipple-red"></div>
        </div>
      `).join("");
    }

    // Kafelki pętli na dole
    const grid = this.shadowRoot.getElementById("loops-cards-grid");
    if (grid) {
      grid.innerHTML = this._currentLoops.map((loop, idx) => `
        <div class="loop-card" data-idx="${idx}">
          <div class="loop-room-name" title="${loop.room}">${loop.room}</div>
          <div class="loop-flow-display">${loop.flow_lmin.toFixed(1)} <small style="font-size:0.65em">l/m</small></div>
          <div class="loop-subinfo">${Math.round(loop.flow_lh)} l/h • ${Math.round(loop.length_m)}m</div>
          <div class="stepper-controls" onclick="event.stopPropagation();">
            <button class="stepper-btn" data-idx="${idx}" data-step="-0.1">-</button>
            <button class="stepper-btn" data-idx="${idx}" data-step="+0.1">+</button>
          </div>
        </div>
      `).join("");

      // Kliknięcie w kafelek -> szybka edycja pętli
      grid.querySelectorAll(".loop-card").forEach(card => {
        card.onclick = () => {
          const idx = parseInt(card.getAttribute("data-idx"));
          this._openModal(idx);
        };
      });

      // Steppery [-] [+]
      grid.querySelectorAll(".stepper-btn").forEach(btn => {
        btn.onclick = e => {
          e.stopPropagation();
          const idx = parseInt(btn.getAttribute("data-idx"));
          const step = parseFloat(btn.getAttribute("data-step"));
          const targetLoop = this._currentLoops[idx];
          if (!targetLoop) return;

          const newLmin = Math.max(0.1, Math.min(6.0, parseFloat((targetLoop.flow_lmin + step).toFixed(1))));
          targetLoop.flow_lmin = newLmin;
          targetLoop.flow_lh = Math.round(newLmin * 60);

          if (this._hass && targetLoop.entity_id) {
            const isLmin = targetLoop.entity_id.includes("lmin");
            this._hass.callService("number", "set_value", {
              entity_id: targetLoop.entity_id,
              value: isLmin ? newLmin : (newLmin * 60),
            });
          }
          this.updateCard();
        };
      });
    }
  }

  _openModal(idx) {
    this._editingLoopIndex = idx;
    const loop = this._currentLoops[idx];
    if (!loop) return;

    this.shadowRoot.getElementById("modal-heading").textContent = `Edycja pętli: ${loop.room} (Sekcja ${loop.section})`;
    this.shadowRoot.getElementById("modal-inp-room").value = loop.room;
    this.shadowRoot.getElementById("modal-inp-area").value = loop.area_m2;
    this.shadowRoot.getElementById("modal-inp-flow").value = loop.flow_lmin.toFixed(1);
    this.shadowRoot.getElementById("modal-inp-screed").value = loop.screed || "default";

    this.shadowRoot.getElementById("edit-modal").style.display = "flex";
  }

  _closeModal() {
    this.shadowRoot.getElementById("edit-modal").style.display = "none";
    this._editingLoopIndex = null;
  }

  _saveModal() {
    if (this._editingLoopIndex === null) return;
    const loop = this._currentLoops[this._editingLoopIndex];
    if (!loop) return;

    const newRoom = this.shadowRoot.getElementById("modal-inp-room").value.trim() || loop.room;
    const newArea = parseFloat(this.shadowRoot.getElementById("modal-inp-area").value) || loop.area_m2;
    const newFlow = parseFloat(this.shadowRoot.getElementById("modal-inp-flow").value) || loop.flow_lmin;
    const newScreed = this.shadowRoot.getElementById("modal-inp-screed").value;

    loop.room = newRoom;
    loop.area_m2 = newArea;
    loop.flow_lmin = newFlow;
    loop.flow_lh = Math.round(newFlow * 60);
    loop.screed = newScreed;
    loop.length_m = Math.round((newArea / 0.15) * 1.03 + 8);

    // Wywołaj usługi Home Assistant w tle
    if (this._hass) {
      if (loop.loop_id) {
        this._hass.callService("underfloor_heating", "update_loop", {
          loop_id: loop.loop_id,
          name: newRoom,
        });
        this._hass.callService("underfloor_heating", "set_rotameter_flow", {
          loop_id: loop.loop_id,
          rotameter_flow_lh: loop.flow_lh,
        });
      }
    }

    this._closeModal();
    this.updateCard();
  }
}

customElements.define("underfloor-heating-card", UnderfloorHeatingCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "underfloor-heating-card",
  name: "Underfloor Heating Manifold Card",
  preview: true,
  description: "Interaktywny rozdzielacz podłogówki z rotametrami i regulacją l/min (RWD)"
});
