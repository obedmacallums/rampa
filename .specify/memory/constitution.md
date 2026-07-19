<!--
Informe de Impacto de Sincronización
- Cambio de versión: 1.2.0 → 1.3.0 (adición menor)
- Cambios: nuevo Principio XI (IA como Servicio Aislado, Sujeta a Autoridad Humana);
  nueva fase V6 en el roadmap con módulos de IA (segmentación de ortofotos con SAM,
  segmentación semántica de nubes de puntos, IA generativa para reportes/consultas,
  predicción de degradación de caminos); nueva restricción técnica sobre inferencia
  de IA como servicio aislado, versionado de modelos y confidencialidad de datos.
- Principios modificados: ninguno renombrado ni redefinido.
- Historial del documento:
  - 1.3.0: adición de IA (Principio XI, fase V6, restricción de inferencia).
  - 1.2.0: adopción inicial en el repositorio (.specify/memory/constitution.md).
  - 1.2.0: se agrega el procesamiento fotogramétrico en plataforma (fotos de dron →
    NodeODM) como módulo futuro del roadmap (V5) y como restricción técnica: el motor
    fotogramétrico opera como servicio aislado orquestado por el pipeline de ingesta,
    produciendo los mismos artefactos derivados (nube → DEM/COG/COPC); se registra la
    consideración de licencia AGPL de ODM/NodeODM.
  - 1.1.0: proyecto renombrado a "Plataforma de Auditoría Geométrica para Faenas
    Mineras"; nuevo Principio X (Enfoque Minero, Núcleo Neutro); roadmap extendido con
    cubicación/multitemporal, auditoría de bancos y bermas de contención, y distancia
    de visibilidad en curvas.
- Plantillas revisadas:
  - ✅ .specify/templates/plan-template.md — gate "Constitution Check" genérico, se
    resuelve dinámicamente contra este archivo; sin cambios necesarios.
  - ✅ .specify/templates/spec-template.md — sin referencias a principios; alineada.
  - ✅ .specify/templates/tasks-template.md — sin referencias a principios; alineada.
  - ✅ .specify/templates/checklist-template.md — sin referencias a principios; alineada.
- TODOs diferidos: ninguno.
-->

# Constitución — Plataforma de Auditoría Geométrica para Faenas Mineras

Plataforma web para ingestar nubes de puntos / mallas de faenas mineras (típicamente de vuelos de dron), definir o detectar automáticamente ejes de caminos, evaluarlos contra parámetros geométricos configurables (pendiente, curvatura, altura de bermas, ancho de calzada, peralte), visualizar el cumplimiento como segmentos semaforizados (verde/amarillo/rojo) y generar reportes automáticos — incluyendo reportes por zona — alineados con la normativa minera chilena (DS 132) y criterios de diseño por flota. La evaluación de caminos es el producto inicial; el mismo motor sustenta módulos futuros dentro de la misma faena: cubicación de acopios y comparación multitemporal, auditoría de bancos y bermas de contención, análisis de distancia de visibilidad en curvas, procesamiento fotogramétrico en plataforma (fotos de dron → nube/ortofoto vía NodeODM) como fuente de ingesta adicional, y capacidades de IA (segmentación asistida de ortofotos y nubes de puntos, generación asistida de reportes, predicción de degradación) siempre bajo el modelo de detección asistida con autoridad humana.

## Principios Fundamentales

### I. Análisis sobre Rasters, Visualización sobre Tiles (NO NEGOCIABLE)

Todo cálculo geométrico (pendiente, curvatura, secciones transversales, detección de bermas, ancho) DEBE ejecutarse contra un DEM raster (Cloud Optimized GeoTIFF) generado en la ingesta — nunca contra la nube de puntos cruda. La nube cruda existe solo para visualización, servida como COPC (o Cesium 3D Tiles para mallas) con nivel de detalle progresivo. No puede diseñarse ninguna funcionalidad que requiera consultar puntos crudos en tiempo de análisis.

**Justificación:** El análisis raster es órdenes de magnitud más rápido, testeable con numpy/rasterio, y la resolución (10–25 cm) es suficiente para todas las métricas objetivo. Mezclar ambas responsabilidades es el principal modo de falla arquitectónico en esta clase de producto.

### II. Backend Delgado, Frontend Interactivo

El backend (Django + GeoDjango + PostGIS) es responsable de: pipelines de ingesta, persistencia, usuarios/proyectos, generación de reportes y servir artefactos derivados (COG, COPC, tiles). Todo análisis interactivo — cambios de umbrales, recoloreo, inspección de secciones transversales, navegación del perfil — DEBE ejecutarse del lado del cliente contra el COG del DEM vía HTTP range requests, con cero viajes al servidor. Un slider de parámetros que requiera una llamada al backend para recolorear el eje viola este principio.

