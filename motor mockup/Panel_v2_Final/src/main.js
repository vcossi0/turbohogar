/**
 * main.js — Nesting Industrial UXP Plugin
 * ========================================
 * Puente entre Adobe Illustrator y el Motor de Anidamiento (FastAPI).
 *
 * Flujo:
 *   1. Extraer geometría de la selección → PathPoints + FillColor
 *   2. Serializar a JSON (contrato 03_MODULO_ILLUSTRATOR_UXP)
 *   3. Enviar a http://127.0.0.1:8765/nest (o /validate)
 *   4. Mostrar progreso por color con barras individuales
 *   5. Re-inyectar coordenadas optimizadas en el lienzo
 */

// ─── Configuración ─────────────────────────────────────────────
const API_BASE = "http://127.0.0.1:8765";
const BEZIER_TOLERANCE = 0.05; // mm — resolución de poligonalización

// ─── Estado ────────────────────────────────────────────────────
let lastResult = null;
let isProcessing = false;

// ─── Referencias DOM ───────────────────────────────────────────
const statusDot       = document.getElementById("statusDot");
const btnValidate     = document.getElementById("btnValidate");
const btnNest         = document.getElementById("btnNest");
const btnApply        = document.getElementById("btnApply");
const progressSection = document.getElementById("progressSection");
const reportCard      = document.getElementById("reportCard");
const logArea         = document.getElementById("logArea");
const pieceCountEl    = document.getElementById("pieceCount");

// Report fields
const rptEfficiency = document.getElementById("rptEfficiency");
const rptOptimized  = document.getElementById("rptOptimized");
const rptManual     = document.getElementById("rptManual");
const rptSaved      = document.getElementById("rptSaved");
const suggestionsArea = document.getElementById("suggestionsArea");

// ═══════════════════════════════════════════════════════════════
// 1. LOGGING
// ═══════════════════════════════════════════════════════════════

function log(msg, level = "info") {
  const line = document.createElement("div");
  line.className = `log-line ${level}`;
  line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  logArea.appendChild(line);
  logArea.scrollTop = logArea.scrollHeight;
}

// ═══════════════════════════════════════════════════════════════
// 2. SERVER HEALTH CHECK
// ═══════════════════════════════════════════════════════════════

async function checkServer() {
  try {
    statusDot.className = "status-dot connecting";
    statusDot.dataset.tooltip = "Conectando...";

    const resp = await fetch(`${API_BASE}/health`, { method: "GET" });
    if (resp.ok) {
      statusDot.className = "status-dot connected";
      statusDot.dataset.tooltip = "Servidor conectado";
      log("Servidor conectado ✓", "success");
      return true;
    }
  } catch (e) {
    // ignore
  }
  statusDot.className = "status-dot disconnected";
  statusDot.dataset.tooltip = "Servidor desconectado";
  log("Servidor no disponible. Ejecutar: python -m engine.main", "error");
  return false;
}

// ═══════════════════════════════════════════════════════════════
// 3. EXTRACCIÓN DE GEOMETRÍA DE ILLUSTRATOR
// ═══════════════════════════════════════════════════════════════

/**
 * Extrae la geometría de la selección actual de Illustrator.
 * Devuelve un array de objetos GeometryModel.
 */
function extractGeometries() {
  const app = require("illustrator").app;
  const doc = app.activeDocument;
  const selection = doc.selection;

  if (!selection || selection.length === 0) {
    log("No hay objetos seleccionados.", "warn");
    return [];
  }

  const geometries = [];
  let idCounter = 1;

  for (let i = 0; i < selection.length; i++) {
    const item = selection[i];
    const geo = extractSingleItem(item, idCounter);
    if (geo) {
      geometries.push(geo);
      idCounter++;
    }
  }

  pieceCountEl.textContent = `${geometries.length} piezas`;
  log(`Extraídas ${geometries.length} piezas de la selección.`);
  return geometries;
}

/**
 * Extrae PathPoints y color de un PathItem individual.
 */
