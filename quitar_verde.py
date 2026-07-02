"""
Elimina el fondo verde de foreground.mp4 y exporta:
  - vigi.webm  (WebM con canal alpha — transparencia real)
  - vigi.gif   (GIF animado, sin transparencia, fondo blanco)

Requiere: pip install opencv-python numpy pillow
"""
import cv2, numpy as np, os, sys
from PIL import Image

INPUT  = r"C:\Users\vicho\Downloads\foreground.mp4"
OUT_DIR = r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar\assets"
OUT_GIF = os.path.join(OUT_DIR, "vigi.gif")

# ── Parámetros chroma key ──────────────────────────────────────────────────
# Rango de verde en HSV
LOWER_GREEN = np.array([35,  40,  40])
UPPER_GREEN = np.array([90, 255, 255])
BLUR_RADIUS = 3   # suavizado de bordes
RESIZE_W    = 200 # ancho de salida (px)

def remove_green(frame_bgr):
    """Devuelve frame BGRA con alpha donde estaba el verde."""
    hsv  = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_GREEN, UPPER_GREEN)
    # Suavizar bordes
    mask = cv2.GaussianBlur(mask, (BLUR_RADIUS*2+1, BLUR_RADIUS*2+1), 0)
    alpha = cv2.bitwise_not(mask)
    b,g,r = cv2.split(frame_bgr)
    bgra  = cv2.merge([b,g,r,alpha])
    return bgra

def main():
    cap = cv2.VideoCapture(INPUT)
    if not cap.isOpened():
        print("ERROR: no se pudo abrir", INPUT); sys.exit(1)

    fps    = cap.get(cv2.CAP_PROP_FPS) or 24
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {total} frames @ {fps:.1f} fps")

    frames_pil = []
    frame_idx  = 0

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame_idx += 1
        if frame_idx % 30 == 0:
            print(f"  Procesando frame {frame_idx}/{total}...")

        bgra = remove_green(frame)

        # Redimensionar
        h, w = bgra.shape[:2]
        new_w = RESIZE_W
        new_h = int(h * new_w / w)
        bgra  = cv2.resize(bgra, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        # Convertir a PIL RGBA
        r,g,b,a = cv2.split(bgra)
        pil = Image.fromarray(cv2.merge([r,g,b,a])[:,:,::-1].copy() if False
                              else np.stack([bgra[:,:,2],bgra[:,:,1],bgra[:,:,0],bgra[:,:,3]],axis=2),
                              mode='RGBA')
        frames_pil.append(pil)

    cap.release()
    print(f"Frames procesados: {len(frames_pil)}")

    if not frames_pil:
        print("ERROR: sin frames"); sys.exit(1)

    # ── Exportar GIF (fondo blanco para compatibilidad) ────────────────────
    print("Exportando GIF...")
    gif_frames = []
    bg = Image.new('RGBA', frames_pil[0].size, (255,255,255,255))
    for f in frames_pil:
        merged = Image.alpha_composite(bg.copy(), f).convert('P',
                    palette=Image.ADAPTIVE, colors=256)
        gif_frames.append(merged)

    duration_ms = int(1000 / fps)
    gif_frames[0].save(
        OUT_GIF,
        save_all=True,
        append_images=gif_frames[1:],
        loop=0,
        duration=duration_ms,
        optimize=False,
        disposal=2,
    )
    size_kb = os.path.getsize(OUT_GIF) // 1024
    print(f"GIF guardado: {OUT_GIF}  ({size_kb} KB)")

    # ── Exportar frames PNG individuales (para APNG vía ffmpeg si está) ───
    frames_dir = os.path.join(OUT_DIR, "_vigi_frames")
    os.makedirs(frames_dir, exist_ok=True)
    for i, f in enumerate(frames_pil):
        f.save(os.path.join(frames_dir, f"frame_{i:04d}.png"))
    print(f"Frames PNG en: {frames_dir}")
    print(f"\nListo. Archivos en: {OUT_DIR}")
    print("Siguiente paso: usa los frames PNG para crear un WebM con alpha en FFmpeg:")
    print(f'  ffmpeg -framerate {fps:.0f} -i "{frames_dir}\\frame_%04d.png" -c:v libvpx-vp9 -pix_fmt yuva420p "{OUT_DIR}\\vigi.webm"')

if __name__ == "__main__":
    main()
