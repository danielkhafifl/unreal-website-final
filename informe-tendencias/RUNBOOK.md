# Manual de ejecución: informe de tendencias de moda masculina (cada lunes)

Este manual lo sigue la sesión programada que se lanza cada lunes de madrugada (hora de Panamá). Objetivo: que marvin@fgpanama.com reciba antes de las 7:00 a. m. (America/Panama, UTC-5) un correo con el informe de tendencias de moda masculina para un equipo de diseño de marcas de ropa de caballero en Latinoamérica.

`<REPO>` = la raíz del repositorio clonado. Todo el material vive en la rama `claude/informe-tendencias-moda-masculina`.

## 0. Preparación

```bash
cd <REPO>
git fetch origin claude/informe-tendencias-moda-masculina
git checkout claude/informe-tendencias-moda-masculina
git pull origin claude/informe-tendencias-moda-masculina
cd informe-tendencias
npm install --silent
pip install -q -r requirements.txt
mkdir -p images && touch images/registry.tsv
curl -s -o /dev/null -w '%{http_code}\n' https://www.vogue.com/   # debe dar 200
```

Si vogue.com no responde 200 (red bloqueada), no inventes contenido: envía igualmente un correo breve a marvin@fgpanama.com explicando que esta semana no se pudo generar el informe porque la red del entorno bloquea las fuentes, y que se arregla en la configuración del entorno (Network access). Luego termina.

## 1. Tipo de edición y fechas

- Fecha de edición = hoy (lunes), en formato «9 de noviembre de 2026».
- Ventana de novedades = los 7 días anteriores (lunes a domingo de la semana pasada).
- **Primer lunes del mes (día 1 a 7): «Informe mensual completo».** Rehace el informe completo de los siete departamentos, con la misma estructura y profundidad que el último informe completo en `<REPO>/reports/` (el primero fue `Tendencias moda masculina noviembre 2026.md`).
- **Resto de lunes: «Actualización semanal».** Informe más corto (unas 20–30 páginas) centrado en lo nuevo de la semana.
- Lee el informe más reciente en `<REPO>/reports/` para saber qué tendencias ya se documentaron y no repetir fotos ni enlaces.

## 2. Investigación (con subagentes)

Usa la herramienta Agent con `subagent_type: "general-purpose"`. Cada subagente debe leer primero `<REPO>/informe-tendencias/BRIEF_AGENTES.md` (sustituye `<REPO>` y `<fecha de la edición>` en tu encargo) y trabajar con las herramientas de `informe-tendencias/tools/`:
- `vogue_looks.py` (looks de Vogue Runway con número, foto y crédito; hoja de contacto para elegir a la vista),
- `page_info.py` (abrir páginas, fechas, og:image, precios),
- `fetch_img.py` (descargar cada foto usada; obligatorio para que el PDF la incruste),
- registro anti-duplicados `informe-tendencias/images/registry.tsv` (antes de esta edición, añade al registro las URL de imagen del informe anterior para no repetirlas: extrae las URL de la columna «Imagen» de ese Markdown).

Reparto recomendado:
- **Semanal (4 subagentes):** (1) Novedades de la semana y panorama (lanzamientos, colaboraciones, nombramientos, resultados de empresas, índices como Lyst, eventos y moda en Latinoamérica); (2) Denim + Formal y sastrería + Urbano; (3) Streetwear + Deportivo y athleisure; (4) Básicos, polos y camisetas + Calzado y accesorios. Cada uno: solo lo nuevo o lo que cambió en la ventana, más confirmación de qué tendencias siguen vigentes; 1–3 tendencias con novedad por departamento, cada una con 3–4 fotos reales y 2–4 productos con ficha activa.
- **Mensual completo (8 subagentes):** panorama + uno por departamento, como en la edición de noviembre de 2026.
- Pide a cada subagente que escriba su parte en un archivo Markdown propio y un archivo `_fuentes.md`, siguiendo las convenciones del brief.

Reglas que no se negocian: nada inventado (datos, fechas, precios, looks, enlaces); popularidad, búsquedas, reventa y conteos de pasarela no son ventas; resultados de empresas etiquetados «datos de la empresa»; hechos separados de recomendaciones; español.

## 3. Estructura del Markdown