**Justificación:** La respuesta instantánea a los parámetros de evaluación es el diferenciador central de UX; la interactividad dependiente del servidor no escala y se siente lenta.

### III. Ingesta Asíncrona, Siempre

La ingesta de archivos (LAS/LAZ/E57/malla, 10–50 GB) DEBE ser asíncrona (Celery + Redis), reanudable (subida multipart/tus a almacenamiento de objetos compatible con S3) y observable (estados de progreso por etapa visibles para el usuario). Ninguna petición síncrona puede tocar jamás un archivo de nube de puntos crudo. Los artefactos derivados (DEM COG, hillshade, COPC, tiles de ortofoto) son salidas inmutables de una ejecución versionada del pipeline; reprocesar crea una versión nueva, nunca muta en el lugar.

### IV. Modelo de Evaluación Basado en Estaciones

La evaluación de caminos sigue el modelo clásico de alineamiento: eje → estaciones a intervalos fijos (1–5 m) → secciones transversales perpendiculares muestreadas del DEM → métricas por estación → estado de cumplimiento por segmento. Todas las métricas, umbrales y resultados DEBEN ser trazables a estaciones (persistidas en PostGIS con geometría + valores de métricas). La estación es la unidad atómica de análisis, reporte y auditoría. Toda métrica nueva DEBE poder expresarse como función del perfil longitudinal y/o de la sección transversal en una estación.

### V. Detección Asistida, Autoridad Humana (NO NEGOCIABLE)

Las salidas automáticas (extracción de eje, detección de bermas, detección de bordes de calzada) son borradores, nunca veredictos. Toda detección automática DEBE: (a) llevar un puntaje de confianza por estación, (b) ser auditable visualmente (sección transversal renderizada con los elementos detectados marcados), y (c) ser corregible manualmente, con las correcciones persistidas y con precedencia sobre una re-detección. La plataforma se vende como "detección asistida con auditoría visual" — nunca como certificación de cumplimiento totalmente automática. Los reportes DEBEN distinguir valores auto-detectados de valores verificados por humanos.

**Justificación:** Las bermas son irregulares y críticas para la seguridad; sobreprometer automatización crea responsabilidad legal y destruye la confianza de prevencionistas y reguladores.

### VI. Perfiles de Evaluación como Datos de Primera Clase

Los umbrales de cumplimiento nunca se escriben en el código. Los rangos verde/amarillo/rojo por métrica viven en **perfiles de evaluación** reutilizables y versionados, asociados a un vehículo/flota de diseño (ej. "CAT 797F — DS 132"). Un resultado de análisis almacena la versión del perfil contra la que fue evaluado, de modo que los reportes históricos sigan siendo reproducibles incluso después de editar el perfil. El criterio de altura de berma expresado como fracción del diámetro de neumático DEBE soportarse nativamente.

### VII. Los Reportes Son Artefactos Reproducibles

Todo reporte (de faena completa o filtrado por zona) se genera del lado del servidor (HTML → PDF) a partir de datos de estaciones persistidos + una versión específica del perfil de evaluación + una versión específica de la ejecución del pipeline. Regenerar un reporte pasado DEBE producir resultados idénticos. Los reportes DEBEN incluir: mapa del eje semaforizado, perfil longitudinal, tabla de tramos no conformes con kilometraje (km inicio/fin), secciones transversales críticas y resumen ejecutivo de cumplimiento. El formato del reporte apunta a ser presentable ante Sernageomin.

### VIII. Test-First para el Núcleo de Análisis

El motor de análisis (extracción de perfil, secciones transversales, ajuste de curvatura, detección de bermas/bordes, clasificación de cumplimiento) DEBE desarrollarse como una librería Python independiente del framework, con cobertura pytest contra DEMs sintéticos de verdad conocida (ej. una rampa generada con pendiente exacta de 9% debe clasificar como amarillo bajo el perfil por defecto). Ningún código de análisis se despliega sin tests de verdad conocida. Las capas de UI y API consumen esta librería; nunca reimplementan su lógica.

### IX. Bilingüe por Diseño

La interfaz de usuario, las plantillas de reporte y los documentos generados DEBEN soportar español (primario, con terminología minera chilena: berma, rasante, peralte, calzada, rajo) e inglés (secundario). El código, los identificadores, los mensajes de commit y la documentación interna se escriben en inglés. Ningún texto visible al usuario puede quedar fijo en el código fuera de la capa de i18n.

### X. Enfoque Minero, Núcleo Neutro

