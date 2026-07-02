# Nesting Industrial — Guía de Instalación CEP

## Requisitos

- Adobe Illustrator **2020** (v24) o superior (compatible hasta 2026+)
- Python 3.8+ con las dependencias del proyecto instaladas
- No se requiere ninguna app adicional de Adobe

---

## Instalación (2 pasos)

### Paso 1 — Instalar el panel

1. Abre la carpeta `panel\`
2. Haz **doble clic** en `install_panel.bat`
   - Pedirá permisos de administrador — acepta
3. Verás confirmación de cada paso:
   ```
   [1/3] Activando modo desarrollo CEP... OK
   [2/3] Copiando panel...               OK
   [3/3] Verificando instalacion...      OK
   ```
4. **Reinicia Adobe Illustrator**

### Paso 2 — Iniciar el motor

1. Haz doble clic en `start_server.bat`
2. Mantén esa ventana abierta mientras trabajas
3. Verás: `Uvicorn running on http://127.0.0.1:8765`

---

## Abrir el panel en Illustrator

```
Ventana > Extensiones > Nesting Industrial
```

Si no aparece en el menú, verifica:
1. Que cerraste y reabriste Illustrator **después** de instalar
2. Que el `install_panel.bat` mostró "INSTALACION COMPLETADA"

---

## Uso del panel

| Botón | Acción |
|-------|--------|
| 🔍 **Validar** | Verifica que las piezas seleccionadas son válidas sin anidar |
| 🚀 **Anidar** | Extrae la selección, llama al motor y muestra el resultado |
| ✅ **Aplicar al Lienzo** | Re-inyecta las piezas en su posición óptima |

### Flujo recomendado

1. Selecciona las piezas a anidar en Illustrator
2. Click en **Validar** para detectar problemas
3. Ajusta los parámetros (ancho, margen, modo, rotaciones)
4. Click en **Anidar** y espera el resultado
5. Revisa el reporte de eficiencia
6. Click en **Aplicar al Lienzo** si el resultado es satisfactorio
   - Se creará una capa `ANIDAMIENTO_YYYYMMDD_HHMM` con sub-capas por color

---

## Parámetros de configuración

| Campo | Descripción |
|-------|-------------|
| **Ancho Rollo** | Ancho del material en mm (se auto-detecta del artboard) |
| **Alto Bin** | Largo máximo del rollo en mm |
| **Margen Kerf** | Separación entre piezas en mm (típico: 2mm) |
| **Modo** | *Rollo Infinito*: no hay límite de largo. *Retal Fijo*: bin cerrado |
| **Tiempo máx.** | Segundos que puede calcular el motor (más tiempo = mejor resultado) |
| **Rotaciones** | Orientaciones permitidas para cada pieza |

---

## Solución de problemas

### El panel no aparece en Ventana > Extensiones
- Ejecuta `install_panel.bat` como administrador y reinicia Illustrator
- Verifica que existe: `%APPDATA%\Adobe\CEP\extensions\com.turboprint.nesting\CSXS\manifest.xml`

### El punto de estado permanece rojo (desconectado)
- Ejecuta `start_server.bat` y espera a ver `Uvicorn running on http://127.0.0.1:8765`
- Verifica que Python está en el PATH: `python --version`

### Error "NO_SELECTION"
- Selecciona al menos un PathItem en Illustrator antes de hacer clic en Anidar

### Las piezas no se reposicionan correctamente
- Asegúrate de que las piezas usan colores de relleno sólido (no degradados ni sin relleno)
- El sistema convierte automáticamente CMYK y escala de grises a hex RGB

---

## Estructura del proyecto

```
proyecto anidamiento/
├── engine/                    Motor de optimización Python
│   ├── main.py                Servidor FastAPI (puerto 8765)
│   └── core/                  geometry, nfp, bins, search, validator
└── panel/                     Plugin CEP para Illustrator
    ├── CSXS/manifest.xml      Manifiesto CEP (AI 2020-2026+)
    ├── CSInterface.js          Librería oficial Adobe CEP
    ├── index.html             UI del panel
    ├── styles.css             Tema dark glassmorphism
    ├── main.js                Lógica del panel
    ├── host.jsx               ExtendScript (corre dentro de AI)
    ├── start_server.bat       Inicia el motor
    └── install_panel.bat      Instalador de un clic
```
