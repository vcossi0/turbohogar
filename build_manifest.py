# -*- coding: utf-8 -*-
r"""
build_manifest.py — TurboHogar

Recorre ordenado\{CATEGORIA}\{SUBCATEGORIA}\{nombre_diseno}\, copia los assets
a assets\mock\ con nombres limpios, genera designs.json e inyecta los datos
inline en turbohogar.html.
"""

import os
import re
import json
import shutil
import unicodedata

# ---------------------------------------------------------------------------
# Rutas (siempre como variables, nunca concatenacion manual de strings)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ORDENADO_DIR = os.path.join(PROJECT_ROOT, "ordenado")
ASSETS_MOCK_DIR = os.path.join(PROJECT_ROOT, "assets", "mock")
DESIGNS_JSON = os.path.join(PROJECT_ROOT, "designs.json")
HTML_FILE = os.path.join(PROJECT_ROOT, "turbohogar.html")

PRICE = 24990


def clean_id(name):
    # Quitar acentos
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    # Lowercase, reemplazar espacios y # por guion bajo, quitar no alfanumericos
    name = name.lower().strip()
    name = re.sub(r'[#\s]+', '_', name)
    name = re.sub(r'[^\w]', '', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name


def copy_if_missing(src, dst, stats):
    """Copia src -> dst solo si dst no existe. Actualiza contadores."""
    if os.path.exists(dst):
        stats['skipped'] += 1
        return
    shutil.copy2(src, dst)
    stats['copied'] += 1


def main():
    # 1. Crear carpeta assets\mock\
    os.makedirs(ASSETS_MOCK_DIR, exist_ok=True)

    designs = []
    stats = {'copied': 0, 'skipped': 0}
    vertical_count = 0
    horizontal_count = 0
    warnings = []
    seen_ids = {}
    # Contador de diseños por personaje (cat+sub) para numerar duplicados
    seen_display_names = {}  # (cat, sub) -> count

    # Recorrer ordenado\{CAT}\{SUB}\{DISENO}\
    for cat in sorted(os.listdir(ORDENADO_DIR)):
        cat_dir = os.path.join(ORDENADO_DIR, cat)
        if not os.path.isdir(cat_dir):
            continue
        for sub in sorted(os.listdir(cat_dir)):
            sub_dir = os.path.join(cat_dir, sub)
            if not os.path.isdir(sub_dir):
                continue
            for design in sorted(os.listdir(sub_dir)):
                design_dir = os.path.join(sub_dir, design)
                if not os.path.isdir(design_dir):
                    continue

                name = design  # nombre original del diseno (carpeta)

                # Rutas de los archivos esperados dentro de la carpeta del diseno
                comun_src = os.path.join(design_dir, name + "_comun.png")
                v1_src = os.path.join(design_dir, name + "_v1.png")
                v2_src = os.path.join(design_dir, name + "_v2.png")
                h1_src = os.path.join(design_dir, name + "_h1.png")
                h2_src = os.path.join(design_dir, name + "_h2.png")

                # Arte original: .jpg o .jpeg
                art_src = os.path.join(design_dir, name + ".jpg")
                art_ext = "jpg"
                if not os.path.exists(art_src):
                    jpeg_candidate = os.path.join(design_dir, name + ".jpeg")
                    if os.path.exists(jpeg_candidate):
                        art_src = jpeg_candidate
                        art_ext = "jpeg"

                # Validacion: debe existir _comun.png
                if not os.path.exists(comun_src):
                    warnings.append("[WARN] Sin _comun.png, se salta: %s" % design_dir)
                    continue

                # Detectar orientacion (vertical tiene prioridad)
                if os.path.exists(v1_src):
                    orient = "vertical"
                    a_src, b_src = v1_src, v2_src
                elif os.path.exists(h1_src):
                    orient = "horizontal"
                    a_src, b_src = h1_src, h2_src
                else:
                    warnings.append("[WARN] Sin variantes _v1/_h1, se salta: %s" % design_dir)
                    continue

                # ID limpio (asegurar unicidad)
                base_id = clean_id(name)
                if not base_id:
                    base_id = "design"
                uid = base_id
                if uid in seen_ids:
                    seen_ids[base_id] += 1
                    uid = "%s_%d" % (base_id, seen_ids[base_id])
                    warnings.append("[WARN] ID duplicado '%s' -> renombrado a '%s'" % (base_id, uid))
                else:
                    seen_ids[base_id] = 0

                # Rutas destino
                comun_dst = os.path.join(ASSETS_MOCK_DIR, uid + "_comun.png")
                a_dst = os.path.join(ASSETS_MOCK_DIR, uid + "_a.png")
                b_dst = os.path.join(ASSETS_MOCK_DIR, uid + "_b.png")
                art_dst = os.path.join(ASSETS_MOCK_DIR, uid + "_art." + art_ext)

                # Copiar (skip si ya existen)
                copy_if_missing(comun_src, comun_dst, stats)
                if os.path.exists(a_src):
                    copy_if_missing(a_src, a_dst, stats)
                else:
                    warnings.append("[WARN] Falta variante A para: %s" % design_dir)
                if os.path.exists(b_src):
                    copy_if_missing(b_src, b_dst, stats)
                else:
                    warnings.append("[WARN] Falta variante B para: %s" % design_dir)
                if os.path.exists(art_src):
                    copy_if_missing(art_src, art_dst, stats)
                else:
                    warnings.append("[WARN] Falta arte original para: %s" % design_dir)

                # Nombre de display: usar sub (personaje) + número si hay duplicados
                name_key = (cat, sub)
                if name_key not in seen_display_names:
                    seen_display_names[name_key] = 0
                    display_name = sub  # "Iron Man", "Batman", "Aquaman"
                else:
                    seen_display_names[name_key] += 1
                    display_name = "%s %d" % (sub, seen_display_names[name_key] + 1)

                # Rutas web (forward slashes para el HTML/JSON)
                designs.append({
                    "id": uid,
                    "name": display_name,
                    "cat": cat,
                    "sub": sub,
                    "orient": orient,
                    "mock": {
                        "comun": "assets/mock/%s_comun.png" % uid,
                        "a": "assets/mock/%s_a.png" % uid,
                        "b": "assets/mock/%s_b.png" % uid,
                    },
                    "art": "assets/mock/%s_art.%s" % (uid, art_ext),
                    "price": PRICE,
                })

                if orient == "vertical":
                    vertical_count += 1
                else:
                    horizontal_count += 1

    # 4. Guardar designs.json
    with open(DESIGNS_JSON, "w", encoding="utf-8") as f:
        json.dump(designs, f, ensure_ascii=False, indent=2)

    # 5. Inyectar inline en turbohogar.html
    inject_into_html(designs)

    # 6. Resumen
    print("")
    print("=" * 60)
    print("RESUMEN build_manifest.py")
    print("=" * 60)
    print("Total disenos procesados : %d" % len(designs))
    print("  Verticales             : %d" % vertical_count)
    print("  Horizontales           : %d" % horizontal_count)
    print("Assets copiados          : %d" % stats['copied'])
    print("Assets skipped (existian): %d" % stats['skipped'])
    print("designs.json             : %s" % DESIGNS_JSON)
    print("assets\\mock\\            : %s" % ASSETS_MOCK_DIR)
    if warnings:
        print("-" * 60)
        print("WARNINGS (%d):" % len(warnings))
        for w in warnings:
            print("  " + w)
    print("=" * 60)


def inject_into_html(designs):
    if not os.path.exists(HTML_FILE):
        print("[WARN] No se encontro turbohogar.html, se omite inyeccion: %s" % HTML_FILE)
        return

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    json_str = json.dumps(designs, ensure_ascii=False)
    injection = '<script>window.DESIGNS_DATA = %s;</script>' % json_str

    # Reemplazar inyeccion previa si existe
    pattern = re.compile(r'<script>\s*window\.DESIGNS_DATA\s*=.*?</script>', re.DOTALL)
    if pattern.search(html):
        html = pattern.sub(injection, html, count=1)
    else:
        # Insertar justo ANTES de <script type="text/babel">
        babel_pattern = re.compile(r'(<script\s+type="text/babel">)')
        m = babel_pattern.search(html)
        if not m:
            print("[WARN] No se encontro <script type=\"text/babel\"> en el HTML, no se inyecto.")
            return
        insert_pos = m.start()
        html = html[:insert_pos] + injection + "\n" + html[insert_pos:]

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
