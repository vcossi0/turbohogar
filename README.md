# TurboHogar

Tienda de cuadros personalizados de cultura pop para el mercado chileno, desarrollada para un cliente del
rubro de la impresión. Lo distintivo del proyecto no es la vitrina, sino el **motor propio que automatiza
Photoshop** para generar mockups fotorrealistas a escala: un proceso por lotes recorrió **2.130 diseños** y
produjo **6.390 mockups** (tres vistas por diseño).

**▶ Demo en vivo:** https://vcossi0.github.io/turbohogar/ — muestra curada (~140 diseños de las 6 categorías)
con mockups optimizados para web. El uploader corre en modo demo, ya que el motor de montaje requiere
Photoshop local (ver más abajo).

## El motor de mockups

Componer los cuadros por software puro se ve plano: la imagen queda pegada sin perspectiva ni sombra. Para
conservar el realismo opté por reutilizar plantillas `.psd` profesionales, que ya traen montada la
perspectiva, la textura del lienzo y las luces sobre un *Smart Object*. El motor abre la plantilla, reemplaza
el contenido del Smart Object por el diseño mediante scripting JSX y deja que Photoshop re-renderice el
resultado; así cada cuadro hereda el realismo del template en lugar de imitarlo.

Ese mismo motor funciona en dos modos:

- **Por lotes** (`motor mockup/1/`): recorre el catálogo completo con Python + Pillow y automatización de
  Photoshop (`win32com` + JSX), generando las tres vistas de cada diseño.
- **En vivo** (`server.py`): una API Flask recibe la imagen que sube el cliente, la inserta en las plantillas
  y devuelve sus mockups. La tienda consulta `/health` para indicar si el motor está activo u offline.

## Arquitectura

| Componente | Rol |
|---|---|
| `turbohogar.html` | Tienda en un solo archivo — React 18 (CDN) con JSX transpilado en el navegador (Babel). Catálogo con búsqueda y filtros, carrito y flujo de compra, panel de administración. |
| `server.py` | API Flask local que procesa las imágenes del cliente con el motor Photoshop y sirve los resultados. |
| `motor mockup/1/` | Motor por lotes (Python + Pillow + Photoshop vía COM/JSX). |
| `motor mockup/Panel_v2_Final/` | Panel CEP de Photoshop (`host.jsx` + CSInterface) para operar el motor desde el propio Photoshop. |
| `process-designs.py`, `build_manifest.py` | Validación de diseños (resolución, DPI, proporción) y generación del catálogo servible. |

## Stack

React 18 · Flask · Python (Pillow, pywin32) · Adobe ExtendScript/JSX · Photoshop CEP · Tailwind (vía CDN)

## Estado y nota sobre el despliegue

El motor depende de Photoshop mediante automatización COM, que solo corre en Windows con la aplicación
abierta; por eso no puede vivir en un hosting serverless (tipo Vercel). El catálogo funciona con los 6.390
mockups ya generados, y la generación en vivo se documenta en video. El siguiente paso natural del proyecto
es portar el motor a una versión *headless* con OpenCV/Pillow, que reproduzca la perspectiva y las sombras de
cada plantilla sin depender de Photoshop, para poder hostearlo en la nube.

## Ejecutar localmente

```bash
# 1) Motor de mockups — requiere Windows con Photoshop abierto
pip install flask flask-cors pillow pywin32
python server.py              # queda en http://localhost:5000

# 2) Tienda
python -m http.server 8000    # y abrir turbohogar.html
```

## Sobre los archivos excluidos

Este repositorio contiene solo el código. Los diseños fuente, las plantillas `.psd` (assets con licencia) y
los cientos de GB de mockups generados quedan fuera a propósito.

---

Desarrollado por **Vicente Cossío** — [github.com/vcossi0](https://github.com/vcossi0)