El producto, la interfaz, los reportes, la terminología y el posicionamiento comercial están dedicados a la minería: faenas, rajos, rampas, flota CTH y cumplimiento del DS 132. No se desarrollarán funcionalidades ni verticales fuera del contexto minero (forestal, vialidad urbana, canales u otros) sin una enmienda a esta constitución. Toda expansión funcional DEBE servir al mismo comprador (superintendencias de operaciones mina, prevención de riesgos y planificación) y apoyarse en el mismo motor de análisis; los módulos previstos bajo este criterio son: (a) cubicación de acopios y botaderos con comparación multitemporal de DEMs, (b) auditoría geométrica de bancos, taludes y bermas de contención, y (c) distancia de visibilidad en curvas e intersecciones según el vehículo de diseño.

Sin embargo, el núcleo de análisis y el modelo de datos DEBEN mantenerse neutros de dominio: las entidades se nombran de forma genérica (`Alignment`, `Station`, `CrossSection`, `Surface`, `EvaluationProfile`), y todo el conocimiento normativo y de flota (umbrales DS 132, criterios por camión, textos de reporte) vive exclusivamente en perfiles de evaluación y plantillas versionadas — nunca en el código del motor. El enfoque minero es una decisión de producto; la neutralidad del núcleo es una decisión de arquitectura, y ambas coexisten.

**Justificación:** El foco en un solo vertical concentra el esfuerzo comercial y de producto donde el autor ya tiene red y conocimiento del dominio; la neutralidad del núcleo asegura que ese foco no hipoteque el futuro ni contamine el motor con reglas de negocio.

### XI. IA como Servicio Aislado, Sujeta a Autoridad Humana

Toda capacidad de IA/ML (segmentación de ortofotos con SAM u otro modelo de fundación, segmentación semántica de nubes de puntos, generación de texto de reportes, asistentes de consulta, modelos predictivos de degradación) se rige por estas reglas:

- **Aislamiento:** los modelos de inferencia DEBEN operar como servicios independientes y contenerizados, orquestados vía API por el pipeline o el backend — nunca embebidos en el núcleo de análisis determinista. La plataforma DEBE seguir siendo completamente funcional (ingesta, evaluación, reportes) con todos los servicios de IA apagados: la IA aumenta el flujo, jamás es dependencia del flujo.
- **Borradores, no veredictos:** toda salida de IA hereda íntegramente el Principio V — puntaje de confianza, auditoría visual, corrección manual persistida con precedencia sobre re-inferencias. El texto generado por LLM (resúmenes ejecutivos, narrativas de reporte) DEBE quedar marcado como borrador generado, ser editable antes de emitirse, y ningún reporte puede emitirse con texto generado no revisado por un humano.
- **Reproducibilidad:** todo resultado de IA persiste la identidad y versión del modelo (nombre, versión de pesos, versión de prompt/plantilla cuando aplique), en coherencia con el Principio VII. Cambiar de modelo o de pesos crea resultados nuevos versionados, nunca sobrescribe los anteriores.
- **Núcleo neutro:** los modelos y prompts no incorporan reglas normativas (DS 132, criterios de flota) fijas en código; el conocimiento normativo sigue viviendo exclusivamente en perfiles de evaluación y plantillas versionadas (Principio X). Los modelos operan sobre las entidades genéricas del motor (`Surface`, `Alignment`, `Station`, `CrossSection`).
- **Confidencialidad:** los datos de faena (nubes, ortofotos, métricas) son confidenciales del cliente; la inferencia DEBE ejecutarse en infraestructura controlada por la plataforma (self-hosted) o mediante proveedores con garantías contractuales explícitas de no retención ni entrenamiento con esos datos. Ningún dato de faena se envía a un servicio externo sin esa garantía.

**Justificación:** La IA en esta clase de producto acelera el trabajo del auditor, pero un veredicto de cumplimiento minero es responsabilidad humana y legal; aislar la inferencia protege la testeabilidad del núcleo determinista, y el versionado de modelos preserva la reproducibilidad de reportes históricos.

## Restricciones Técnicas

