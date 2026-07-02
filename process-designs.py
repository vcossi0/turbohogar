#!/usr/bin/env python3
"""
TurboHogar Designs Batch Processor
Procesa 3000+ diseños PNG: valida, resizea, genera metadatos.
Uso: python process-designs.py [--config designs-config.json]
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

try:
    from PIL import Image
except ImportError:
    print("❌ Pillow no está instalado. Instala con: pip install Pillow")
    sys.exit(1)


class DesignProcessor:
    def __init__(self, config_path="designs-config.json"):
        self.config = self._load_config(config_path)
        self.designs_dir = Path(self.config["paths"]["designs_folder"])
        self.output_dir = Path(self.config["paths"]["output_folder"])
        self.mockups_dir = Path(self.config["paths"]["mockups_folder"])
        
        self.stats = {"total": 0, "ok": 0, "warnings": 0, "errors": 0}
        self.errors_list = []
        self.warnings_list = []
        self.processed_designs = []
        
    def _load_config(self, path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Archivo config no encontrado: {path}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"❌ JSON inválido en {path}")
            sys.exit(1)
    
    def run(self):
        """Main entry point"""
        print("\n🎨 TurboHogar Design Processor")
        print("=" * 60)
        
        # Validar estructura
        if not self.designs_dir.exists():
            print(f"❌ Carpeta de diseños no encontrada: {self.designs_dir}")
            sys.exit(1)
        
        # Crear output
        self.output_dir.mkdir(exist_ok=True)
        
        # Procesar
        print(f"\n📁 Procesando diseños desde: {self.designs_dir}")
        self._process_all()
        
        # Reportes
        self._generate_reports()
        
        # Resumen
        self._print_summary()
    
    def _process_all(self):
        """Itera todas las carpetas y procesa diseños"""
        design_files = []
        
        # Recolectar todos los PNGs
        for category_dir in sorted(self.designs_dir.iterdir()):
            if not category_dir.is_dir():
                continue
            
            category = category_dir.name
            for png_file in category_dir.glob("*.png"):
                design_files.append((category, png_file))
        
        self.stats["total"] = len(design_files)
        
        if not design_files:
            print("⚠️ No se encontraron archivos PNG en las carpetas")
            return
        
        print(f"📦 Encontrados {len(design_files)} diseños")
        
        # Procesamiento paralelo
        workers = self.config["processing"]["parallel_workers"]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._process_design, cat, file): (cat, file)
                for cat, file in design_files
            }
            
            for i, future in enumerate(as_completed(futures), 1):
                cat, file = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"⚠️ Error procesando {file.name}: {e}")
                
                # Progress
                if i % max(1, len(design_files) // 10) == 0:
                    print(f"  [{i}/{len(design_files)}] ...")
    
    def _process_design(self, category, png_path):
        """Procesa un PNG individual"""
        try:
            # Validar PNG
            validation = self._validate_png(png_path)
            if validation["status"] == "error":
                self.stats["errors"] += 1
                self.errors_list.append({
                    "category": category,
                    "file": png_path.name,
                    "error": validation["message"]
                })
                return
            
            if validation["status"] == "warning":
                self.stats["warnings"] += 1
                self.warnings_list.append({
                    "category": category,
                    "file": png_path.name,
                    "warning": validation["message"]
                })
            else:
                self.stats["ok"] += 1
            
            # Abrir imagen
            img = Image.open(png_path)
            original_w, original_h = img.size
            aspect_ratio = original_w / original_h if original_h > 0 else 0
            
            # Crear carpeta de salida
            output_subdir = self.output_dir / category / png_path.stem
            output_subdir.mkdir(parents=True, exist_ok=True)
            
            # Copiar original
            if self.config["processing"]["preserve_original"]:
                img.save(output_subdir / "original.png", "PNG", optimize=True)
            
            # Procesar para cada producto
            compatibility = {}
            for product_key, product_spec in self.config["products"].items():
                resized = self._resize_for_product(img, product_spec, aspect_ratio)
                if resized:
                    resized.save(
                        output_subdir / f"{product_key}.png",
                        "PNG",
                        optimize=True
                    )
                    compatibility[product_key] = {
                        "status": "ok",
                        "ratio_match": f"{aspect_ratio:.2f}",
                        "action": product_spec["behavior"]
                    }
            
            # Generar thumbnails
            self._create_thumbnail(img, output_subdir, "gallery", 300)
            self._create_thumbnail(img, output_subdir, "admin", 180)
            
            # Crear meta.json
            design_id = f"{category.lower().replace(' ', '_')}_{png_path.stem.lower().replace(' ', '_')}"
            meta = {
                "id": design_id,
                "name": png_path.stem.replace("_", " ").title(),
                "category": category,
                "original": {
                    "filename": png_path.name,
                    "width": original_w,
                    "height": original_h,
                    "aspect_ratio": round(aspect_ratio, 3),
                    "size_bytes": png_path.stat().st_size,
                    "dpi_estimated": 300
                },
                "validation": validation,
                "compatibility": compatibility,
                "files_created": [
                    f"{k}.png" for k in compatibility.keys()
                ] + ["thumb_gallery.png", "thumb_admin.png"],
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            
            with open(output_subdir / "meta.json", "w") as f:
                json.dump(meta, f, indent=2)
            
            self.processed_designs.append(meta)
        
        except Exception as e:
            self.stats["errors"] += 1
            self.errors_list.append({
                "category": category,
                "file": png_path.name,
                "error": str(e)
            })
    
    def _validate_png(self, path):
        """Valida un archivo PNG"""
        try:
            # Verificar extensión
            if path.suffix.lower() != ".png":
                return {"status": "error", "message": "No es un archivo PNG"}
            
            # Verificar tamaño
            size = path.stat().st_size
            if size < self.config["validation"]["min_file_size_bytes"]:
                return {"status": "error", "message": f"Archivo muy pequeño ({size} bytes)"}
            if size > self.config["validation"]["max_file_size_bytes"]:
                return {"status": "error", "message": f"Archivo muy grande ({size} bytes)"}
            
            # Verificar que sea PNG válido
            img = Image.open(path)
            if img.format != "PNG":
                return {"status": "error", "message": f"No es PNG válido (formato: {img.format})"}
            
            w, h = img.size
            if w < 100 or h < 100:
                return {"status": "error", "message": f"Resolución mínima muy baja ({w}×{h})"}
            
            # Warning si resolución baja
            min_res = 1600 * 1200  # mínimo general
            if (w * h) < min_res:
                return {"status": "warning", "message": f"Resolución baja ({w}×{h}), verificar DPI"}
            
            return {"status": "ok", "message": "PNG válido"}
        
        except Exception as e:
            return {"status": "error", "message": f"Error al leer PNG: {str(e)}"}
    
    def _resize_for_product(self, img, product_spec, aspect_ratio):
        """Resizea imagen para un producto específico"""
        try:
            opt_w = product_spec["optimal_resolution"]["width"]
            opt_h = product_spec["optimal_resolution"]["height"]
            expected_ratio = product_spec["aspect_ratio"]
            tolerance = self.config["validation"]["aspect_ratio_tolerance"]
            
            # Detectar si el ratio es similar
            ratio_diff = abs(aspect_ratio - expected_ratio) / expected_ratio
            
            if ratio_diff <= tolerance:
                # Resize simple
                return img.resize((opt_w, opt_h), Image.Resampling.LANCZOS)
            else:
                # Letterbox (centerbox)
                canvas = Image.new("RGB", (opt_w, opt_h), color=(255, 255, 255))
                
                # Calcular dimensiones manteniendo aspect ratio
                if aspect_ratio > expected_ratio:
                    # Más ancho que esperado
                    new_w = opt_w
                    new_h = int(opt_w / aspect_ratio)
                else:
                    # Más alto que esperado
                    new_h = opt_h
                    new_w = int(opt_h * aspect_ratio)
                
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                offset_x = (opt_w - new_w) // 2
                offset_y = (opt_h - new_h) // 2
                canvas.paste(resized, (offset_x, offset_y))
                
                return canvas
        
        except Exception as e:
            print(f"⚠️ Error resizeando: {e}")
            return None
    
    def _create_thumbnail(self, img, output_dir, thumb_type, size):
        """Crea thumbnail"""
        try:
            thumb = img.copy()
            thumb.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Centrar en canvas cuadrado
            canvas = Image.new("RGB", (size, size), color=(240, 240, 240))
            offset = ((size - thumb.width) // 2, (size - thumb.height) // 2)
            canvas.paste(thumb, offset)
            
            quality = self.config["thumbnails"][thumb_type]["quality"]
            canvas.save(
                output_dir / f"thumb_{thumb_type}.png",
                "PNG",
                optimize=True,
                quality=quality
            )
        except Exception as e:
            print(f"⚠️ Error generando thumbnail {thumb_type}: {e}")
    
    def _generate_reports(self):
        """Genera reportes JSON y TXT"""
        # REPORT.json
        report = {
            "summary": {
                "total_designs": self.stats["total"],
                "processed": self.stats["total"],
                "ok": self.stats["ok"],
                "warnings": self.stats["warnings"],
                "errors": self.stats["errors"],
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "errors": self.errors_list,
            "warnings": self.warnings_list,
            "designs_sample": self.processed_designs[:5]  # Primeros 5 como muestra
        }
        
        with open(self.output_dir / "REPORT.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # SUMMARY.txt
        summary_text = f"""
