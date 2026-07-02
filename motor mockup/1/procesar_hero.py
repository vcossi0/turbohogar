"""Procesa solo la imagen hero_cityscape.png con los 5 PSDs."""
import os, sys, shutil, time, subprocess, win32com.client
from PIL import Image

# ── Config ────────────────────────────────────────────────────
HERO_IMG   = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\designs\Categorias\HERO\hero_city\hero_nebula.png"
OUTPUT_DIR = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\assets\mock"
HERO_PREFIX = "hero2"
SCRIPT_DIR = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\motor mockup\1"
TEMP_DIR   = os.path.join(SCRIPT_DIR, "_temp_hero")
JSX_TIMEOUT = 90

PSD_MAPPING = {
    'comun': r'Horizontal\TC03.psd',
    'h1':    r'Horizontal\Mockup Premium 39 - Editável.psd',
    'h2':    r'Horizontal\TC02.psd',
    'v1':    r'Vertical\TC01.psd',
    'v2':    r'Vertical\TC05.psd',
}

SO_NAMES = ['@design','sua imagem aqui','imagem','imagem aqui 1','imagem aqui 1 copiar','imagem aqui']

# ── Helpers (copiados de v6) ───────────────────────────────────
def fix_path_for_jsx(p): return p.replace('\\','/')

def aspect_fill_and_save(img_path, tw, th, out_path):
    img = Image.open(img_path).convert("RGB")
    iw, ih = img.size
    if (iw>ih) != (tw>th):
        img = img.rotate(-90, expand=True)
        iw, ih = img.size
    scale = max(tw/iw, th/ih)
    nw, nh = round(iw*scale), round(ih*scale)
    img = img.resize((nw,nh), Image.Resampling.LANCZOS)
    l, t = (nw-tw)//2, (nh-th)//2
    img = img.crop((l,t,l+tw,t+th))
    img.save(out_path,"PNG"); img.close()

def connect_ps():
    ps = win32com.client.Dispatch("Photoshop.Application")
    ps.Preferences.RulerUnits = 1
    ps.DisplayDialogs = 3
    return ps

def find_so(layers):
    for i in range(1,layers.Count+1):
        ly = layers.Item(i)
        if ly.LayerType==1:
            try:
                if ly.Kind==17 and ly.Name.lower() in SO_NAMES: return ly
            except: pass
        if ly.LayerType==2:
            r = find_so(ly.Layers)
            if r: return r
    return None

def run_jsx(ps, jsx):
    worker = os.path.join(SCRIPT_DIR,"ps_worker.py")
    try:
        proc = subprocess.Popen([sys.executable,worker],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out,_ = proc.communicate(jsx.encode("utf-8"),timeout=JSX_TIMEOUT)
        return out.decode("utf-8",errors="replace").strip() or "ERROR:empty"
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait()
        os.system("taskkill /F /IM Photoshop.exe >nul 2>&1")
        time.sleep(3); return "TIMEOUT"
    except Exception as e: return f"ERROR:{e}"

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

# ── Main ──────────────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR,   exist_ok=True)

    print("Conectando Photoshop...")
    ps = connect_ps()
    print("OK\n")

    for key, psd_rel in PSD_MAPPING.items():
        psd_path = os.path.join(SCRIPT_DIR, psd_rel)
        if not os.path.exists(psd_path):
            print(f"[SKIP] {psd_rel} no existe"); continue

        out_path = os.path.join(OUTPUT_DIR, f"{HERO_PREFIX}_{key}.png")
        print(f"Procesando {key} -> {os.path.basename(out_path)} ...")

        # Abrir PSD y obtener dims PSB
        try: doc = ps.Open(psd_path)
        except Exception as e: print(f"  Error abriendo PSD: {e}"); continue

        so = find_so(doc.Layers)
        if not so: print("  SO no encontrado"); doc.Close(2); continue
        doc.ActiveLayer = so

        dims = ps.DoJavaScript(JSX_GET_DIMS)
        if dims.startswith("ERROR"): print(f"  Error dims: {dims}"); doc.Close(2); continue
        psb_w, psb_h = [int(x) for x in dims.split("x")]
        print(f"  PSB: {psb_w}×{psb_h}")

        # Preprocesar imagen
        temp = os.path.join(TEMP_DIR, f"temp_{key}.png")
        try: aspect_fill_and_save(HERO_IMG, psb_w, psb_h, temp)
        except Exception as e: print(f"  Error Pillow: {e}"); doc.Close(2); continue

        tj = fix_path_for_jsx(temp)
        oj = fix_path_for_jsx(out_path)

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

        result = run_jsx(ps, jsx)
        try: os.remove(temp)
        except: pass

        if result=="OK":
            print(f"  OK Guardado: {HERO_PREFIX}_{key}.png")
        else:
            print(f"  FALLO: {result}")

        doc.Close(2)

    print("\nListo! Archivos en:", OUTPUT_DIR)
    print(f"Busca: {HERO_PREFIX}_comun.png, {HERO_PREFIX}_h1.png, {HERO_PREFIX}_h2.png, {HERO_PREFIX}_v1.png, {HERO_PREFIX}_v2.png")

if __name__ == "__main__":
    main()
