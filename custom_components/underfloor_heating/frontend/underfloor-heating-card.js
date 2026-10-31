/**
 * Underfloor Heating Manifold Lovelace Card (RWD)
 * Fotorealistyczna, responsywna wizualizacja rozdzielacza hydraulicznego podłogówki:
 * - Belka zasilająca z rotametrami pionowymi, skalą l/min i pływakami
 * - Belka powrotna z zaworami termostatycznymi
 * - Kolumny sekcji z nazwami pomieszczeń, metrażem, estymowaną długością i wylewką
 * - Boczne zawory kulowe z termometrami i odpowietrzniki
 * - Przełącznik rozdzielaczy (Parter / Piętro) i pełne RWD
 *
 * Wersja: 1.1.0
 */

const I18N = {
  pl: {
    manifold: "Rozdzielacz",
    balanced: "Zrównoważony",
    unbalanced: "Wymaga regulacji",
    loop: "Pętla",
    flow: "Przepływ",
    required: "Wymagany",
    length: "Długość",
    dp: "Opór",
    screed: "Posadzka",
    total_flow: "Sumaryczny przepływ",
    supply: "Zasilanie",
    return: "Powrót",
    status_optimal: "Optymalny",
    status_underflow: "Zdławiony",
    status_overflow: "Zawyżony",
    status_critical: "Za długa pętla",
  },
  en: {
    manifold: "Manifold",
    balanced: "Balanced",
    unbalanced: "Needs adjustment",
    loop: "Loop",
    flow: "Flow",
    required: "Required",
    length: "Length",
    dp: "Pressure",
    screed: "Screed",
    total_flow: "Total flow",
    supply: "Supply",
    return: "Return",
    status_optimal: "Optimal",
    status_underflow: "Throttled",
    status_overflow: "Oversized",
    status_critical: "Loop too long",
  },
  de: {
    manifold: "Heizkreisverteiler",
    balanced: "Abgeglichen",
    unbalanced: "Abgleich nötig",
    loop: "Kreis",
    flow: "Durchfluss",
    required: "Soll",
    length: "Länge",
    dp: "Druckverlust",
    screed: "Estrich",
    total_flow: "Gesamtdurchfluss",
    supply: "Vorlauf",
    return: "Rücklauf",
    status_optimal: "Optimal",
    status_underflow: "Gedrosselt",
    status_overflow: "Überhöht",
    status_critical: "Zu lang",
  },
  es: {
    manifold: "Colector",
    balanced: "Equilibrado",
    unbalanced: "Requiere ajuste",
    loop: "Circuito",
    flow: "Caudal",
    required: "Requerido",
    length: "Longitud",
    dp: "Pérdida",
    screed: "Recrecido",
    total_flow: "Caudal total",
    supply: "Impulsión",
    return: "Retorno",
    status_optimal: "Óptimo",
    status_underflow: "Estrangulado",
    status_overflow: "Sobredimensionado",
    status_critical: "Muy largo",
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
  }

  setConfig(config) {
    this._config = config || {};
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    const detected = (hass.locale && hass.locale.language) || hass.language || "pl";
    this._lang = I18N[detected] ? detected : (detected.startsWith("en") ? "en" : (detected.startsWith("de") ? "de" : (detected.startsWith("es") ? "es" : "pl")));
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
          --card-bg: var(--ha-card-background, #1c1c1e);
          --card-color: var(--primary-text-color, #f2f2f7);
          --sec-color: var(--secondary-text-color, #8e8e93);
          --border: var(--divider-color, rgba(255, 255, 255, 0.1));
          --steel-grad: linear-gradient(180deg, #e2e8f0 0%, #94a3b8 40%, #64748b 70%, #cbd5e1 100%);
          --brass-grad: linear-gradient(180deg, #fef08a 0%, #eab308 45%, #a16207 75%, #fef08a 100%);
          --success: #22c55e;
          --warning: #f59e0b;
          --danger: #ef4444;
          --primary: #0284c7;
        }

        .container {
          background: var(--card-bg);
          color: var(--card-color);
          border-radius: 16px;
          padding: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 4px 16px rgba(0,0,0,0.25));
          border: 1px solid var(--border);
          overflow: hidden;
        }

        /* Dodaj przycisk otwierający modal do tworzenia rozdzielacza */
        .header {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          border-bottom: 1px solid var(--border);
          padding-bottom: 12px;
          margin-bottom: 16px;
        }
        .add-manifold-btn {
          background: var(--primary);
          color: #fff;
          border: none;
          padding: 6px 12px;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
        }
        .modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }
        .modal {
          background: var(--card-bg);
          color: var(--card-color);
          border-radius: 12px;
          padding: 20px;
          max-width: 500px;
          width: 90%;
          box-shadow: var(--ha-card-box-shadow, 0 4px 16px rgba(0,0,0,0.25));
        }
        .modal h2 {font-size: 1.2rem; margin-top:0;}
        .modal label {display:block;margin-top:8px;}
        .modal input, .modal select {width:100%;padding:4px;margin-top:4px;}
        .modal .actions {margin-top:12px;text-align:right;}
        .modal .actions button {margin-left:8px;}


        .header-title {
          font-size: 1.15rem;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .tabs-wrapper {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }

        .tab-btn {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--border);
          color: var(--sec-color);
          padding: 5px 12px;
          border-radius: 8px;
          font-size: 0.85rem;
          cursor: pointer;
          font-weight: 600;
          transition: all 0.2s;
        }

        .tab-btn.active {
          background: var(--primary);
          color: #ffffff;
          border-color: var(--primary);
          box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4);
        }

        .summary-banner {
          display: flex;
          flex-wrap: wrap;
          justify-content: space-between;
          align-items: center;
          background: rgba(0, 0, 0, 0.15);
          border-radius: 10px;
          padding: 8px 14px;
          font-size: 0.85rem;
          margin-bottom: 16px;
          gap: 8px;
        }

        .badge {
          padding: 3px 10px;
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 700;
          text-transform: uppercase;
        }
        .badge.opt { background: rgba(34, 197, 94, 0.2); color: var(--success); }
        .badge.warn { background: rgba(245, 158, 11, 0.2); color: var(--warning); }

        /* WIZUALIZACJA ROZDZIELACZA (MANIFOLD) */
        .manifold-viewport {
          overflow-x: auto;
          padding-bottom: 10px;
          -webkit-overflow-scrolling: touch;
        }

        .manifold-frame {
          min-width: 620px;
          background: rgba(0, 0, 0, 0.2);
          border: 1px solid var(--border);
          border-radius: 14px;
          padding: 16px;
          position: relative;
        }

        .manifold-station {
          display: grid;
          grid-template-columns: 80px 1fr 60px;
          gap: 8px;
          align-items: stretch;
        }

        /* Lewa strona: zawory zasilania i powrotu z termometrami */
        .manifold-inlet {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 10px 0;
        }

        .valve-block {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .valve-handle {
          width: 34px;
          height: 34px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          font-size: 0.7rem;
          color: white;
          box-shadow: inset 0 2px 4px rgba(255,255,255,0.4), 0 2px 6px rgba(0,0,0,0.4);
          border: 2px solid rgba(0,0,0,0.3);
        }
        .valve-supply { background: #ef4444; }
        .valve-return { background: #0284c7; }

        .temp-dial {
          font-size: 0.75rem;
          font-weight: 700;
          color: var(--card-color);
        }

        /* Belki rozdzielacza */
        .manifold-bars {
          display: flex;
          flex-direction: column;
          gap: 48px;
          position: relative;
          padding: 10px 0;
        }

        .steel-bar {
          height: 38px;
          background: var(--steel-grad);
          border-radius: 6px;
          box-shadow: 0 4px 10px rgba(0,0,0,0.3), inset 0 2px 2px rgba(255,255,255,0.8);
          border: 1px solid #475569;
          position: relative;
        }

        /* Sekcje obiegów */
        .sections-row {
          position: absolute;
          top: -46px;
          left: 10px;
          right: 10px;
          display: flex;
          justify-content: space-around;
        }

        .bottom-sections-row {
          position: absolute;
          top: 36px;
          left: 10px;
          right: 10px;
          display: flex;
          justify-content: space-around;
        }

        .section-unit {
          display: flex;
          flex-direction: column;
          align-items: center;
          width: 90px;
          flex-shrink: 0;
        }

        /* SZKLANY ROTAMETR */
        .rotameter-assembly {
          display: flex;
          flex-direction: column;
          align-items: center;
          cursor: pointer;
        }

        .rotameter-brass-cap {
          width: 18px;
          height: 10px;
          background: var(--brass-grad);
          border-radius: 3px 3px 0 0;
          border: 1px solid #78350f;
        }

        .glass-tube {
          width: 20px;
          height: 70px;
          background: rgba(186, 230, 253, 0.4);
          border: 1.5px solid #0284c7;
          border-radius: 4px;
          position: relative;
          overflow: hidden;
          box-shadow: inset 0 0 6px rgba(56, 189, 248, 0.5);
        }

        .glass-water {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          background: linear-gradient(180deg, rgba(56, 189, 248, 0.8) 0%, rgba(2, 132, 199, 0.9) 100%);
          transition: height 0.4s ease;
        }

        .glass-float {
          position: absolute;
          left: 1px;
          right: 1px;
          height: 5px;
          background: #ef4444;
          border-radius: 2px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.5);
          transition: bottom 0.4s ease;
        }

        .glass-scale-mark {
          position: absolute;
          left: 1px;
          width: 4px;
          height: 1px;
          background: rgba(0,0,0,0.5);
        }

        /* Siłownik/zawór dolny */
        .actuator-cap {
          width: 24px;
          height: 28px;
          background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%);
          border: 1px solid #64748b;
          border-radius: 4px 4px 6px 6px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }

        /* Prawa strona: Odpowietrzniki */
        .manifold-outlet {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 8px 0;
          align-items: center;
        }

        .air-vent {
          width: 22px;
          height: 40px;
          background: var(--brass-grad);
          border-radius: 4px;
          border: 1px solid #78350f;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }

        /* KARTY DANYCH OBIEGÓW POD ROZDZIELACZEM */
        .loops-details-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
          gap: 10px;
          margin-top: 55px;
          border-top: 1px solid var(--border);
          padding-top: 14px;
        }

        .loop-col {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid var(--border);
          border-radius: 10px;
          padding: 8px;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: 4px;
        }

        .loop-col.opt { border-top: 3px solid var(--success); }
        .loop-col.warn { border-top: 3px solid var(--warning); }
        .loop-col.crit { border-top: 3px solid var(--danger); }

        .loop-room {
          font-weight: 700;
          font-size: 0.85rem;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100%;
        }

        .loop-meta {
          font-size: 0.72rem;
          color: var(--sec-color);
        }

        .flow-stepper {
          display: flex;
          align-items: center;
          gap: 4px;
          margin: 4px 0;
        }

        .step-btn {
          background: rgba(255, 255, 255, 0.1);
          border: 1px solid var(--border);
          color: var(--card-color);
          width: 22px;
          height: 22px;
          border-radius: 4px;
          font-weight: bold;
          font-size: 0.8rem;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .step-btn:hover { background: var(--primary); color: white; }

        .flow-val {
          font-size: 0.95rem;
          font-weight: 800;
          color: var(--primary);
        }
      </style>

      <div class="container">
        <!-- Nagłówek -->
        <div class="header">
          <div class="header-title">
            <span>🔥</span>
            <span id="card-title">Rozdzielacz Podłogówki</span>
          </div>
          <div class="tabs-wrapper" id="manifold-tabs"></div>
        </div>

        <!-- Pasek podsumowania -->
        <div class="summary-banner">
          <div>Przepływ rozdzielacza: <b id="sum-flow" style="color:var(--primary)">0.0 l/min</b> (<span id="sum-flow-lh">0</span> l/h)</div>
          <div>Aktywne pętle: <b id="sum-loops">0</b></div>
          <div id="sum-status" class="badge opt">Zrównoważony</div>
        </div>

        <!-- Wizualizacja Rozdzielacza -->
        <div class="manifold-viewport">
          <div class="manifold-frame">
            <div class="manifold-station">
              
              <!-- Zawory wejściowe z termometrami -->
              <div class="manifold-inlet">
                <div class="valve-block">
                  <div class="valve-handle valve-supply">35°</div>
                  <div class="temp-dial">ZASILANIE</div>
                </div>
                <div class="valve-block">
                  <div class="valve-handle valve-return">30°</div>
                  <div class="temp-dial">POWRÓT</div>
                </div>
              </div>

              <!-- Belki rozdzielacza i rotametry -->
              <div class="manifold-bars">
                <!-- Belka górna (Zasilająca) z rotametrami -->
                <div class="steel-bar">
                  <div class="sections-row" id="rotameters-row"></div>
                </div>

                <!-- Belka dolna (Powrotna) z zaworami -->
                <div class="steel-bar">
                  <div class="bottom-sections-row" id="actuators-row"></div>
                </div>
              </div>

              <!-- Prawa strona: Odpowietrzniki -->
              <div class="manifold-outlet">
                <div class="air-vent" title="Odpowietrznik automatyczny"></div>
                <div class="air-vent" title="Zawór spustowy"></div>
              </div>

            </div>

            <!-- Karty obiegów pod belką -->
            <div class="loops-details-grid" id="loops-details"></div>
          </div>
        </div>

      </div>
    `;
    this.updateCard();
  }

  updateCard() {
    if (!this.shadowRoot) return;

    const t = this.t;
    const states = (this._hass && this._hass.states) || {};

    // 1. Zbieranie rozdzielaczy z encji HA
    const manifolds = {};
    const loops = [];

    Object.keys(states).forEach((entityId) => {
      const stateObj = states[entityId];
      if (!stateObj) return;

      // Wykrywanie rozdzielacza
      if (entityId.includes("manifold_") && entityId.includes("_total_flow")) {
        const mId = stateObj.attributes.manifold_id || entityId.split("manifold_")[1].split("_total_flow")[0];
        manifolds[mId] = {
          id: mId,
          name: stateObj.attributes.friendly_name?.replace(" Sumaryczny przepływ", "") || mId,
          total_flow_lh: parseFloat(stateObj.state) || 0,
        };
      }

      // Wykrywanie pętli (poprzez encję rotametru l/min lub l/h)
      if (entityId.includes("rotameter_flow_lmin") || (entityId.includes("loop_") && entityId.includes("_status"))) {
        const attrs = stateObj.attributes || {};
        if (attrs.section_number !== undefined || attrs.loop_id) {
          loops.push({
            entity_id: entityId,
            loop_id: attrs.loop_id,
            section: attrs.section_number || 1,
            room: attrs.room_name || attrs.zone_name || "Pomieszczenie",
            flow_lmin: parseFloat(stateObj.state) || parseFloat(attrs.current_flow_lmin) || 1.5,
            flow_lh: parseFloat(attrs.current_flow_lh) || (parseFloat(stateObj.state) * 60) || 90,
            req_lmin: parseFloat(attrs.required_flow_lmin) || 1.5,
            length_m: parseFloat(attrs.loop_length_m) || 75.0,
            dp_kpa: parseFloat(attrs.pressure_drop_kpa) || 8.5,
            screed: attrs.screed_type ? `${attrs.screed_type} ${attrs.screed_thickness_mm || 50}mm` : "Wylewka 50mm",
            area_m2: parseFloat(attrs.area_m2) || 15.0,
            status: attrs.status || "optymalny",
            manifold_id: attrs.manifold_id || Object.keys(manifolds)[0] || "parter",
          });
        }
      }
    });

    // Jeśli brak danych na żywo z serwera, wygeneruj eleganckie demo
    if (Object.keys(manifolds).length === 0) {
      manifolds["parter"] = { id: "parter", name: "Rozdzielacz Parter", total_flow_lh: 690 };
      manifolds["pietro"] = { id: "pietro", name: "Rozdzielacz Piętro", total_flow_lh: 480 };

      // Przykładowe pętle rozdzielacza
      const demoRooms = [
        { sec: 1, room: "Salon (P1)", lmin: 1.8, req: 1.8, area: 18.5, len: 86.4, scr: "Cement 50mm" },
        { sec: 2, room: "Salon (P2)", lmin: 1.8, req: 1.8, area: 18.5, len: 88.0, scr: "Cement 50mm" },
        { sec: 3, room: "Kuchnia", lmin: 1.5, req: 1.5, area: 14.0, len: 65.0, scr: "Płytki 50mm" },
        { sec: 4, room: "Hol / Wiatrołap", lmin: 1.0, req: 1.2, area: 8.0, len: 42.0, scr: "Płytki 50mm" },
        { sec: 5, room: "Łazienka dół", lmin: 1.6, req: 1.6, area: 9.0, len: 54.0, scr: "Anhydryt 45mm" },
        { sec: 6, room: "Gabinet", lmin: 1.4, req: 1.4, area: 13.0, len: 62.0, scr: "Panele 50mm" },
        { sec: 7, room: "Garaż", lmin: 0.8, req: 1.2, area: 20.0, len: 78.0, scr: "Cement 70mm", status: "zdławiony" },
        { sec: 8, room: "Kotłownia", lmin: 0.6, req: 0.6, area: 6.0, len: 30.0, scr: "Płytki 50mm" },
      ];

      demoRooms.forEach(d => {
        loops.push({
          entity_id: `number.petla_parter_${d.sec}_rotameter_flow_lmin`,
          loop_id: `petla_parter_${d.sec}`,
          section: d.sec,
          room: d.room,
          flow_lmin: d.lmin,
          flow_lh: d.lmin * 60,
          req_lmin: d.req,
          length_m: d.len,
          dp_kpa: (d.len * 0.12).toFixed(1),
          screed: d.scr,
          area_m2: d.area,
          status: d.status || "optymalny",
          manifold_id: "parter",
        });
      });
    }

    if (!this._activeManifoldId || !manifolds[this._activeManifoldId]) {
      this._activeManifoldId = Object.keys(manifolds)[0];
    }

    const currentM = manifolds[this._activeManifoldId];
    const currentLoops = loops.filter(l => l.manifold_id === this._activeManifoldId || !l.manifold_id);
    currentLoops.sort((a, b) => a.section - b.section);

    // 2. Renderowanie zakładek rozdzielaczy
    const tabsContainer = this.shadowRoot.getElementById("manifold-tabs");
    if (tabsContainer) {
      tabsContainer.innerHTML = Object.values(manifolds).map(m => `
        <button class="tab-btn ${m.id === this._activeManifoldId ? "active" : ""}" data-mid="${m.id}">
          ${m.name}
        </button>
      `).join("");

      tabsContainer.querySelectorAll(".tab-btn").forEach(btn => {
        btn.onclick = () => {
          this._activeManifoldId = btn.getAttribute("data-mid");
          this.updateCard();
        };
      });
    }

    // 3. Podsumowanie rozdzielacza
    const totalFlowLh = currentLoops.reduce((acc, l) => acc + (l.flow_lh || 0), 0);
    const totalFlowLmin = (totalFlowLh / 60.0).toFixed(1);
    const sumFlow = this.shadowRoot.getElementById("sum-flow");
    const sumFlowLh = this.shadowRoot.getElementById("sum-flow-lh");
    const sumLoops = this.shadowRoot.getElementById("sum-loops");
    const cardTitle = this.shadowRoot.getElementById("card-title");

    if (sumFlow) sumFlow.textContent = `${totalFlowLmin} l/min`;
    if (sumFlowLh) sumFlowLh.textContent = `${Math.round(totalFlowLh)}`;
    if (sumLoops) sumLoops.textContent = `${currentLoops.length}`;
    if (cardTitle && currentM) cardTitle.textContent = currentM.name;

    // 4. Rysowanie rotametrów i siłowników na belkach
    const rotametersRow = this.shadowRoot.getElementById("rotameters-row");
    const actuatorsRow = this.shadowRoot.getElementById("actuators-row");
    const loopsDetails = this.shadowRoot.getElementById("loops-details");

    if (!rotametersRow || !actuatorsRow || !loopsDetails) return;

    rotametersRow.innerHTML = currentLoops.map(loop => {
      // Skala 0-5 l/min (max wysokość 70px)
      const fillHeightPct = Math.min(Math.max((loop.flow_lmin / 4.0) * 100, 8), 92);
      return `
        <div class="section-unit">
          <div class="rotameter-assembly" title="${loop.room}: ${loop.flow_lmin} l/min">
            <div class="rotameter-brass-cap"></div>
            <div class="glass-tube">
              <div class="glass-water" style="height: ${fillHeightPct}%;"></div>
              <div class="glass-float" style="bottom: ${fillHeightPct}%;"></div>
              <div class="glass-scale-mark" style="top: 20%;"></div>
              <div class="glass-scale-mark" style="top: 40%;"></div>
              <div class="glass-scale-mark" style="top: 60%;"></div>
              <div class="glass-scale-mark" style="top: 80%;"></div>
            </div>
          </div>
        </div>
      `;
    }).join("");

    actuatorsRow.innerHTML = currentLoops.map(loop => `
      <div class="section-unit">
        <div class="actuator-cap" title="Zawór pętli ${loop.section}"></div>
      </div>
    `).join("");

    // 5. Karty obiegów pod spodem z przyciskami regulacji
    loopsDetails.innerHTML = currentLoops.map((loop, idx) => {
      const isOptimal = loop.status === "optymalny";
      const isWarn = loop.status === "zdławiony" || loop.status === "zawyżony";
      const colClass = isOptimal ? "opt" : isWarn ? "warn" : "crit";

      return `
        <div class="loop-col ${colClass}">
          <div style="font-size:0.7rem; color:var(--sec-color); font-weight:700;">SEKCJA ${loop.section}</div>
          <div class="loop-room" title="${loop.room}">${loop.room}</div>
          <div class="loop-meta">${loop.area_m2} m² • ${loop.length_m} m</div>

          <!-- Regulacja przepływu l/min -->
          <div class="flow-stepper">
            <button class="step-btn" data-idx="${idx}" data-step="-0.1">-</button>
            <span class="flow-val">${loop.flow_lmin.toFixed(1)} <small style="font-size:0.65em">l/m</small></span>
            <button class="step-btn" data-idx="${idx}" data-step="+0.1">+</button>
          </div>

          <div class="loop-meta">Wymagany: <b>${loop.req_lmin.toFixed(1)} l/m</b></div>
          <div class="loop-meta" style="font-size:0.68rem; margin-top:2px;">${loop.screed}</div>
        </div>
      `;
    }).join("");

    // Obsługa przycisków regulacji
    loopsDetails.querySelectorAll(".step-btn").forEach(btn => {
      btn.onclick = () => {
        const idx = parseInt(btn.getAttribute("data-idx"));
        const step = parseFloat(btn.getAttribute("data-step"));
        const targetLoop = currentLoops[idx];
        if (!targetLoop) return;

        const newLmin = Math.max(0, Math.min(6.0, parseFloat((targetLoop.flow_lmin + step).toFixed(1))));
        targetLoop.flow_lmin = newLmin;
        targetLoop.flow_lh = newLmin * 60;

        // Jeśli encja istnieje w HA, wywołaj usługę Home Assistant
        if (this._hass && targetLoop.entity_id) {
          const isLminEntity = targetLoop.entity_id.includes("lmin");
          this._hass.callService("number", "set_value", {
            entity_id: targetLoop.entity_id,
            value: isLminEntity ? newLmin : (newLmin * 60),
          });
        }

        this.updateCard();
      };
    });
  }
}

customElements.define("underfloor-heating-card", UnderfloorHeatingCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "underfloor-heating-card",
  name: "Underfloor Heating Manifold Card",
  preview: true,
  description: "Wizualizacja rozdzielacza podłogówki z rotametrami i regulacją l/min (RWD)"
});
