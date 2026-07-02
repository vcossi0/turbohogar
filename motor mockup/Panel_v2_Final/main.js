/**
 * main.js — Panel CEP Nesting Industrial
 * =======================================
 * Adaptado de UXP a CEP.
 * Usa CSInterface para comunicarse con host.jsx (ExtendScript).
 * Usa fetch() para comunicarse con el servidor FastAPI.
 */

var csInterface = new CSInterface();
var API_BASE    = "http://127.0.0.1:8765";

var lastResult   = null;
var isProcessing = false;

// ─── Referencias DOM ────────────────────────────────────────────
var statusDot       = document.getElementById("statusDot");
var btnValidate     = document.getElementById("btnValidate");
var btnNest         = document.getElementById("btnNest");
var btnApply        = document.getElementById("btnApply");
var progressSection = document.getElementById("progressSection");
var reportCard      = document.getElementById("reportCard");
var logArea         = document.getElementById("logArea");
var pieceCountEl    = document.getElementById("pieceCount");
var rptEfficiency   = document.getElementById("rptEfficiency");
var rptOptimized    = document.getElementById("rptOptimized");
var rptManual       = document.getElementById("rptManual");
var rptSaved        = document.getElementById("rptSaved");
var suggestionsArea = document.getElementById("suggestionsArea");

// Elementos de Previsualización
var previewBinSelect = document.getElementById("previewBinSelect");
var previewCanvas    = document.getElementById("previewCanvas");
var ctx              = previewCanvas ? previewCanvas.getContext("2d") : null;

// ═══════════════════════════════════════════════════════════════
// 1. LOGGING
// ═══════════════════════════════════════════════════════════════
function log(msg, level) {
    level = level || "info";
    var line = document.createElement("div");
    line.className = "log-line " + level;
    var now = new Date();
    var t   = pad2(now.getHours()) + ":" + pad2(now.getMinutes()) + ":" + pad2(now.getSeconds());
    line.textContent = "[" + t + "] " + msg;
    logArea.appendChild(line);
    logArea.scrollTop = logArea.scrollHeight;
}
function pad2(n) { return n < 10 ? "0" + n : "" + n; }

// ═══════════════════════════════════════════════════════════════
// 1.5 COLOR NAMING
// ═══════════════════════════════════════════════════════════════
function getHumanColorName(hex) {
    var colors = {
        "#000000": "Negro", "#ffffff": "Blanco", "#ff0000": "Rojo",
        "#00ff00": "Verde", "#0000ff": "Azul", "#ffff00": "Amarillo",
        "#00ffff": "Cian", "#ff00ff": "Magenta", "#888888": "Gris",
        "#ffa500": "Naranja", "#800080": "Púrpura", "#a52a2a": "Marrón",
        "#ffc0cb": "Rosa", "#008000": "Verde Oscuro", "#000080": "Azul Marino",
        "#ffd700": "Dorado", "#c0c0c0": "Plateado", "#808080": "Gris Medio"
    };
    
    hex = hex.toLowerCase();
    if (colors[hex]) return colors[hex];
    
    var r = parseInt(hex.slice(1, 3), 16) || 0;
    var g = parseInt(hex.slice(3, 5), 16) || 0;
    var b = parseInt(hex.slice(5, 7), 16) || 0;
    
    var minDistance = Infinity;
    var closestName = hex;
    
    for (var k in colors) {
        var kr = parseInt(k.slice(1, 3), 16);
        var kg = parseInt(k.slice(3, 5), 16);
        var kb = parseInt(k.slice(5, 7), 16);
        var dist = Math.sqrt(Math.pow(r - kr, 2) + Math.pow(g - kg, 2) + Math.pow(b - kb, 2));
        if (dist < minDistance) {
            minDistance = dist;
            closestName = colors[k];
        }
    }
    return closestName;
}

