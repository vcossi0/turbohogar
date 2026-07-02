/**
 * host.jsx — ExtendScript para Adobe Illustrator
 * Corre dentro del motor ES3/ES5 de Illustrator.
 * Comunicacion via CSInterface.evalScript().
 */

var PT_TO_MM = 0.352778; // 1 punto tipografico = 0.352778 mm

// ───────────────────────────────────────────────
// 0. POLYFILL JSON
// ───────────────────────────────────────────────
var MyJSON = {};
MyJSON.stringify = function (value) {
    var t = typeof value;
    if (t !== "object" || value === null) {
        if (t === "string") return '"' + value.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
        return String(value);
    } else {
        var n, v, json = [], arr = (value && value.constructor === Array);
        if (arr) {
            for (var i = 0; i < value.length; i++) {
                v = value[i];
                t = typeof v;
                if (t === "string") v = '"' + v.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
                else if (t === "object" && v !== null) v = MyJSON.stringify(v);
                json.push(String(v));
            }
        } else {
            for (n in value) {
                if (value.hasOwnProperty(n)) {
                    v = value[n];
                    t = typeof v;
                    if (t === "string") v = '"' + v.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
                    else if (t === "object" && v !== null) v = MyJSON.stringify(v);
                    json.push('"' + n + '":' + String(v));
                }
            }
        }
        return (arr ? "[" : "{") + String(json) + (arr ? "]" : "}");
    }
};

MyJSON.parse = function (str) {
    try {
        return eval("(" + str + ")");
    } catch (e) {
        return {};
    }
};
// ───────────────────────────────────────────────
// 1. INFO DEL DOCUMENTO
// ───────────────────────────────────────────────
function getDocumentInfo() {
    try {
        var doc = app.activeDocument;
        var ab  = doc.artboards[0].artboardRect; // [left, top, right, bottom] en pts
        return MyJSON.stringify({
            width_mm:  Math.abs(ab[2] - ab[0]) * PT_TO_MM,
            height_mm: Math.abs(ab[1] - ab[3]) * PT_TO_MM
        });
    } catch (e) { return MyJSON.stringify({ error: e.message }); }
}

// ───────────────────────────────────────────────
// 2. EXTRACCION DE GEOMETRIA
// ───────────────────────────────────────────────
function getPathsFromItems(items, pathsArray) {
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        if (item.typename === "GroupItem") {
            pathsArray.push(item); // Preservar grupo como una sola pieza
        } else if (item.typename === "CompoundPathItem") {
            pathsArray.push(item);
        } else if (item.typename === "PathItem") {
            pathsArray.push(item);
        }
    }
}

function extractGeometries() {
    try {
        var doc       = app.activeDocument;
        var selection = doc.selection;
        if (!selection || selection.length === 0)
            return MyJSON.stringify({ error: "NO_SELECTION" });

        var flatSelection = [];
        getPathsFromItems(selection, flatSelection);

        var geometries = [];
        var id = 1;
        for (var i = 0; i < flatSelection.length; i++) {
            var geo = extractItem(flatSelection[i], id);
            if (geo) { geometries.push(geo); id++; }
        }
        if (geometries.length === 0)
            return MyJSON.stringify({ error: "NO_PATHS" });

        return MyJSON.stringify({ geometries: geometries });
    } catch (e) { return MyJSON.stringify({ error: e.message }); }
}

