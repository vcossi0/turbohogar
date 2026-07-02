"""
Servidor local TurboHogar — procesa imágenes del cliente con el motor Photoshop
y devuelve mockups fotorrealistas.

Instalar: pip install flask flask-cors pillow pywin32
Ejecutar: python server.py
"""

import os, sys, uuid, time, subprocess, threading, shutil, tempfile, logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("turbohogar")

# ── Config ────────────────────────────────────────────────────────────────────
BASE      = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar"
SCRIPT_DIR = os.path.join(BASE, "motor mockup", "1")
UPLOADS   = os.path.join(BASE, "assets", "uploads")
RESULTS   = os.path.join(BASE, "assets", "results")
# TEMP_DIR fuera de OneDrive para evitar conflictos de sincronización
TEMP_DIR  = os.path.join(tempfile.gettempdir(), "turbohogar_temp")
JSX_TIMEOUT = 120

os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(RESULTS, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# PSDs disponibles por orientación
PSDS = {
    "vertical":   [("v1", r"Vertical\TC01.psd"), ("v2", r"Vertical\TC05.psd")],
    "horizontal": [("h1", r"Horizontal\Mockup Premium 39 - Editável.psd"), ("h2", r"Horizontal\TC02.psd")],
    "comun":      [("comun", r"Horizontal\TC03.psd")],
}

SO_NAMES = ["@design","sua imagem aqui","imagem","imagem aqui 1","imagem aqui 1 copiar","imagem aqui"]

JSX_GET_DIMS = """
function getDims(){
    try{
        var mainDoc=app.activeDocument,mainName=mainDoc.name;
        var idEdit=stringIDToTypeID("placedLayerEditContents");
        executeAction(idEdit,new ActionDescriptor(),DialogModes.NO);
        var soDoc=app.activeDocument;
        if(soDoc.name===mainName) return "ERROR";
        var w=Math.round(soDoc.width.as("px")),h=Math.round(soDoc.height.as("px"));
        soDoc.close(SaveOptions.DONOTSAVECHANGES);
        app.activeDocument=mainDoc;
        return w+"x"+h;
    }catch(e){return "ERROR:"+e.toString();}
}
getDims();
"""

# ── Helpers ───────────────────────────────────────────────────────────────────
def fix_jsx(p): return p.replace("\\", "/")

def aspect_fill(img_path, tw, th, out_path):
    img = Image.open(img_path).convert("RGB")
    iw, ih = img.size
    if (iw > ih) != (tw > th):
        img = img.rotate(-90, expand=True)
        iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = round(iw * scale), round(ih * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    l, t = (nw - tw) // 2, (nh - th) // 2
    img = img.crop((l, t, l + tw, t + th))
    img.save(out_path, "PNG")
    img.close()

def run_jsx(jsx_code):
    worker = os.path.join(SCRIPT_DIR, "ps_worker.py")
    try:
        proc = subprocess.Popen(
            [sys.executable, worker],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, _ = proc.communicate(jsx_code.encode("utf-8"), timeout=JSX_TIMEOUT)
        return out.decode("utf-8", errors="replace").strip() or "ERROR:empty"
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait()
        os.system("taskkill /F /IM Photoshop.exe >nul 2>&1")
        time.sleep(3)
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR:{e}"

def find_so(layers):
    import win32com.client as wc
    for i in range(1, layers.Count + 1):
        ly = layers.Item(i)
        if ly.LayerType == 1:
            try:
                if ly.Kind == 17 and ly.Name.lower() in SO_NAMES:
                    return ly
            except: pass
        if ly.LayerType == 2:
            r = find_so(ly.Layers)
            if r: return r
    return None

def get_ps():
    import win32com.client as wc
    ps = wc.Dispatch("Photoshop.Application")
    ps.Preferences.RulerUnits = 1
    ps.DisplayDialogs = 3
    return ps

# Photoshop singleton
_ps_lock = threading.Lock()
_ps = None

def ps():
    global _ps
    if _ps is not None:
        try:
            _ = _ps.Version  # verifica si PS sigue vivo
        except:
            _ps = None
    if _ps is None:
        _ps = get_ps()
    return _ps

def process_image(img_path, orient, job_id):
    """
    Procesa img_path con el PSD correspondiente a la orientación.
    Devuelve lista de rutas de PNG generados.
    """
    results = []
    key_list = PSDS.get(orient, PSDS["vertical"])

    with _ps_lock:
        app = ps()
        for key, psd_rel in key_list:
            psd_path = os.path.join(SCRIPT_DIR, psd_rel)
            if not os.path.exists(psd_path):
                log.warning(f"[{key}] PSD no encontrado: {psd_path}")
                continue

            out_path = os.path.join(RESULTS, f"{job_id}_{key}.png")

            # Copia del PSD fuera de OneDrive para evitar sync locks
            temp_psd = os.path.join(TEMP_DIR, f"{job_id}_{key}_template.psd")
            try:
                shutil.copy2(psd_path, temp_psd)
                log.info(f"[{key}] PSD copiado a temp")
            except Exception as e:
                log.error(f"[{key}] Error copiando PSD: {e}")
                continue

            try:
                doc = app.Open(temp_psd)
                log.info(f"[{key}] PSD abierto en Photoshop")
            except Exception as e:
                log.error(f"[{key}] Error abriendo PSD: {e}")
                try: os.remove(temp_psd)
                except: pass
                continue

            so = find_so(doc.Layers)
            if not so:
                log.error(f"[{key}] Smart Object no encontrado")
                doc.Close(2)
                try: os.remove(temp_psd)
                except: pass
                continue

            doc.ActiveLayer = so
            dims = app.DoJavaScript(JSX_GET_DIMS)
            log.info(f"[{key}] Dims SO: {dims}")
            if dims.startswith("ERROR"):
                log.error(f"[{key}] Error obteniendo dims: {dims}")
                doc.Close(2)
                try: os.remove(temp_psd)
                except: pass
                continue

            psb_w, psb_h = [int(x) for x in dims.split("x")]

            temp = os.path.join(TEMP_DIR, f"{job_id}_{key}.png")
            try:
                aspect_fill(img_path, psb_w, psb_h, temp)
            except Exception as e:
                log.error(f"[{key}] Error en aspect_fill: {e}")
                doc.Close(2)
                try: os.remove(temp_psd)
                except: pass
                continue

            tj = fix_jsx(temp)
            oj = fix_jsx(out_path)

            jsx = f"""
            function process(){{
                try{{
                    var mainDocName=app.activeDocument.name;
                    var idEdit=stringIDToTypeID("placedLayerEditContents");
                    executeAction(idEdit,new ActionDescriptor(),DialogModes.NO);
                    var soDocName=app.activeDocument.name;
                    var designDoc=app.open(new File("{tj}"));
                    designDoc.resizeImage(new UnitValue({psb_w},"px"),new UnitValue({psb_h},"px"),null,ResampleMethod.BICUBIC);
                    designDoc.flatten();
                    var soDoc;
                    for(var i=0;i<app.documents.length;i++){{
                        if(app.documents[i].name===soDocName){{soDoc=app.documents[i];break;}}
                    }}
                    designDoc.artLayers[0].duplicate(soDoc,ElementPlacement.PLACEATBEGINNING);
                    designDoc.close(SaveOptions.DONOTSAVECHANGES);
                    app.activeDocument=soDoc;
                    soDoc.flatten();
                    soDoc.close(SaveOptions.SAVECHANGES);
                    for(var j=0;j<app.documents.length;j++){{
                        if(app.documents[j].name===mainDocName){{app.activeDocument=app.documents[j];break;}}
                    }}
                    var savedState=app.activeDocument.activeHistoryState;
                    app.activeDocument.resizeImage(new UnitValue(1200,"px"),new UnitValue(1200,"px"),300,ResampleMethod.BICUBIC);
                    var pngOpts=new PNGSaveOptions();pngOpts.compression=6;
                    app.activeDocument.saveAs(new File("{oj}"),pngOpts,true,Extension.LOWERCASE);
                    app.activeDocument.activeHistoryState=savedState;
                    return "OK";
                }}catch(e){{return "ERROR:"+e.toString();}}
            }}
            process();
            """

            result = run_jsx(jsx)
            log.info(f"[{key}] Resultado JSX: {result}")

            try: os.remove(temp)
            except: pass

            doc.Close(2)
            try: os.remove(temp_psd)
            except: pass

            if result == "OK" and os.path.exists(out_path):
                results.append({
                    "key": key,
                    "url": f"/resultado/{job_id}_{key}.png"
                })

    return results

# ── Flask App ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "msg": "TurboHogar motor activo"})

@app.route("/procesar-upload", methods=["POST"])
def procesar_upload():
    if "imagen" not in request.files:
        return jsonify({"error": "No se recibio imagen"}), 400

    archivo = request.files["imagen"]
    orient  = request.form.get("orient", "vertical")  # "vertical" | "horizontal"

    if not archivo.filename:
        return jsonify({"error": "Archivo vacio"}), 400

    # Guardar upload
    job_id   = uuid.uuid4().hex[:12]
    ext      = os.path.splitext(archivo.filename)[1].lower() or ".jpg"
    img_path = os.path.join(UPLOADS, f"{job_id}{ext}")
    archivo.save(img_path)

    # Validar imagen
    try:
        with Image.open(img_path) as img:
            w, h = img.size
            if w < 400 or h < 400:
                os.remove(img_path)
                return jsonify({"error": "Imagen demasiado pequena (minimo 400px)"}), 400
    except Exception as e:
        return jsonify({"error": f"Imagen invalida: {e}"}), 400

    # Procesar con el motor
    try:
        mockups = process_image(img_path, orient, job_id)
    except Exception as e:
        return jsonify({"error": f"Error en el motor: {e}"}), 500

    if not mockups:
        return jsonify({"error": "No se pudo generar el mockup"}), 500

    return jsonify({
        "ok":      True,
        "job_id":  job_id,
        "orient":  orient,
        "mockups": mockups
    })

@app.route("/resultado/<filename>", methods=["GET"])
def resultado(filename):
    path = os.path.join(RESULTS, filename)
    if not os.path.exists(path):
        return "No encontrado", 404
    return send_file(path, mimetype="image/png")

if __name__ == "__main__":
    print("=" * 55)
    print("  TurboHogar Motor Server")
    print("  http://localhost:5000")
    print("  Photoshop debe estar abierto")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=False)