// ═══════════════════════════════════════════════════════════════
// 2. HEALTH CHECK DEL SERVIDOR
// ═══════════════════════════════════════════════════════════════
function checkServer() {
    return new Promise(function(resolve) {
        statusDot.className = "status-dot connecting";
        fetch(API_BASE + "/health", { method: "GET" })
            .then(function(r) {
                if (r.ok) {
                    statusDot.className = "status-dot connected";
                    if (!window._serverConnectedMsg) {
                        log("Motor conectado y listo \u2713", "success");
                        window._serverConnectedMsg = true;
                    }
                    resolve(true);
                } else {
                    throw new Error("HTTP " + r.status);
                }
            })
            .catch(function() {
                if (!window._serverStartAttempted) {
                    window._serverStartAttempted = true;
                    log("Iniciando el motor de anidamiento en segundo plano...", "warn");
                    
                    try {
                        var extPath = csInterface.getSystemPath(SystemPath.EXTENSION);
                        var batPath = extPath + "/start_server.bat";
                        window.cep.process.createProcess(batPath);
                        
                        // Esperar 4 segundos a que el servidor levante e intentar de nuevo
                        setTimeout(function() {
                            checkServer().then(resolve);
                        }, 4000);
                    } catch (e) {
                        statusDot.className = "status-dot disconnected";
                        log("No se pudo auto-iniciar el servidor.", "error");
                        resolve(false);
                    }
                } else {
                    statusDot.className = "status-dot disconnected";
                    log("Servidor no disponible. Asegurate de tener Python instalado.", "error");
                    resolve(false);
                }
            });
    });
}

// ═══════════════════════════════════════════════════════════════
// 3. EXTRACCIÓN DE GEOMETRÍA (via ExtendScript)
// ═══════════════════════════════════════════════════════════════
function extractGeometries() {
    return new Promise(function(resolve) {
        var script = "try { extractGeometries(); } catch(e) { 'EXTENDSCRIPT_ERROR:' + e.message + ' (line ' + e.line + ')'; }";
        csInterface.evalScript(script, function(result) {
            if (result && typeof result === "string" && result.indexOf("EXTENDSCRIPT_ERROR:") === 0) {
                log("Error interno ExtendScript: " + result.substring(19), "error");
                resolve(null);
                return;
            }
            if (result === "EvalScript error.") {
                log("Error grave: El archivo host.jsx tiene un error de sintaxis y no cargó correctamente.", "error");
                resolve(null);
                return;
            }
            try {
                var data = JSON.parse(result);
                if (data.error) {
                    log("Error extracción: " + (data.message || data.error), "error");
                    resolve(null);
                    return;
                }
                var geos = data.geometries;
                pieceCountEl.textContent = geos.length + " piezas";
                log("Extraídas " + geos.length + " piezas de la selección.");
                resolve(geos);
            } catch (e) {
                log("Error parseando extracción: " + e.message + " (Recibido: " + result + ")", "error");
                resolve(null);
            }
        });
    });
}

// ═══════════════════════════════════════════════════════════════
// 4. INFO DEL DOCUMENTO (artboard en mm)
// ═══════════════════════════════════════════════════════════════
function getDocInfo() {
    return new Promise(function(resolve) {
        csInterface.evalScript("getDocumentInfo()", function(result) {
            try { resolve(JSON.parse(result)); }
            catch(e) { resolve({ width_mm: 1200, height_mm: 3000 }); }
        });
    });
}

// ═══════════════════════════════════════════════════════════════
// 5. CONSTRUIR PAYLOAD JSON
// ═══════════════════════════════════════════════════════════════
function buildPayload(geometries, docInfo) {
    var width  = parseFloat(document.getElementById("canvasWidth").value)  || (docInfo && docInfo.width_mm)  || 1200;
    var height = parseFloat(document.getElementById("canvasHeight").value) || (docInfo && docInfo.height_mm) || 3000;
    var margin = parseFloat(document.getElementById("margin").value)       || 2.0;
    var mode   = document.getElementById("packingMode").value;
    var time   = parseFloat(document.getElementById("maxTime").value)      || 30;
    var rotSel = document.getElementById("rotations").value;
    var rots   = rotSel.split(",").map(function(x) { return parseFloat(x); });

    return {
        session_id: generateUUID(),
        settings: {
            canvas_width: width,
            canvas_height: height,
            margin: margin,
            unit: "mm",
            packing_mode: mode,
            max_time_seconds: time,
            rotations: rots,
            efficiency_threshold: 85.0
        },
        geometries: geometries
    };
}