function extractItem(item, id) {
    var isGroup = (item.typename === "GroupItem");

    if (isGroup) {
        var bounds = item.geometricBounds; // [left, top, right, bottom]
        if (!bounds || bounds.length < 4) return null;
        
        item.note = "NEST_ID_" + id;
        
        var left = bounds[0] * PT_TO_MM;
        var top = -(bounds[1] * PT_TO_MM);
        var right = bounds[2] * PT_TO_MM;
        var bottom = -(bounds[3] * PT_TO_MM);
        
        var points = [
            [left, top],
            [right, top],
            [right, bottom],
            [left, bottom]
        ];
        var cx = (left + right) / 2;
        var cy = (top + bottom) / 2;
        
        var groupColor = getGroupColor(item) || "#888888";
        
        return {
            id: id, color_id: groupColor,
            points: points, is_closed: true,
            path_points: null, original_center: [cx, cy]
        };
    }

    var pi = item;
    if (item.typename === "CompoundPathItem") {
        if (!item.pathItems || item.pathItems.length === 0) return null;
        pi = item.pathItems[0];
    }
    if (pi.typename !== "PathItem") return null;
    if (!pi.pathPoints || pi.pathPoints.length < 3) return null;

    // Marcar con ID persistente
    item.note = "NEST_ID_" + id;

    var points = [], pathPoints = [];
    for (var j = 0; j < pi.pathPoints.length; j++) {
        var pp = pi.pathPoints[j];
        var ax = pp.anchor[0] * PT_TO_MM;
        var ay = -(pp.anchor[1] * PT_TO_MM); // inversion eje Y
        points.push([ax, ay]);
        pathPoints.push({
            anchor:         [ax, ay],
            leftDirection:  [pp.leftDirection[0]  * PT_TO_MM, -(pp.leftDirection[1]  * PT_TO_MM)],
            rightDirection: [pp.rightDirection[0] * PT_TO_MM, -(pp.rightDirection[1] * PT_TO_MM)]
        });
    }

    var cx = 0, cy = 0;
    for (var k = 0; k < points.length; k++) { cx += points[k][0]; cy += points[k][1]; }
    cx /= points.length; cy /= points.length;

    return {
        id: id, color_id: getColor(pi),
        points: points, is_closed: (pi.closed !== false),
        path_points: pathPoints, original_center: [cx, cy]
    };
}

function getGroupColor(groupItem) {
    if (!groupItem.pageItems) return null;
    for (var i = 0; i < groupItem.pageItems.length; i++) {
        var item = groupItem.pageItems[i];
        if (item.typename === "PathItem") {
            try {
                if (item.filled) return getColor(item);
            } catch(e) {}
        } else if (item.typename === "CompoundPathItem") {
            try {
                if (item.pathItems && item.pathItems.length > 0 && item.pathItems[0].filled) {
                    return getColor(item.pathItems[0]);
                }
            } catch(e) {}
        } else if (item.typename === "GroupItem") {
            var c = getGroupColor(item);
            if (c) return c;
        }
    }
    return null;
}

function getColor(item) {
    try {
        var f = item.fillColor;
        if (f.typename === "RGBColor")
            return "#" + h2(f.red) + h2(f.green) + h2(f.blue);
        if (f.typename === "CMYKColor") {
            var c=f.cyan/100, m=f.magenta/100, y=f.yellow/100, k=f.black/100;
            return "#" + h2(255*(1-c)*(1-k)) + h2(255*(1-m)*(1-k)) + h2(255*(1-y)*(1-k));
        }
        if (f.typename === "SpotColor")
            return getColor({ fillColor: f.spot.color });
        if (f.typename === "GrayColor") {
            var v = Math.round(255*(1-f.gray/100));
            return "#" + h2(v)+h2(v)+h2(v);
        }
    } catch(e) {}
    return "#000000";
}

function h2(n) {
    var s = Math.max(0,Math.min(255,Math.round(n))).toString(16);
    return s.length===1 ? "0"+s : s;
}

function getHumanColorName(hex) {
    var colors = {
        "#000000": "Negro", "#ffffff": "Blanco", "#ff0000": "Rojo",
        "#00ff00": "Verde", "#0000ff": "Azul", "#ffff00": "Amarillo",
        "#00ffff": "Cian", "#ff00ff": "Magenta", "#888888": "Gris",
        "#ffa500": "Naranja", "#800080": "Purpura", "#a52a2a": "Marron",
        "#ffc0cb": "Rosa", "#008000": "Verde Oscuro", "#000080": "Azul Marino",
        "#ffd700": "Dorado", "#c0c0c0": "Plateado", "#808080": "Gris Medio"
    };
    hex = hex.toLowerCase();
    if (colors[hex]) return colors[hex];
    var r = parseInt(hex.substring(1, 3), 16) || 0;
    var g = parseInt(hex.substring(3, 5), 16) || 0;
    var b = parseInt(hex.substring(5, 7), 16) || 0;
    var minDistance = Infinity;
    var closestName = hex;
    for (var k in colors) {
        var kr = parseInt(k.substring(1, 3), 16);
        var kg = parseInt(k.substring(3, 5), 16);
        var kb = parseInt(k.substring(5, 7), 16);
        var dist = Math.sqrt(Math.pow(r - kr, 2) + Math.pow(g - kg, 2) + Math.pow(b - kb, 2));
        if (dist < minDistance) {
            minDistance = dist;
            closestName = colors[k];
        }
    }
    return closestName;
}