function extractSingleItem(item, id) {
  // Solo PathItems (no grupos, texto, etc.)
  if (!item.pathPoints && !item.pathItems) return null;

  // Si es un CompoundPathItem, tomar el primer sub-path
  let pathItem = item;
  if (item.pathItems && item.pathItems.length > 0) {
    pathItem = item.pathItems[0];
  }

  if (!pathItem.pathPoints || pathItem.pathPoints.length < 3) return null;

  // ─── Extraer puntos ───
  const points = [];
  const pathPoints = [];

  for (let j = 0; j < pathItem.pathPoints.length; j++) {
    const pp = pathItem.pathPoints[j];
    const anchor = [pp.anchor[0], pp.anchor[1]];
    const left   = [pp.leftDirection[0], pp.leftDirection[1]];
    const right  = [pp.rightDirection[0], pp.rightDirection[1]];

    points.push(anchor);
    pathPoints.push({ anchor, leftDirection: left, rightDirection: right });
  }

  // ─── Extraer color ───
  const colorId = extractColor(pathItem);

  // ─── Centro original ───
  const cx = points.reduce((s, p) => s + p[0], 0) / points.length;
  const cy = points.reduce((s, p) => s + p[1], 0) / points.length;

  return {
    id: id,
    color_id: colorId,
    points: points,
    is_closed: pathItem.closed !== false,
    path_points: pathPoints,
    original_center: [cx, cy],
  };
}

/**
 * Extrae el color de relleno como hex #RRGGBB.
 */