function generateUUID() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0;
        var v = c === "x" ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// ═══════════════════════════════════════════════════════════════
// 6. PROGRESO POR COLOR
// ═══════════════════════════════════════════════════════════════
function showColorBins(geometries) {
    progressSection.innerHTML = "";
    var colors = {};
    for (var i = 0; i < geometries.length; i++) {
        var cid = geometries[i].color_id;
        colors[cid] = (colors[cid] || 0) + 1;
    }
    for (var colorId in colors) {
        if (!colors.hasOwnProperty(colorId)) continue;
        var count = colors[colorId];
        var safeId = colorId.replace("#", "");
        var card = document.createElement("div");
        card.className = "bin-card active fade-in";
        card.id = "bin-" + safeId;
        var colorName = getHumanColorName(colorId);
        card.innerHTML =
            '<div class="bin-header">' +
            '  <div class="color-swatch" style="background:' + colorId + '"></div>' +
            '  <span class="bin-color-id">' + colorName + '</span>' +
            '  <span class="bin-stats">' + count + ' piezas</span>' +
            '</div>' +
            '<div class="progress-bar-container">' +
            '  <div class="progress-bar-fill" id="pb-' + safeId + '"></div>' +
            '</div>' +
            '<div class="metrics-row">' +
            '  <div class="metric">Eficiencia: <span class="value" id="eff-' + safeId + '">—</span></div>' +
            '  <div class="metric">Waterline: <span class="value" id="wl-' + safeId + '">—</span></div>' +
            '</div>';
        progressSection.appendChild(card);
    }
}

function updateBinResult(colorId, binResult) {
    var safeId = colorId.replace("#", "");
    var card = document.getElementById("bin-" + safeId);
    var pb   = document.getElementById("pb-" + safeId);
    var eff  = document.getElementById("eff-" + safeId);
    var wl   = document.getElementById("wl-" + safeId);
    if (!card) return;
    card.className = "bin-card done fade-in";
    if (pb) {
        var pct = Math.min(binResult.efficiency_pct, 100);
        pb.style.width = pct + "%";
        pb.className = "progress-bar-fill" +
            (binResult.efficiency_pct >= 85 ? " success" : binResult.efficiency_pct >= 70 ? "" : " warning");
    }
    if (eff) eff.textContent = binResult.efficiency_pct + "%";
    if (wl)  wl.textContent  = binResult.waterline_mm + "mm";
}

// ═══════════════════════════════════════════════════════════════
// 7. REPORTE
// ═══════════════════════════════════════════════════════════════
function showReport(response) {
    reportCard.classList.remove("hidden");
    var ge = response.postflight.global_efficiency;
    rptEfficiency.textContent = ge + "%";
    rptEfficiency.className   = "value " + (ge >= 85 ? "good" : ge >= 70 ? "" : "bad");
    var sr = response.savings_report;
    rptOptimized.textContent = sr.optimized_roll_length_m + "m";
    rptManual.textContent    = sr.manual_estimate_m + "m";
    rptSaved.textContent     = sr.material_saved_m + "m (" + sr.savings_pct + "%)";
    suggestionsArea.innerHTML = "";
    if (response.postflight.suggestions && response.postflight.suggestions.length > 0) {
        for (var i = 0; i < response.postflight.suggestions.length; i++) {
            var div = document.createElement("div");
            div.className = "suggestion";
            div.innerHTML = '<span class="icon">\u26a0\ufe0f</span> ' + response.postflight.suggestions[i];
            suggestionsArea.appendChild(div);
        }
    }

    // Configurar Visor
    if (response.bins && response.bins.length > 0) {
        previewBinSelect.innerHTML = "";
        for (var b = 0; b < response.bins.length; b++) {
            var opt = document.createElement("option");
            opt.value = b;
            var cName = getHumanColorName(response.bins[b].color_id);
            opt.textContent = cName + " (" + response.bins[b].placed.length + " piezas)";
            previewBinSelect.appendChild(opt);
        }
        drawPreview(response.bins[0]);
    }
}

