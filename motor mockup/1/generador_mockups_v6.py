import os
import sys
import time
import subprocess
import win32com.client
from PIL import Image

# =========================================================
# CONFIGURACION GENERAL
# =========================================================
MODO_PRUEBA = False  # Cambiar a False para las 2,130 imagenes
BATCH_SIZE  = 50     # Reiniciar Photoshop cada N imagenes para liberar RAM
JSX_TIMEOUT = 90     # Segundos antes de considerar Photoshop colgado

BASE_DIR   = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\designs\Categorias"
OUTPUT_DIR = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\processed"
TEMP_DIR   = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\motor mockup\1\_temp"

PSD_MAPPING = {
    'comun': r'Horizontal\TC03.psd',
    'h1':    r'Horizontal\Mockup Premium 39 - Editável.psd',
    'h2':    r'Horizontal\TC02.psd',
    'v1':    r'Vertical\TC01.psd',
    'v2':    r'Vertical\TC05.psd'
}

SO_NAMES = [
    '@design', 'sua imagem aqui', 'imagem',
    'imagem aqui 1', 'imagem aqui 1 copiar', 'imagem aqui'
]

SCRIPT_DIR = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\motor mockup\1"

JSX_GET_DIMS = """
function getDims() {
    try {
        var mainDoc = app.activeDocument;
        var mainName = mainDoc.name;
        var idEdit = stringIDToTypeID("placedLayerEditContents");
        executeAction(idEdit, new ActionDescriptor(), DialogModes.NO);
        var soDoc = app.activeDocument;
        if (soDoc.name === mainName) return "ERROR";
        var w = Math.round(soDoc.width.as("px"));
        var h = Math.round(soDoc.height.as("px"));
        soDoc.close(SaveOptions.DONOTSAVECHANGES);
        app.activeDocument = mainDoc;
        return w + "x" + h;
    } catch(e) { return "ERROR:" + e.toString(); }
}
getDims();
"""

# =========================================================
# HELPERS
# =========================================================

def fix_path_for_jsx(p):
    return p.replace('\\', '/')

def aspect_fill_and_save(img_path, target_w, target_h, out_path):
    img = Image.open(img_path).convert("RGB")
    img_w, img_h = img.size

    source_is_landscape = img_w > img_h
    target_is_landscape = target_w > target_h

    if source_is_landscape != target_is_landscape:
        img = img.rotate(-90, expand=True)
        img_w, img_h = img.size

    scale = max(target_w / img_w, target_h / img_h)
    new_w = round(img_w * scale)
    new_h = round(img_h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))
    img.save(out_path, "PNG")
    img.close()

