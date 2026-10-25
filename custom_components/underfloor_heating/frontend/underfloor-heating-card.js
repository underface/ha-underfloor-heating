/**
 * Underfloor Heating Lovelace Card (RWD)
 * Wielojęzyczna karta wizualizacji i kontroli rozdzielaczy, stref oraz rotametrów podłogówki.
 * Obsługuje automatyczne wykrywanie języka użytkownika w Home Assistant (PL, EN, DE, ES).
 *
 * Wersja: 1.0.0
 */

const I18N = {
  pl: {
    manifold_title: "Rozdzielacz Podłogówki",
    balanced: "Zrównoważony",
    unbalanced: "Wymaga regulacji",
    section: "Obwód",
    required: "Wymagany",
    scale: "Skala rotametru",
    loop_length: "Długość pętli",
    pressure_drop: "Spadek ciśnienia",
    screed: "Wylewka",
    inertia: "Bezwładność",
    status_optimal: "Optymalny",
    status_underflow: "Zdławiony",
    status_overflow: "Przewymiarowany",
    status_critical: "Krytyczny",
    warn_underflow: "Przepływ zdławiony. Otwórz rotametr.",
    warn_overflow: "Zbyt duży przepływ. Pętla zabiera przepływ innym.",
    warn_length: "Długość przekracza dopuszczalny limit dla rury PEX 16x2!"
  },
  en: {
    manifold_title: "Heating Manifold",
    balanced: "Balanced",
    unbalanced: "Needs Balancing",
    section: "Loop",
    required: "Required",
    scale: "Rotameter scale",
    loop_length: "Loop length",
    pressure_drop: "Pressure drop",
    screed: "Screed",
    inertia: "Thermal inertia",
    status_optimal: "Optimal",
    status_underflow: "Throttled",
    status_overflow: "Oversized",
    status_critical: "Critical",
    warn_underflow: "Underflowing. Open rotameter valve.",
    warn_overflow: "Excessive flow. Loop is stealing flow from others.",
    warn_length: "Loop length exceeds safe threshold for 16x2 pipe!"
  },
  de: {
    manifold_title: "Heizkreisverteiler",
    balanced: "Abgeglichen",
    unbalanced: "Abgleich nötig",
    section: "Kreis",
    required: "Soll-Wert",
    scale: "Durchflussskala",
    loop_length: "Rohrlänge",
    pressure_drop: "Druckverlust",
    screed: "Estrich",
    inertia: "Trägheit",
    status_optimal: "Optimal",
    status_underflow: "Gedrosselt",
    status_overflow: "Überdimensioniert",
    status_critical: "Kritisch",
    warn_underflow: "Zu geringer Durchfluss. Durchflussmesser öffnen.",
    warn_overflow: "Zu hoher Durchfluss. Kreis stiehlt Durchfluss.",
    warn_length: "Rohrlänge überschreitet das Limit für 16x2 Rohr!"
  },
  es: {
    manifold_title: "Colector de Suelo Radiante",
    balanced: "Equilibrado",
    unbalanced: "Requiere ajuste",
    section: "Circuito",
    required: "Requerido",
    scale: "Escala caudalímetro",
    loop_length: "Longitud circuito",
    pressure_drop: "Pérdida de carga",
    screed: "Recrecido",
    inertia: "Inercia térmica",
    status_optimal: "Óptimo",
    status_underflow: "Estrangulado",
    status_overflow: "Sobredimensionado",
    status_critical: "Crítico",
    warn_underflow: "Caudal insuficiente. Abra el caudalímetro.",
    warn_overflow: "Caudal excesivo. El circuito roba caudal a otros.",
    warn_length: "¡Longitud excesiva para tubería 16x2!"
  }
};

class UnderfloorHeatingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
    this._lang = 'pl';
  }

  setConfig(config) {
    this._config = config || {};
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    // Automatyczne wykrycie języka profilu użytkownika w Home Assistant
    const detectedLang = (hass.locale && hass.locale.language) || hass.language || 'pl';
    this._lang = I18N[detectedLang] ? detectedLang : (detectedLang.startsWith('en') ? 'en' : (detectedLang.startsWith('de') ? 'de' : (detectedLang.startsWith('es') ? 'es' : 'pl')));
    this.updateCard();
  }

  get t() {
    return I18N[this._lang] || I18N['pl'];
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
            <span id="manifold-title">${this.t.manifold_title}</span>
          </div>
          <div id="manifold-badge" class="badge-status badge-optimal">${this.t.balanced}</div>
        </div>

        <div class="loops-grid" id="loops-container">
          <!-- Dynamicznie generowane pętle -->
        </div>
      </div>
    `;
    this.updateCard();
  }

  updateCard() {
    const container = this.shadowRoot ? this.shadowRoot.getElementById('loops-container') : null;
    if (!container) return;

    const t = this.t;

    // Przykładowe dane demo z tłumaczeniami
    const sampleLoops = [
      {
        id: "salon_1",
        name: "Salon (1)",
        section: `${t.section} 1`,
        flow_lh: 110,
        flow_req_lh: 115,
        length_m: 85.5,
        dp_kpa: 11.2,
        screed: "Anhydryt 50mm",
        inertia: "0.6 h",
        status: "optymalny",
      },
      {
        id: "lazienka",
        name: "Łazienka",
        section: `${t.section} 2`,
        flow_lh: 65,
        flow_req_lh: 95,
        length_m: 54.0,
        dp_kpa: 5.8,
        screed: "Cement 65mm",
        inertia: "1.4 h",
        status: "zdławiony",
        warning: t.warn_underflow,
      },
      {
        id: "sypialnia",
        name: "Sypialnia",
        section: `${t.section} 3`,
        flow_lh: 140,
        flow_req_lh: 90,
        length_m: 72.0,
        dp_kpa: 14.5,
        screed: "Cement 65mm",
        inertia: "1.8 h",
        status: "przewymiarowany",
        warning: t.warn_overflow,
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
                <span class="flow-req">${t.required}: <b>${loop.flow_req_lh} l/h</b></span>
              </div>
              <div style="font-size: 0.75rem; color: var(--secondary-text)">
                ${t.scale}: ${(loop.flow_lh / 60).toFixed(2)} l/min
              </div>
              <div class="controls">
                <button class="btn-ctrl" onclick="alert('-5 l/h')">-5</button>
                <button class="btn-ctrl" onclick="alert('+5 l/h')">+5</button>
              </div>
            </div>
          </div>

          <div class="specs-grid">
            <div class="spec-item">
              <span class="spec-label">${t.loop_length}</span>
              <span class="spec-val">${loop.length_m} m</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">${t.pressure_drop}</span>
              <span class="spec-val">${loop.dp_kpa} kPa</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">${t.screed}</span>
              <span class="spec-val">${loop.screed}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">${t.inertia}</span>
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