// ───────────────────────────────────────────────
// 3. RE-INYECCION DE RESULTADOS
// ───────────────────────────────────────────────
function applyNestingResult(jsonStr) {
    try {
        var result = MyJSON.parse(jsonStr);
        var doc    = app.activeDocument;
        var ab     = doc.artboards[0].artboardRect;
        var origX  = ab[0]; // left en pts
        var origY  = ab[1]; // top en pts
        var abW    = Math.abs(ab[2] - ab[0]);
        var abH    = Math.abs(ab[3] - ab[1]);
        var gap    = 50; // separacion de 50 pts entre planchas

        var now = new Date();
        var ts  = now.getFullYear() + p2(now.getMonth()+1) + p2(now.getDate()) +
                  "_" + p2(now.getHours()) + p2(now.getMinutes());
        var master = doc.layers.add();
        master.name = "ANIDAMIENTO_" + ts;

        for (var b = 0; b < result.bins.length; b++) {
            var bin = result.bins[b];
            var sub = master.layers.add();
            var colorName = getHumanColorName(bin.color_id);
            sub.name = "CORTE_" + colorName;

            // Desplazamiento horizontal para separar colores
            var currentOrigX = origX + (b * (abW + gap));
            // NOTA: Se eliminó la creación forzosa de Artboards para no ensuciar el documento.

            for (var p = 0; p < bin.placed.length; p++) {
                var piece = bin.placed[p];
                var item  = findById(doc, piece.piece_id);
                if (!item) continue;

                item.move(sub, ElementPlacement.PLACEATEND);

                if (piece.rotation !== 0)
                    item.rotate(piece.rotation, true, true, true, true, Transformation.CENTER);

                var newX = currentOrigX + (piece.position[0] / PT_TO_MM);
                var newY = origY - (piece.position[1] / PT_TO_MM);
                var bb   = item.geometricBounds; // [left, top, right, bottom]
                item.translate(newX - bb[0], newY - bb[1]);
            }
        }
        return "ok";
    } catch (e) { return "error: " + e.message; }
}

function findById(doc, pieceId) {
    var note = "NEST_ID_" + pieceId;
    var i;
    for (i = 0; i < doc.pathItems.length; i++)
        if (doc.pathItems[i].note === note) return doc.pathItems[i];
    for (i = 0; i < doc.compoundPathItems.length; i++)
        if (doc.compoundPathItems[i].note === note) return doc.compoundPathItems[i];
    for (i = 0; i < doc.groupItems.length; i++)
        if (doc.groupItems[i].note === note) return doc.groupItems[i];
    return null;
}

function clearNestIds() {
    try {
        var doc = app.activeDocument;
        var i;
        for (i = 0; i < doc.pathItems.length; i++) {
            if (doc.pathItems[i].note && doc.pathItems[i].note.indexOf("NEST_ID_") === 0)
                doc.pathItems[i].note = "";
        }
        for (i = 0; i < doc.compoundPathItems.length; i++) {
            if (doc.compoundPathItems[i].note && doc.compoundPathItems[i].note.indexOf("NEST_ID_") === 0)
                doc.compoundPathItems[i].note = "";
        }
        for (i = 0; i < doc.groupItems.length; i++) {
            if (doc.groupItems[i].note && doc.groupItems[i].note.indexOf("NEST_ID_") === 0)
                doc.groupItems[i].note = "";
        }
        return "ok";
    } catch (e) { return "error: " + e.message; }
}

function p2(n) { return n < 10 ? "0"+n : ""+n; }