// ═══════════════════════════════════════════════════════════════
// 7.5 DIBUJAR PREVISUALIZACIÓN EN CANVAS
// ═══════════════════════════════════════════════════════════════
function drawPreview(bin) {
    if (!ctx || !previewCanvas) return;
    
    var cW = document.getElementById("canvasWidth").value || 1200;
    var cH = document.getElementById("canvasHeight").value || 3000;
    
    // Configurar tamaño interno del canvas (resolución)
    previewCanvas.width = previewCanvas.parentElement.clientWidth;
    previewCanvas.height = 200; // altura fija razonable para el panel
    
    // Limpiar canvas
    ctx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
    
    // Calcular escala para encajar la plancha (bin)
    var scaleX = previewCanvas.width / cW;
    var scaleY = previewCanvas.height / cH;
    var scale = Math.min(scaleX, scaleY) * 0.95; // 5% de padding
    
    var offsetX = (previewCanvas.width - (cW * scale)) / 2;
    var offsetY = (previewCanvas.height - (cH * scale)) / 2;
    
    // Dibujar el fondo del bin (la plancha)
    ctx.fillStyle = "rgba(255, 255, 255, 0.05)";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
    ctx.lineWidth = 1;
    ctx.fillRect(offsetX, offsetY, cW * scale, cH * scale);
    ctx.strokeRect(offsetX, offsetY, cW * scale, cH * scale);
    
    // Dibujar piezas
    ctx.fillStyle = bin.color_id || "#638cff";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.8)";
    ctx.lineWidth = 1;
    
    for (var i = 0; i < bin.placed.length; i++) {
        var piece = bin.placed[i];
        if (!piece.points || piece.points.length === 0) continue;
        
        ctx.beginPath();
        for (var p = 0; p < piece.points.length; p++) {
            // Aplicar la rotación y posición recibida del motor
            // piece.points es el contorno base. El backend puede estar devolviendolos ya transformados, 
            // o quizas debamos sumarle la posicion. El motor IMBA* devuelve los puntos originales (original_points) 
            // y la pos/rot. Para simplificar, asumimos que "points" en PlacedPieceResponse son relativos 
            // y tenemos que aplicar la transformacion o bien ya vienen absolutos. 
            // Si el backend envia "points" ya transformados a la plancha, simplemente escalamos:
            var px = piece.points[p][0];
            var py = piece.points[p][1];
            
            // Asumiendo points absolutos devueltos en la respuesta:
            var canvasX = offsetX + (px * scale);
            var canvasY = offsetY + (py * scale); // Si el Y es invertido, ajustar. Asumo origin Top-Left.
            
            if (p === 0) ctx.moveTo(canvasX, canvasY);
            else ctx.lineTo(canvasX, canvasY);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
    }
}

if (previewBinSelect) {
    previewBinSelect.addEventListener("change", function(e) {
        if (lastResult && lastResult.bins) {
            drawPreview(lastResult.bins[parseInt(e.target.value)]);
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// 8. API CALLS
// ═══════════════════════════════════════════════════════════════
function callValidate(payload) {
    log("Ejecutando pre-flight check...");
    return fetch(API_BASE + "/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    }).then(function(r) {
        if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || "HTTP " + r.status); });
        return r.json();
    }).then(function(data) {
        log("Validación: " + data.valid_count + " válidas, " + data.invalid_count + " con error.",
            data.invalid_count > 0 ? "warn" : "success");
        if (data.issues) {
            for (var i = 0; i < data.issues.length; i++) {
                var iss = data.issues[i];
                log("  [" + iss.severity + "] " + iss.message,
                    iss.severity === "error" ? "error" : "warn");
            }
        }
        return data;
    });
}

function callNest(payload) {
    log("Iniciando motor de anidamiento...");
    return fetch(API_BASE + "/nest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    }).then(function(r) {
        if (!r.ok) return r.json().then(function(e) {
            throw new Error((e.detail && e.detail.error) || JSON.stringify(e.detail) || "HTTP " + r.status);
        });
        return r.json();
    });
}

// ═══════════════════════════════════════════════════════════════
// 9. RE-INYECCIÓN
// ═══════════════════════════════════════════════════════════════
function applyResults() {
    if (!lastResult) { log("No hay resultado para aplicar.", "warn"); return; }
    log("Aplicando anidamiento al lienzo...");
    csInterface.evalScript(
        'applyNestingResult(' + JSON.stringify(JSON.stringify(lastResult)) + ')',
        function(result) {
            if (result === "ok") {
                log("\u2705 Anidamiento aplicado correctamente.", "success");
            } else {
                log("Error al aplicar: " + result, "error");
            }
        }
    );
}

