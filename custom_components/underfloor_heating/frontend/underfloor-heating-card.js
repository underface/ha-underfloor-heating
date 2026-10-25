/**
 * Underfloor Heating Lovelace Card (RWD)
 * Karta wizualizacji i kontroli rozdzielaczy, stref oraz rotametrów ogrzewania podłogowego.
 *
 * Wersja: 1.0.0
 */

class UnderfloorHeatingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    this._config = config || {};
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.updateCard();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          --primary-color: #03a9f4;
          --card-bg: var(--ha-card-background, #ffffff);
          --text-color: var(--primary-text-color, #212121);
          --secondary-text: var(--secondary-text-color, #757575);
          --success-color: #4caf50;
          --warning-color: #ff9800;
          --danger-color: #f44336;
          --border-color: var(--divider-color, rgba(0, 0, 0, 0.12));
        }

        .card-container {
          background: var(--card-bg);
          color: var(--text-color);
          border-radius: 16px;
          box-shadow: var(--ha-card-box-shadow, 0 4px 14px rgba(0,0,0,0.08));
          padding: 16px;
          box-sizing: border-box;
          max-width: 100%;
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid var(--border-color);
          padding-bottom: 12px;
          margin-bottom: 16px;
          flex-wrap: wrap;
          gap: 8px;
        }

        .title {
          font-size: 1.25rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .badge-status {
          font-size: 0.75rem;
          font-weight: 600;
          padding: 4px 10px;
          border-radius: 20px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .badge-optimal {
          background-color: rgba(76, 175, 80, 0.15);
          color: var(--success-color);
        }

        .badge-warning {
          background-color: rgba(255, 152, 0, 0.15);
          color: var(--warning-color);
        }

        .badge-danger {
          background-color: rgba(244, 67, 54, 0.15);
          color: var(--danger-color);
        }

        /* Siatka RWD dla pętli podłogówki */
        .loops-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 16px;
        }

        @media (max-width: 600px) {
          .loops-grid {
            grid-template-columns: 1fr;
          }
          .card-container {
            padding: 12px;
          }
        }

        .loop-card {
          border: 1px solid var(--border-color);
          border-radius: 12px;
          padding: 14px;
          background: rgba(125, 125, 125, 0.03);
          display: flex;
          flex-direction: column;
          gap: 10px;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .loop-card:hover {
          box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        }

        .loop-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .loop-title {
          font-weight: 600;
          font-size: 1rem;
        }

        .loop-section {
          font-size: 0.8rem;
          color: var(--secondary-text);
          background: rgba(0, 0, 0, 0.05);
          padding: 2px 6px;
          border-radius: 4px;
        }

        /* Graficzny rotametr RWD */
        .rotameter-wrapper {
          display: flex;
          align-items: center;
          gap: 12px;
          background: rgba(0,0,0,0.02);
          border-radius: 8px;
          padding: 8px 12px;
        }

        .rotameter-tube {
          width: 22px;
          height: 90px;
          background: #e0f2fe;
          border: 2px solid #0284c7;
          border-radius: 6px;
          position: relative;
          overflow: hidden;
          flex-shrink: 0;
        }

        .water-fill {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          background: linear-gradient(180deg, #38bdf8 0%, #0284c7 100%);
          transition: height 0.3s ease;
        }

        .float-indicator {
          position: absolute;
          left: 2px;
          right: 2px;
          height: 6px;
          background: #ef4444;
          border-radius: 2px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.4);
          transition: bottom 0.3s ease;
        }

        .rotameter-data {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .flow-values {
          display: flex;
          justify-content: space-between;
          font-size: 0.9rem;
        }

        .flow-current {
          font-size: 1.15rem;
          font-weight: 700;
          color: #0284c7;
        }

        .flow-req {
          font-size: 0.8rem;
          color: var(--secondary-text);
        }

        .controls {
          display: flex;
          gap: 6px;
          margin-top: 4px;
        }

        .btn-ctrl {
          border: none;
          background: #0284c7;
          color: white;
          padding: 4px 10px;
          border-radius: 6px;
          cursor: pointer;
          font-weight: bold;
          font-size: 0.9rem;
          transition: opacity 0.2s;
        }

        .btn-ctrl:active {
          opacity: 0.7;
        }

        /* Właściwości techniczne i wylewka */
        .specs-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 6px;
          font-size: 0.8rem;
          color: var(--secondary-text);
          background: rgba(0,0,0,0.02);
          padding: 8px;
          border-radius: 6px;
        }

        .spec-item {
          display: flex;
          flex-direction: column;
        }

        .spec-label {
          font-size: 0.7rem;
          text-transform: uppercase;
        }

        .spec-val {
          font-weight: 600;
          color: var(--text-color);
        }

        .warnings-box {
          font-size: 0.75rem;
          color: var(--danger-color);
          background: rgba(244, 67, 54, 0.08);
          border-radius: 6px;
          padding: 6px 8px;
          line-height: 1.3;
        }
      </style>

      <div class="card-container">
        <div class="header">
          <div class="title">
            <span>🔥</span>
            <span id="manifold-title">Rozdzielacz Podłogówki</span>
          </div>
          <div id="manifold-badge" class="badge-status badge-optimal">Zrównoważony</div>
        </div>

        <div class="loops-grid" id="loops-container">
          <!-- Dynamicznie generowane pętle -->
        </div>
      </div>
    `;
  }

  updateCard() {
    if (!this._hass || !this.shadowRoot) return;

    const container = this.shadowRoot.getElementById('loops-container');
    if (!container) return;

    // Przeszukiwanie encji powiązanych z integracją underfloor_heating
    const entities = Object.keys(this._hass.states).filter(e => e.includes('rotameter_flow_lh') || e.includes('loop_'));
    
    // Jeśli brak encji na żywo, karta prezentuje interaktywny widok demonstracyjny
    if (entities.length === 0) {
      this.renderDemoView();
      return;
    }

    // Dynamiczna prezentacja encji w HA
    // ...
  }

  renderDemoView() {
    const container = this.shadowRoot.getElementById('loops-container');
    if (!container) return;

    const sampleLoops = [
      {
        id: "salon_1",
        name: "Salon Pętla 1",
        section: "Obwód 1",
        flow_lh: 110,
        flow_req_lh: 115,
        length_m: 85.5,
        dp_kpa: 11.2,
        screed: "Anhydryt 50mm",
        inertia: "0.6 h",
        status: "optymalny",
      },
      {
        id: "salon_2",
        name: "Salon Pętla 2",
        section: "Obwód 2",
        flow_lh: 115,
        flow_req_lh: 115,
        length_m: 88.0,
        dp_kpa: 12.1,
        screed: "Anhydryt 50mm",
        inertia: "0.6 h",
        status: "optymalny",
      },
      {
        id: "lazienka",
        name: "Łazienka Piętro",
        section: "Obwód 3",
        flow_lh: 65,
        flow_req_lh: 95,
        length_m: 54.0,
        dp_kpa: 5.8,
        screed: "Cement 65mm",
        inertia: "1.4 h",
        status: "zdławiony",
        warning: "Przepływ zdławiony (-31%). Otwórz rotametr.",
      },
      {
        id: "sypialnia",
        name: "Sypialnia Główna",
        section: "Obwód 4",
        flow_lh: 140,
        flow_req_lh: 90,
        length_m: 72.0,
        dp_kpa: 14.5,
        screed: "Cement 65mm",
        inertia: "1.8 h",
        status: "przewymiarowany",
        warning: "Zbyt duży przepływ (+55%). Pętla zabiera przepływ innym.",
      }
    ];

    container.innerHTML = sampleLoops.map(loop => {
      const fillPct = Math.min(Math.max((loop.flow_lh / 200) * 100, 5), 95);
      const isOptimal = loop.status === "optymalny";
      const isWarning = loop.status === "zdławiony" || loop.status === "przewymiarowany";
      const badgeClass = isOptimal ? "badge-optimal" : isWarning ? "badge-warning" : "badge-danger";

      return `
        <div class="loop-card">
          <div class="loop-header">
            <span class="loop-title">${loop.name}</span>
            <span class="loop-section">${loop.section}</span>
          </div>

          <div class="rotameter-wrapper">
            <div class="rotameter-tube">
              <div class="water-fill" style="height: ${fillPct}%;"></div>
              <div class="float-indicator" style="bottom: ${fillPct}%;"></div>
            </div>

            <div class="rotameter-data">
              <div class="flow-values">
                <span class="flow-current">${loop.flow_lh} <small style="font-size:0.65em">l/h</small></span>
                <span class="flow-req">Wymagany: <b>${loop.flow_req_lh} l/h</b></span>
              </div>
              <div style="font-size: 0.75rem; color: var(--secondary-text)">
                Skala rotametru: ${(loop.flow_lh / 60).toFixed(2)} l/min
              </div>
              <div class="controls">
                <button class="btn-ctrl" onclick="alert('Zmieniono przepływ ${loop.name} o -5 l/h')">-5</button>
                <button class="btn-ctrl" onclick="alert('Zmieniono przepływ ${loop.name} o +5 l/h')">+5</button>
              </div>
            </div>
          </div>

          <div class="specs-grid">
            <div class="spec-item">
              <span class="spec-label">Długość pętli</span>
              <span class="spec-val">${loop.length_m} m</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Spadek ciśnienia</span>
              <span class="spec-val">${loop.dp_kpa} kPa</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Wylewka</span>
              <span class="spec-val">${loop.screed}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">Bezwładność</span>
              <span class="spec-val">${loop.inertia}</span>
            </div>
          </div>

          ${loop.warning ? `<div class="warnings-box">⚠️ ${loop.warning}</div>` : ''}
        </div>
      `;
    }).join('');
  }
}

customElements.define('underfloor-heating-card', UnderfloorHeatingCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "underfloor-heating-card",
  name: "Underfloor Heating Card",
  preview: true,
  description: "Responsywna karta rozdzielaczy, stref i rotametrów podłogówki (RWD)"
});