def run_jsx_with_timeout(jsx_code):
    """Ejecuta JSX en subprocess separado con timeout nativo de Python."""
    worker = os.path.join(SCRIPT_DIR, "ps_worker.py")
    try:
        proc = subprocess.Popen(
            [sys.executable, worker],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, _ = proc.communicate(jsx_code.encode("utf-8"), timeout=JSX_TIMEOUT)
        return stdout.decode("utf-8", errors="replace").strip() or "ERROR:empty"
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        os.system("taskkill /F /IM Photoshop.exe >nul 2>&1")
        time.sleep(3)
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR:{e}"

def connect_photoshop():
    """Conecta con Photoshop y configura para batch sin dialogos. Reintenta si falla."""
    for attempt in range(5):
        try:
            ps = win32com.client.Dispatch("Photoshop.Application")
            ps.Preferences.RulerUnits = 1
            ps.DisplayDialogs = 3
            ps.DoJavaScript("app.preferences.numberOfHistoryStates = 5;")
            return ps
        except Exception as e:
            print(f"  [PS] Intento {attempt+1}/5 fallido: {e}")
            time.sleep(8)
    raise RuntimeError("No se pudo conectar con Photoshop tras 5 intentos.")

def kill_all_photoshop():
    """Mata todas las instancias de Photoshop via WMI (mas confiable que taskkill)."""
    try:
        import win32com.client as wc
        wmi = wc.GetObject("winmgmts:")
        procs = wmi.ExecQuery("SELECT * FROM Win32_Process WHERE Name='Photoshop.exe'")
        for p in procs:
            p.Terminate()
    except Exception:
        os.system("taskkill /F /IM Photoshop.exe >nul 2>&1")
    time.sleep(4)

def restart_photoshop(ps):
    """Cierra Photoshop completamente y lo reabre para liberar RAM."""
    print("\n  [REFRESH] Reiniciando Photoshop para liberar RAM...")
    try:
        ps.Quit()
    except Exception:
        pass
    kill_all_photoshop()
    ps = connect_photoshop()
    print("  [REFRESH] OK — Photoshop reiniciado\n")
    return ps

def find_smart_object(layers):
    for i in range(1, layers.Count + 1):
        layer = layers.Item(i)
        if layer.LayerType == 1:
            try:
                if layer.Kind == 17 and layer.Name.lower() in SO_NAMES:
                    return layer
            except Exception:
                pass
        if layer.LayerType == 2:
            res = find_smart_object(layer.Layers)
            if res:
                return res
    return None

def setup_psd(ps, psd_path):
    """Abre el PSD, localiza el Smart Object y lee las dimensiones del PSB."""
    try:
        doc = ps.Open(psd_path)
    except Exception as e:
        print(f"  [ERROR] No se pudo abrir PSD: {e}")
        return None, None, None, None

    target_layer = find_smart_object(doc.Layers)
    if not target_layer:
        print("  [ERROR] No se encontro capa Smart Object.")
        doc.Close(2)
        return None, None, None, None

    doc.ActiveLayer = target_layer

    dims_result = ps.DoJavaScript(JSX_GET_DIMS)
    if dims_result.startswith("ERROR"):
        print(f"  [ERROR] No se pudo leer PSB: {dims_result}")
        doc.Close(2)
        return None, None, None, None

    psb_w, psb_h = [int(x) for x in dims_result.split("x")]
    print(f"  Capa: '{target_layer.Name}' | PSB: {psb_w}x{psb_h}px")
    return doc, target_layer, psb_w, psb_h

# =========================================================
# MAIN
# =========================================================

def main():
    print("=" * 60)
    print("  MOCKUP AUTOMATOR v6 - PHOTOSHOP NATIVO")
    print("=" * 60)
    if MODO_PRUEBA:
        print("[MODO PRUEBA] 1 horizontal + 1 vertical = 6 resultados.")
    print(f"  Batch size: reiniciar PS cada {BATCH_SIZE} imagenes")
    print("-" * 60)

    # Crear carpeta temporal limpia
    import shutil
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    # Clasificar imagenes
    print(f"\nAnalizando imagenes en: {BASE_DIR}")
    images_h, images_v = [], []

    if not os.path.exists(BASE_DIR):
        print(f"CRITICO: No existe la ruta: {BASE_DIR}")
        return

    for root, dirs, files in os.walk(BASE_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                img_path = os.path.join(root, file)
                try:
                    img = Image.open(img_path)
                    w, h = img.width, img.height
                    img.close()
                    (images_h if w > h else images_v).append(img_path)
                except Exception:
                    pass

    if MODO_PRUEBA:
        images_h = images_h[:1]
        images_v = images_v[:1]

    print(f"  Horizontales: {len(images_h)} | Verticales: {len(images_v)}")

    # Conectar con Photoshop
    print("\nConectando con Adobe Photoshop...")
    try:
        psApp = connect_photoshop()
    except Exception as e:
        print(f"CRITICO: No se pudo conectar con Photoshop. Error: {e}")
        return

    images_since_restart = 0
    total_ok = 0
    total_skip = 0
    total_fail = 0

    # Procesar cada plantilla PSD
    for key, psd_rel_path in PSD_MAPPING.items():
        psd_path = os.path.join(SCRIPT_DIR, psd_rel_path)

        if not os.path.exists(psd_path):
            print(f"\n[SKIP] Plantilla no encontrada: {psd_rel_path}")
            continue

        if key == 'comun':
            imgs_to_process = images_h + images_v
        elif key in ['h1', 'h2']:
            imgs_to_process = images_h
        elif key in ['v1', 'v2']:
            imgs_to_process = images_v
        else:
            imgs_to_process = []

        if not imgs_to_process:
            continue

        print(f"\n{'='*60}")
        print(f"  PSD: {psd_rel_path}  ({len(imgs_to_process)} imagenes)")
        print(f"{'='*60}")

        doc, target_layer, psb_w, psb_h = setup_psd(psApp, psd_path)
        if doc is None:
            continue

        for img_path in imgs_to_process:
            rel_path    = os.path.relpath(os.path.dirname(img_path), BASE_DIR)
            out_folder  = os.path.join(OUTPUT_DIR, rel_path) if rel_path != "." else OUTPUT_DIR
            os.makedirs(out_folder, exist_ok=True)

            nombre_base = os.path.splitext(os.path.basename(img_path))[0]
            out_path    = os.path.join(out_folder, f"{nombre_base}_{key}.png")

            # Skip si ya existe
            if os.path.exists(out_path):
                print(f"  -> {os.path.basename(img_path)} ... SKIP")
                total_skip += 1
                continue

            print(f"  -> {os.path.basename(img_path)} ... ", end="", flush=True)

            # PASO A: Preprocesar con Pillow
            temp_path = os.path.join(TEMP_DIR, f"temp_{key}_{nombre_base}.png")
            try:
                aspect_fill_and_save(img_path, psb_w, psb_h, temp_path)
            except Exception as e:
                print(f"FALLO (Pillow) -> {e}")
                total_fail += 1
                continue

            temp_jsx = fix_path_for_jsx(temp_path)
            out_jsx  = fix_path_for_jsx(out_path)

            # PASO B: Photoshop — abrir PSB, duplicar capa (sin clipboard), exportar PNG
            jsx_code = f"""
            function process() {{
                try {{
                    var mainDocName = app.activeDocument.name;

                    // Abrir PSB interno
                    var idEdit = stringIDToTypeID("placedLayerEditContents");
                    executeAction(idEdit, new ActionDescriptor(), DialogModes.NO);
                    var soDocName = app.activeDocument.name;

                    // Abrir imagen de diseno y ajustar dimensiones
                    var designDoc = app.open(new File("{temp_jsx}"));
                    designDoc.resizeImage(
                        new UnitValue({psb_w}, "px"),
                        new UnitValue({psb_h}, "px"),
                        null, ResampleMethod.BICUBIC
                    );
                    designDoc.flatten();

                    // Duplicar la capa directamente al PSB (sin clipboard)
                    var soDoc;
                    for (var i = 0; i < app.documents.length; i++) {{
                        if (app.documents[i].name === soDocName) {{
                            soDoc = app.documents[i]; break;
                        }}
                    }}
                    designDoc.artLayers[0].duplicate(soDoc, ElementPlacement.PLACEATBEGINNING);
                    designDoc.close(SaveOptions.DONOTSAVECHANGES);

                    // Aplanar PSB y guardar
                    app.activeDocument = soDoc;
                    soDoc.flatten();
                    soDoc.close(SaveOptions.SAVECHANGES);

                    // Exportar documento principal como PNG
                    for (var j = 0; j < app.documents.length; j++) {{
                        if (app.documents[j].name === mainDocName) {{
                            app.activeDocument = app.documents[j]; break;
                        }}
                    }}
                    var savedState = app.activeDocument.activeHistoryState;
                    app.activeDocument.resizeImage(new UnitValue(1200, "px"), new UnitValue(1200, "px"), 300, ResampleMethod.BICUBIC);
                    var pngOpts = new PNGSaveOptions();
                    pngOpts.compression = 6;
                    app.activeDocument.saveAs(new File("{out_jsx}"), pngOpts, true, Extension.LOWERCASE);
                    app.activeDocument.activeHistoryState = savedState;
                    return "OK";
                }} catch(e) {{ return "ERROR:" + e.toString(); }}
            }}
            process();
            """

            result = run_jsx_with_timeout(jsx_code)

            # Borrar temp inmediatamente
            try:
                os.remove(temp_path)
            except Exception:
                pass

            if result == "TIMEOUT":
                print(f"TIMEOUT — reiniciando PS y saltando imagen")
                total_fail += 1
                try:
                    doc.Close(2)
                except Exception:
                    pass
                psApp = restart_photoshop(psApp)
                images_since_restart = 0
                doc, target_layer, psb_w, psb_h = setup_psd(psApp, psd_path)
                if doc is None:
                    print(f"  [ERROR] No se pudo reabrir PSD tras timeout.")
                    break
            elif result == "OK":
                print("OK")
                total_ok += 1
                images_since_restart += 1

                # Purgar cache de PS tras cada imagen
                try:
                    psApp.DoJavaScript("app.purge(2);")
                except Exception:
                    pass

                # Reiniciar PS cada BATCH_SIZE imagenes
                if images_since_restart >= BATCH_SIZE:
                    doc.Close(2)
                    psApp = restart_photoshop(psApp)
                    images_since_restart = 0
                    doc, target_layer, psb_w, psb_h = setup_psd(psApp, psd_path)
                    if doc is None:
                        print(f"  [ERROR] No se pudo reabrir PSD tras restart.")
                        break
            else:
                print(f"FALLO (PS) -> {result}")
                total_fail += 1

        doc.Close(2)

    print(f"\n{'='*60}")
    print(f"  PROCESO COMPLETADO")
    print(f"  OK: {total_ok} | Skip: {total_skip} | Fallos: {total_fail}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