Convenciones que entiende `build.py` (mira el informe de noviembre de 2026 como ejemplo):
- `# Capítulo` = página nueva. `# 01 · Denim` (número de dos cifras + « · ») = capítulo de departamento con cabecera grande; su primer párrafo `**Enfoque:** ...` es la entradilla; sus `###` dentro de `## Tendencias principales` aparecen en el índice.
- `Estado: [VIGENTE FW26] [EMERGENTE SS27] [NOVEDAD ESTA SEMANA] [EN DECLIVE] [SIN CONFIRMAR]` = etiquetas.
- Tablas con cabeceras exactas: referencias `| Marca | Colección / temporada | Look | Qué muestra | Crédito | Imagen | Página |` (fichas con foto), productos `| Tendencia | Marca | Producto | Precio | Imagen | Enlace | Verificación |`, propuestas `| Prenda | Corte | Tela | Colores | Detalles |` bajo `### Comerciales` / `### Arriesgadas`, novedades `| Fecha | Novedad | Por qué importa para diseño | Fuente |`. Tablas de más de 13 filas se convierten en tarjetas.
- Callouts: `> **Recomendación:**`, `> **No verificado:**`, `> **Clima cálido y Latinoamérica:**`, `> **Qué vale la pena adaptar y por qué:**`, `> **Novedad esta semana:**`.
- `Paleta: Nombre #RRGGBB; ...` = muestras de color orientativas.

**Semanal:** `# Resumen de la semana` (6–10 hallazgos con fuente y fecha + «Qué hacer esta semana», separado como recomendaciones) → `# Novedades de la semana` (tabla de novedades) → `# Cambios por departamento` con un `## 01 · Denim`, `## 02 · Formal y sastrería`... (dentro, `### <tendencia>` con Estado, Hecho observado, referencias con foto, productos y una línea de lectura; si no hubo novedades, un párrafo «Sin cambios relevantes esta semana; siguen vigentes: …») → `# Alcance y método` (fechas, fuentes abiertas, qué no se pudo verificar) → `# Fuentes y enlaces consultados`.

**Mensual:** misma estructura que el informe de noviembre de 2026 (Resumen ejecutivo, Alcance, Panorama, 7 departamentos con propuestas comerciales y arriesgadas, Fuentes).

## 4. Generar el PDF

Crea `work/meta.json`:
```json
{"date": "9 de noviembre de 2026", "edition": "Actualización semanal",
 "subtitle": "Actualización semanal para diseño y desarrollo de producto",
 "coverage": ["Novedades del 2 al 8 de noviembre de 2026", "Otoño-Invierno 2026 (en tienda) · Primavera-Verano 2027 (pasarelas de junio de 2026)"],
 "footer": "Tendencias de moda masculina · Actualización del 9 de noviembre de 2026"}
```
Antes de generar, corrige los créditos de Vogue con el crédito propio de cada look: `python3 tools/fix_credits.py "<md>"` (usa el campo desktopCredit de cada foto). No incrustes fotos de producto con modelos generados por IA (por ejemplo, fichas que dicen «Modelo realizado con IA»): usa una foto plana de la misma ficha o deja la celda «Imagen» en «—».

Guarda el Markdown final en `<REPO>/reports/<AAAA-MM-DD> Tendencias moda masculina <semanal|mensual>.md` y genera:
```bash
python3 build.py "<md>" "<REPO>/reports/<mismo nombre>.pdf" --meta work/meta.json
python3 qa_pdf.py "<pdf>" "<md>" work/qa
```
Revisa TODAS las hojas `work/qa/contact-*.png` con Read: sin fotos cortadas, sin tablas partidas, sin páginas casi vacías, portada e índice correctos. Corrige y vuelve a generar. Si el PDF pasa de 14 MB, añade a meta.json `"img_max": [460, 690], "img_q": 72` y regenera.

## 5. Entrega

1. **Página privada con el PDF (Artifact).** Carga primero la skill `artifact-design`. Escribe una página HTML sencilla (título, fecha, 5–8 hallazgos, botón «Descargar PDF» que enlaza a `informe.pdf`) y publícala con la herramienta Artifact (`file_path` = la página, `files` = {"informe.pdf": "<ruta del pdf>"}, `icon`: "report"). Cada edición es un artifact nuevo, para que los enlaces de correos anteriores sigan funcionando.
2. **Correo** con `mcp__Gmail__send_message` a `marvin@fgpanama.com` (sin adjuntos: el PDF es demasiado grande para el conector):
   - Asunto: `Tendencias moda masculina · Actualización semanal del 9 nov 2026` (o `· Informe mensual completo de <mes> <año>`).
   - `htmlBody`: saludo breve, enlace destacado al informe (el del artifact), 5–8 hallazgos clave con fecha y fuente, 3–5 novedades de la semana y 3 recomendaciones (marcadas como recomendaciones), y una línea con lo que no se pudo verificar. `body`: la misma información en texto plano.
   - Si el artifact falla, usa como enlace el PDF en GitHub: `https://github.com/danielkhafifl/unreal-website-final/blob/claude/informe-tendencias-moda-masculina/reports/<nombre codificado>.pdf` y dilo en el correo.
3. **Guardar:** `git add reports/ informe-tendencias/` (las imágenes y cachés están ignoradas), commit y `git push -u origin claude/informe-tendencias-moda-masculina`.

## 6. Si algo falla

Nunca envíes un informe con datos o fotos inventados. Si una parte no se pudo completar, entrégala igual indicando qué falta y por qué, tanto en el informe (capítulo de alcance) como en el correo.