TurboHogar Designs — Procesamiento Completo
{'='*60}

📊 RESUMEN
  Total de diseños: {self.stats['total']}
  ✅ Óptimos:      {self.stats['ok']}
  ⚠️  Advertencias: {self.stats['warnings']}
  ❌ Errores:      {self.stats['errors']}

📁 Carpeta de salida: {self.output_dir}

Estructura generada:
  - Diseños resizeados por producto (4 versiones por diseño)
  - Thumbnails gallery (300×300) y admin (180×180)
  - meta.json con specs y compatibilidad
  - REPORT.json con detalles completos

Próximos pasos:
  1. Revisar REPORT.json para errors/warnings
  2. Subir processed/ a storage (S3/R2)
  3. Inyectar metadatos en base de datos
  4. Actualizar viewer 3D con los diseños

Generado: {datetime.utcnow().isoformat()}
"""
        
        with open(self.output_dir / "SUMMARY.txt", "w") as f:
            f.write(summary_text)
    
    def _print_summary(self):
        """Imprime resumen en consola"""
        print("\n" + "="*60)
        print("✅ PROCESAMIENTO COMPLETO")
        print("="*60)
        print(f"\n📊 Resultados:")
        print(f"  Total:       {self.stats['total']}")
        print(f"  ✅ Óptimos:  {self.stats['ok']}")
        print(f"  ⚠️  Avisos:   {self.stats['warnings']}")
        print(f"  ❌ Errores:  {self.stats['errors']}")
        print(f"\n📁 Salida: {self.output_dir}")
        print(f"   → REPORT.json")
        print(f"   → SUMMARY.txt")
        print(f"\n✨ Ready para inyectar en TurboHogar!\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TurboHogar Designs Processor")
    parser.add_argument("--config", default="designs-config.json", help="Config JSON path")
    args = parser.parse_args()
    
    processor = DesignProcessor(args.config)
    processor.run()