// ═══════════════════════════════════════════════════════════════
// 10. EVENT HANDLERS
// ═══════════════════════════════════════════════════════════════
btnValidate.addEventListener("click", function() {
    if (isProcessing) return;
    isProcessing = true;
    btnValidate.disabled = true;
    checkServer().then(function(online) {
        if (!online) { isProcessing = false; btnValidate.disabled = false; return; }
        return extractGeometries().then(function(geos) {
            if (!geos) { isProcessing = false; btnValidate.disabled = false; return; }
            return callValidate(buildPayload(geos, null));
        });
    }).catch(function(e) {
        log("Error: " + e.message, "error");
    }).then(function() {
        isProcessing = false;
        btnValidate.disabled = false;
    });
});

btnNest.addEventListener("click", function() {
    if (isProcessing) return;
    isProcessing = true;
    btnNest.disabled = true;
    reportCard.classList.add("hidden");

    checkServer().then(function(online) {
        if (!online) throw new Error("Servidor no disponible");
        return extractGeometries();
    }).then(function(geos) {
        if (!geos) throw new Error("No hay piezas válidas");
        showColorBins(geos);
        return getDocInfo().then(function(docInfo) {
            var payload = buildPayload(geos, docInfo);
            return callValidate(payload).then(function(validation) {
                if (validation.invalid_count > 0 && validation.valid_count === 0)
                    throw new Error("Todas las piezas son inválidas");
                return callNest(payload);
            });
        });
    }).then(function(result) {
        lastResult = result;
        for (var i = 0; i < result.bins.length; i++)
            updateBinResult(result.bins[i].color_id, result.bins[i]);
        showReport(result);
        log("Anidamiento completado: " + result.status, result.status === "ok" ? "success" : "warn");
    }).catch(function(e) {
        log("Error: " + e.message, "error");
    }).then(function() {
        isProcessing = false;
        btnNest.disabled = false;
    });
});

btnApply.addEventListener("click", function() { applyResults(); });

// ═══════════════════════════════════════════════════════════════
// 11. INIT
// ═══════════════════════════════════════════════════════════════
(function init() {
    log("Inicializando panel Nesting Industrial...");
    
    // Forzar la recarga de host.jsx para saltar la caché de Illustrator
    var extPath = csInterface.getSystemPath(SystemPath.EXTENSION);
    var jsxPath = extPath + "/host.jsx";
    var evalScript = "try { $.evalFile('" + jsxPath.replace(/\\/g, '/') + "'); 'ok'; } catch(e) { 'EXTENDSCRIPT_INIT_ERROR: ' + e.message + ' (linea ' + e.line + ')'; }";
    
    csInterface.evalScript(evalScript, function(res) {
        if (res !== "ok") {
            log("Error cargando host.jsx: " + res, "error");
        } else {
            log("host.jsx cargado correctamente en memoria.", "success");
            
            // Rellenar ancho/alto desde el artboard activo solo si cargó bien
            csInterface.evalScript("getDocumentInfo()", function(result) {
                try {
                    var info = JSON.parse(result);
                    if (info.width_mm)  document.getElementById("canvasWidth").value  = Math.round(info.width_mm);
                    if (info.height_mm) document.getElementById("canvasHeight").value = Math.round(info.height_mm);
                    log("Artboard detectado: " + Math.round(info.width_mm) + " x " + Math.round(info.height_mm) + " mm");
                } catch(e) {
                    try {
                        // Intentar con el MyJSON por si result es un JSON válido
                        var info2 = eval("(" + result + ")");
                        if (info2 && info2.width_mm) {
                            document.getElementById("canvasWidth").value = Math.round(info2.width_mm);
                            document.getElementById("canvasHeight").value = Math.round(info2.height_mm);
                        }
                    } catch(e2) {}
                }
            });
        }
    });

    checkServer();

    // Re-chequear servidor cada 30 segundos
    setInterval(function() { checkServer(); }, 30000);
})();
