import os
import shutil

BASE_DIR     = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\designs\Categorias"
PROCESSED_DIR = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\processed"
OUTPUT_DIR   = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\ordenado"

SUFFIXES = ["_comun", "_h1", "_h2", "_v1", "_v2"]

def main():
    ok = 0
    warn = 0
    total = 0

    for root, dirs, files in os.walk(BASE_DIR):
        for file in files:
            if not file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')):
                continue

            total += 1
            nombre_base = os.path.splitext(file)[0]
            rel_folder  = os.path.relpath(root, BASE_DIR)  # e.g. "DC COMICS\Aquaman"

            # Carpeta destino: ordenado\DC COMICS\Aquaman\#DC03_06\
            dest_folder = os.path.join(OUTPUT_DIR, rel_folder, nombre_base)
            os.makedirs(dest_folder, exist_ok=True)

            # Copiar diseño original
            src_original = os.path.join(root, file)
            shutil.copy2(src_original, os.path.join(dest_folder, file))

            # Copiar los mockups que existan
            mockups_encontrados = 0
            proc_folder = os.path.join(PROCESSED_DIR, rel_folder)

            for suffix in SUFFIXES:
                mockup_name = f"{nombre_base}{suffix}.png"
                src_mockup  = os.path.join(proc_folder, mockup_name)
                if os.path.exists(src_mockup):
                    shutil.copy2(src_mockup, os.path.join(dest_folder, mockup_name))
                    mockups_encontrados += 1

            if mockups_encontrados == 3:
                ok += 1
                print(f"  OK  {rel_folder}\\{nombre_base}  ({mockups_encontrados} mockups)")
            else:
                warn += 1
                print(f"  WARN {rel_folder}\\{nombre_base}  (solo {mockups_encontrados}/3 mockups)")

    print(f"\n{'='*60}")
    print(f"  TOTAL diseños: {total}")
    print(f"  Completos (3 mockups): {ok}")
    print(f"  Incompletos:           {warn}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