- **Stack:** Django + GeoDjango + DRF + PostGIS; Celery + Redis; PDAL/GDAL/rasterio/scipy/shapely/scikit-image en los workers; React + TypeScript + Zustand + MapLibre (2D) + Potree (3D) + terra-draw (edición); titiler para tiles dinámicos de COG; WeasyPrint para PDF; almacenamiento de objetos compatible con S3 (MinIO en desarrollo).
- **Los archivos viven en el almacenamiento de objetos, nunca en la base de datos.** PostGIS almacena solo geometrías, métricas, metadatos y referencias a artefactos.
- **Docker multi-arquitectura:** todas las imágenes DEBEN construirse para linux/arm64 y linux/amd64 (`buildx`). El entorno de desarrollo es Apple Silicon; el despliegue puede ser Graviton.
- **Disciplina de CRS:** cada proyecto declara un único CRS de trabajo; todos los datos ingestados se reproyectan en la ingesta. Las particularidades del marco de referencia chileno (épocas de SIRGAS-Chile) se resuelven en la ingesta, nunca aguas abajo.
- **Presupuestos de memoria:** los workers de ingesta DEBEN procesar nubes grandes por tiles/chunks; ninguna etapa del pipeline puede asumir que la nube completa cabe en RAM.
- **Procesamiento fotogramétrico como servicio aislado (módulo futuro):** cuando se incorpore el procesamiento de fotos de dron en plataforma, el motor fotogramétrico (NodeODM u equivalente) DEBE operar como servicio independiente y contenerizado, orquestado por el pipeline de ingesta vía su API REST — nunca embebido en el código de la plataforma. Sus salidas (nube de puntos, ortofoto, DEM) ingresan al mismo pipeline de derivados que cualquier nube subida directamente, sin ruta especial. El soporte de GCPs y de metadatos RTK/PPK en las imágenes es requisito para uso minero. Consideración de licencia: ODM/NodeODM es AGPL-3.0; se usa sin modificaciones como servicio separado comunicado por red, y cualquier modificación a ese componente obliga a publicar sus fuentes — el código propio de la plataforma permanece separado y no queda afectado.
- **Inferencia de IA como servicios aislados (módulos futuros):** los servicios de inferencia (SAM/SAM2, segmentación de nubes, LLMs, modelos predictivos) siguen el mismo patrón que NodeODM: contenedores independientes con API propia, opcionalmente con GPU, escalables por separado y ausentes del `docker compose` mínimo (la plataforma base opera sin ellos). Los pesos de modelos se tratan como artefactos versionados en el almacenamiento de objetos, nunca dentro de imágenes de la plataforma ni en la base de datos. Consideración de licencia por modelo: SAM/SAM2 es Apache-2.0; cualquier modelo o servicio que se incorpore DEBE registrar su licencia y sus restricciones de uso comercial antes de integrarse.

## Flujo de Desarrollo

- Guiado por especificaciones: las funcionalidades siguen `/speckit.specify → clarify → checklist → plan → tasks → analyze → implement`. Toda funcionalidad que toque el núcleo de análisis o el modelo de datos de estaciones DEBE pasar `/speckit.analyze` antes de implementarse.
- Entrega por fases: MVP (ingesta → DEM/COPC, eje manual, pendiente + curvatura horizontal, semaforización, PDF básico) → V2 (secciones transversales, ancho, peralte, detección asistida de bermas con UI de revisión, perfiles de evaluación, reportes por zona) → V3 (extracción automática de eje con edición persistida, importación/exportación DXF, cubicación de acopios y botaderos con comparación multitemporal de DEMs) → V4 (auditoría de bancos, taludes y bermas de contención; distancia de visibilidad en curvas según vehículo de diseño) → V5 (procesamiento fotogramétrico en plataforma: subida de fotos de dron con soporte GCP y RTK/PPK, procesamiento vía NodeODM como servicio aislado, e ingreso automático de los resultados al pipeline de derivados) → V6 (capacidades de IA como servicios aislados: segmentación asistida de ortofotos con SAM/SAM2 para delimitar acopios, botaderos, caminos e infraestructura; segmentación semántica de nubes de puntos para clasificar suelo, vegetación, equipos y muros; IA generativa para borradores de resumen ejecutivo y asistente de consultas sobre datos de estaciones; y predicción de degradación de caminos sobre series multitemporales de DEMs). Ninguna funcionalidad de una fase comienza antes de que el núcleo de análisis de la fase anterior tenga cobertura de tests de verdad conocida.
- Todo PR que toque código de análisis DEBE incluir o actualizar tests de verdad conocida; todo PR que toque la ingesta DEBE validarse contra al menos una muestra LAZ real.
- Infraestructura demo-first: todo DEBE correr localmente con un único `docker compose up`, sin dependencias de nube.

## Gobernanza

Esta constitución prevalece sobre prácticas ad-hoc. Las enmiendas requieren: una justificación documentada, un incremento de versión según versionado semántico (MAYOR: principio eliminado o redefinido; MENOR: principio o sección agregada; PARCHE: aclaración), y propagación a las plantillas dependientes. Todas las revisiones de PR y ejecuciones de `/speckit.analyze` DEBEN verificar el cumplimiento de estos principios; las desviaciones DEBEN justificarse explícitamente en la sección de Seguimiento de Complejidad del plan.

**Versión**: 1.3.0 | **Ratificada**: 2026-07-16 | **Última enmienda**: 2026-07-18