function extractColor(item) {
  try {
    const fill = item.fillColor;

    // RGB
    if (fill.typename === "RGBColor" || fill.red !== undefined) {
      const r = Math.round(fill.red).toString(16).padStart(2, "0");
      const g = Math.round(fill.green).toString(16).padStart(2, "0");
      const b = Math.round(fill.blue).toString(16).padStart(2, "0");
      return `#${r}${g}${b}`.toUpperCase();
    }

    // CMYK → RGB conversion
    if (fill.typename === "CMYKColor" || fill.cyan !== undefined) {
      const c = fill.cyan / 100;
      const m = fill.magenta / 100;
      const y = fill.yellow / 100;
      const k = fill.black / 100;
      const r = Math.round(255 * (1 - c) * (1 - k));
      const g = Math.round(255 * (1 - m) * (1 - k));
      const b = Math.round(255 * (1 - y) * (1 - k));
      return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`.toUpperCase();
    }

    // Spot Color
    if (fill.typename === "SpotColor" || fill.spot) {
      const spot = fill.spot || fill;
      return spot.name || "#000000";
    }
  } catch (e) {
    // fallback
  }
  return "#000000";
}

// ═══════════════════════════════════════════════════════════════
// 4. CONSTRUIR PAYLOAD JSON
// ═══════════════════════════════════════════════════════════════

function buildPayload(geometries) {
  const width  = parseFloat(document.getElementById("canvasWidth").value)  || 1200;
  const height = parseFloat(document.getElementById("canvasHeight").value) || 3000;
  const margin = parseFloat(document.getElementById("margin").value)       || 2.0;
  const mode   = document.getElementById("packingMode").value;
  const time   = parseFloat(document.getElementById("maxTime").value)      || 30;
  const rots   = document.getElementById("rotations").value.split(",").map(Number);

  return {
    session_id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    settings: {
      canvas_width: width,
      canvas_height: height,
      margin: margin,
      unit: "mm",
      packing_mode: mode,
      max_time_seconds: time,
      rotations: rots,
      efficiency_threshold: 85.0,
    },
    geometries: geometries,
  };
}

// ═══════════════════════════════════════════════════════════════
// 5. PROGRESO POR COLOR
// ═══════════════════════════════════════════════════════════════

function showColorBins(geometries) {
  progressSection.innerHTML = "";
  const colors = {};
  geometries.forEach(g => {
    if (!colors[g.color_id]) colors[g.color_id] = 0;
    colors[g.color_id]++;
  });

  for (const [colorId, count] of Object.entries(colors)) {
    const card = document.createElement("div");
    card.className = "bin-card active fade-in";
    card.id = `bin-${colorId.replace("#", "")}`;
    card.innerHTML = `
      <div class="bin-header">
        <div class="color-swatch" style="background:${colorId}"></div>
        <span class="bin-color-id">${colorId}</span>
        <span class="bin-stats">${count} piezas</span>
      </div>
      <div class="progress-bar-container">
        <div class="progress-bar-fill" id="pb-${colorId.replace("#", "")}"></div>
      </div>
      <div class="metrics-row">
        <div class="metric">Eficiencia: <span class="value" id="eff-${colorId.replace("#", "")}">—</span></div>
        <div class="metric">Waterline: <span class="value" id="wl-${colorId.replace("#", "")}">—</span></div>
      </div>
    `;
    progressSection.appendChild(card);
  }
}

function updateBinResult(colorId, binResult) {
  const safeId = colorId.replace("#", "");
  const card = document.getElementById(`bin-${safeId}`);
  const pb   = document.getElementById(`pb-${safeId}`);
  const eff  = document.getElementById(`eff-${safeId}`);
  const wl   = document.getElementById(`wl-${safeId}`);

  if (!card) return;

  card.className = "bin-card done fade-in";
  if (pb)  {
    pb.style.width = `${Math.min(binResult.efficiency_pct, 100)}%`;
    pb.className = `progress-bar-fill ${binResult.efficiency_pct >= 85 ? "success" : binResult.efficiency_pct >= 70 ? "" : "warning"}`;
  }
  if (eff) eff.textContent = `${binResult.efficiency_pct}%`;
  if (wl)  wl.textContent = `${binResult.waterline_mm}mm`;
}

// ═══════════════════════════════════════════════════════════════
// 6. MOSTRAR REPORTE
// ═══════════════════════════════════════════════════════════════

function showReport(response) {
  reportCard.classList.remove("hidden");

  // Eficiencia global
  const ge = response.postflight.global_efficiency;
  rptEfficiency.textContent = `${ge}%`;
  rptEfficiency.className = `value ${ge >= 85 ? "good" : ge >= 70 ? "" : "bad"}`;

  // Ahorro
  const sr = response.savings_report;
  rptOptimized.textContent = `${sr.optimized_roll_length_m}m`;
  rptManual.textContent = `${sr.manual_estimate_m}m`;
  rptSaved.textContent = `${sr.material_saved_m}m (${sr.savings_pct}%)`;

  // Sugerencias
  suggestionsArea.innerHTML = "";
  if (response.postflight.suggestions && response.postflight.suggestions.length > 0) {
    response.postflight.suggestions.forEach(s => {
      const div = document.createElement("div");
      div.className = "suggestion";
      div.innerHTML = `<span class="icon">⚠️</span> ${s}`;
      suggestionsArea.appendChild(div);
    });
  }
}

// ═══════════════════════════════════════════════════════════════
// 7. RE-INYECCIÓN EN EL LIENZO
// ═══════════════════════════════════════════════════════════════

/**
 * Aplica los resultados del anidamiento al documento de Illustrator.
 * Crea estructura de capas: ANIDAMIENTO_FECHA → CORTE_#HEX
 */
function applyResults() {
  if (!lastResult) {
    log("No hay resultado para aplicar.", "warn");
    return;
  }

  try {
    const app = require("illustrator").app;
    const doc = app.activeDocument;

    // Crear capa maestra
    const now = new Date();
    const timestamp = `${now.getFullYear()}${(now.getMonth()+1).toString().padStart(2,"0")}${now.getDate().toString().padStart(2,"0")}_${now.getHours().toString().padStart(2,"0")}${now.getMinutes().toString().padStart(2,"0")}`;
    const masterLayer = doc.layers.add();
    masterLayer.name = `ANIDAMIENTO_${timestamp}`;

    log(`Creada capa: ${masterLayer.name}`);

    // Para cada bin de color
    for (const bin of lastResult.bins) {
      const subLayer = masterLayer.layers.add();
      subLayer.name = `CORTE_${bin.color_id}`;

      for (const piece of bin.placed) {
        // Buscar el PathItem original por ID y moverlo
        const original = findOriginalItem(doc, piece.piece_id);
        if (!original) continue;

        // Mover a la sub-capa
        original.move(subLayer, ElementPlacement.PLACEATEND);

        // Aplicar transformación
        const matrix = app.getIdentityMatrix();

        // Rotación
        if (piece.rotation !== 0) {
          const rotMatrix = app.getRotationMatrix(piece.rotation);
          // Aplicar rotación centrada
          original.transform(rotMatrix, true, true, true, true, true);
        }

        // Posición
        original.position = [piece.position[0], -piece.position[1]]; // Illustrator Y invertido
      }

      log(`Color ${bin.color_id}: ${bin.placed.length} piezas posicionadas.`, "success");
    }

    log("✅ Anidamiento aplicado correctamente.", "success");

  } catch (e) {
    log(`Error al aplicar: ${e.message}`, "error");
  }
}

/**
 * Busca un PathItem en el documento por su orden de selección (id).
 * Esto asume que los IDs se asignaron secuencialmente durante la extracción.
 */
function findOriginalItem(doc, pieceId) {
  const selection = doc.selection;
  if (selection && pieceId <= selection.length) {
    return selection[pieceId - 1];
  }
  return null;
}

// ═══════════════════════════════════════════════════════════════
// 8. API CALLS
// ═══════════════════════════════════════════════════════════════

async function callValidate(payload) {
  log("Ejecutando pre-flight check...");
  const resp = await fetch(`${API_BASE}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }

  const data = await resp.json();
  log(`Validación: ${data.valid_count} válidas, ${data.invalid_count} con error.`,
      data.invalid_count > 0 ? "warn" : "success");

  if (data.issues) {
    data.issues.forEach(issue => {
      log(`  [${issue.severity}] ${issue.message}`, issue.severity === "error" ? "error" : "warn");
    });
  }

  return data;
}

async function callNest(payload) {
  log("Iniciando motor de anidamiento...");
  const resp = await fetch(`${API_BASE}/nest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail?.error || JSON.stringify(err.detail) || `HTTP ${resp.status}`);
  }

  return await resp.json();
}

// ═══════════════════════════════════════════════════════════════
// 9. EVENT HANDLERS
// ═══════════════════════════════════════════════════════════════

btnValidate.addEventListener("click", async () => {
  if (isProcessing) return;
  isProcessing = true;
  btnValidate.disabled = true;

  try {
    const online = await checkServer();
    if (!online) return;

    const geometries = extractGeometries();
    if (geometries.length === 0) return;

    const payload = buildPayload(geometries);
    await callValidate(payload);
  } catch (e) {
    log(`Error: ${e.message}`, "error");
  } finally {
    isProcessing = false;
    btnValidate.disabled = false;
  }
});

btnNest.addEventListener("click", async () => {
  if (isProcessing) return;
  isProcessing = true;
  btnNest.disabled = true;
  reportCard.classList.add("hidden");

  try {
    const online = await checkServer();
    if (!online) return;

    const geometries = extractGeometries();
    if (geometries.length === 0) return;

    showColorBins(geometries);
    const payload = buildPayload(geometries);

    // Pre-flight
    const validation = await callValidate(payload);
    if (validation.invalid_count > 0 && validation.valid_count === 0) {
      log("Todas las piezas son inválidas. Abortando.", "error");
      return;
    }

    // Nest
    const result = await callNest(payload);
    lastResult = result;

    // Actualizar bins
    for (const bin of result.bins) {
      updateBinResult(bin.color_id, bin);
    }

    // Mostrar reporte
    showReport(result);

    log(`Anidamiento completado: ${result.status}`, result.status === "ok" ? "success" : "warn");

  } catch (e) {
    log(`Error: ${e.message}`, "error");
  } finally {
    isProcessing = false;
    btnNest.disabled = false;
  }
});

btnApply.addEventListener("click", () => {
  applyResults();
});

// ═══════════════════════════════════════════════════════════════
// 10. INIT
// ═══════════════════════════════════════════════════════════════

(async function init() {
  log("Inicializando panel Nesting Industrial...");
  await checkServer();
})();
