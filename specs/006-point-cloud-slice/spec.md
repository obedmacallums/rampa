# Feature Specification: Point Cloud Slice

**Feature Branch**: `006-point-cloud-slice`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Slice de nube de puntos: herramienta de inspección visual que corta la nube con una franja de grosor configurable. El usuario traza una polilínea de N vértices sobre la nube de puntos del survey, en vista cenital ortográfica dentro del visor 3D existente. Define un grosor para esa línea (ej. 10 cm) y la herramienta muestra únicamente los puntos de la nube que caen dentro de esa franja, proyectados en un gráfico 2D de distancia acumulada vs cota. Propósito: inspeccionar la geometría 3D real del terreno —taludes, caras verticales, estructura de bermas— que el DEM no representa fielmente. Esta herramienta NO es análisis de caminos ni de bermas; esos módulos vienen después. Incluye medición manual sobre el gráfico, overlay de la cota del DEM sobre los puntos crudos para auditar el raster, exageración vertical ajustable, coloreado por cota/intensidad/clasificación/RGB, y exportación en DXF(2D), DXF(3D), CSV(2D), LAS(3D) y PNG del gráfico. La línea es efímera: no se persiste."

## Context

The platform today offers two ways to look at a survey: a 2D map of the elevation raster and a 3D view of the point cloud. Neither lets a user answer a basic question that precedes any geometric audit — *what does the ground actually look like along this line?*

This matters more than it might appear, because the elevation raster is a lossy view of the terrain. It is produced by averaging every point that falls inside each cell, with no ground filtering. Three consequences follow. Vegetation, equipment and structures are averaged into the ground surface rather than excluded from it. On the face of a slope, where a single cell legitimately contains points spanning several metres of height, the raster reports a single averaged elevation — a height that exists nowhere on the real terrain. And near-vertical faces, barely seen by a nadir flight, produce cells with no points at all, left empty rather than interpolated.

Every downstream analysis the platform intends to build — road grade, berm height, slope auditing — rests on that raster. This feature gives users the means to look at the raw terrain along a line of their choosing and, critically, to see the raster's own claim drawn on top of it. It is the tool by which a user decides whether to trust the surface that everything else depends on.

Scope is deliberately narrow. This is an inspection instrument: a user draws a line, looks, measures by hand if they wish, and exports what they see. It computes no metrics, stores nothing, and has no knowledge of roads, berms, or compliance. Those are separate features that come later and rest on the raster, not on this tool.

### Relationship to Principle I

The project constitution states that all geometric computation must run against the elevation raster and never against the raw point cloud, and that the raw cloud exists for visualisation only. This feature operates entirely within that boundary, and the spec states the position explicitly so it is not left to interpretation:

- The tool **displays** raw points. Display is the role the constitution assigns to the raw cloud.
- Any number the user obtains is produced by a **deliberate manual act** — placing two markers and reading a distance. The system computes nothing on its own initiative.
- No measurement is persisted, and no value derived here feeds the evaluation engine, a compliance status, or a report. Measurements exist only on screen, for the human who took them.
- No automatic detection, classification, or metric extraction runs against the raw points, now or as a hidden extension of this feature.

A future feature that derives stored metrics from raw points would require a constitutional amendment. This one does not.

## Clarifications

### Session 2026-07-20

- Q: At a direction change the band overlaps itself on the inner side and opens a wedge on the outer side, so a point can fall in two segments and be drawn twice at two different distances. How should this be handled? → A: De-duplicate the overlapping points, mark each vertex on the chart with a vertical line, and warn when a turn is sharper than roughly 120°.
- Q: What bounds a full-resolution load, and what happens when a selection exceeds it? → A: Estimate before loading. Below 2 million points, load directly; above that, warn and let the user confirm; above 10 million, refuse and state how much the selection exceeds the limit, asking the user to shorten the line or narrow the band. Never produce a truncated export.
- Q: What default band width should the tool start with, given that point density varies between surveys? → A: Derive it from the cloud's own density — roughly 3× the mean point spacing — bounded by a safety minimum and maximum, rather than using a fixed value.
- Q: SC-004 asked for updates "quick enough to feel continuous", which is not measurable. What is the actual target? → A: While the user drags a control, redraw at reduced detail sustaining at least 30 updates per second; on release, refine to full detail within 1 second.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect the real terrain along a line (Priority: P1)

A user viewing a survey's point cloud wants to see the terrain's true shape along a line they choose — across a haul road, through a berm, down a slope face. They switch to a top-down view, trace a line over the area of interest, and set how wide a band of terrain to include. A chart appears showing every point inside that band, plotted as distance along the line against elevation. They adjust the band width and watch points appear and disappear, which tells them how densely that area was actually surveyed. Because a road two hundred metres long may drop only a few metres, they raise the vertical exaggeration until the shape is legible, with the current factor always displayed so they are never misled about steepness.

**Why this priority**: This is the feature. Every other story adds value on top of a chart that must exist first, and this story alone already answers the question the tool was created for.

**Independent Test**: Load a survey with a point cloud, trace a line across a known feature, and confirm the chart shows terrain geometry consistent with that feature — including detail the elevation raster flattens.

**Acceptance Scenarios**:

1. **Given** a survey whose point cloud is available, **When** the user activates the slice tool, **Then** the view switches to a top-down orthographic projection suitable for tracing.
2. **Given** the slice tool is active, **When** the user places two or more vertices and completes the line, **Then** a chart appears plotting the points within the band as distance along the line against elevation, using a default band width derived from the survey's own point density.
3. **Given** a chart is displayed, **When** the user changes the band width, **Then** the chart updates continuously as the control moves, without requiring a separate confirmation.
4. **Given** a chart is displayed, **When** the user changes the vertical exaggeration, **Then** the chart rescales and the active factor remains visible on screen.
5. **Given** a completed line, **When** the user moves a vertex, **Then** the chart updates to reflect the new geometry.
5a. **Given** a line with more than two vertices, **When** the chart is displayed, **Then** each vertex is marked with a vertical indicator and no point appears more than once.
5b. **Given** the user draws a turn sharper than approximately 120°, **When** the line is completed, **Then** a warning states that the section is distorted at that turn.
6. **Given** a chart is displayed, **When** the user selects a colouring mode, **Then** points are recoloured by the chosen attribute among elevation, intensity, classification, and captured colour.
7. **Given** a chart is displayed, **When** the user navigates along the line using the keyboard, **Then** the visible portion of the chart advances or retreats while the band width is preserved.
8. **Given** a chart is displayed, **When** the user reads the chart header, **Then** the number of points shown and the level of detail currently loaded are both visible.

---

### User Story 2 - Judge whether the elevation surface is trustworthy (Priority: P2)

A user suspects the elevation surface is misrepresenting a feature — a berm that looks too low, a slope that looks too gentle. They trace a line across it and turn on the raster overlay: the surface's own elevation is drawn as a line over the raw points. Where the two agree, the surface is faithful. Where the line floats above the ground, something was averaged into it. Where it cuts through the middle of a vertical face, the surface has collapsed real geometry into a single invented height. Where it is absent, the surface has no data there at all.

**Why this priority**: This is what makes the tool a platform-level instrument rather than a viewer. It is the only way a user can assess the quality of the surface every future analysis depends on, and it is inexpensive because both data sources already exist.

**Independent Test**: Trace a line across a slope face, enable the overlay, and confirm the raster line visibly departs from the raw points where averaging or missing data occurs.

**Acceptance Scenarios**:

1. **Given** a chart is displayed and the survey has an elevation surface, **When** the user enables the overlay, **Then** the surface's elevation along the same line is drawn over the raw points, visually distinct from them.
2. **Given** the overlay is enabled, **When** the line crosses an area where the surface has no data, **Then** the overlay shows a gap there rather than interpolating across it.
3. **Given** a survey that has no elevation surface, **When** the user views the chart, **Then** the overlay control is unavailable and its unavailability is explained.

---

### User Story 3 - Take a measurement by hand (Priority: P3)

Having found the feature they care about, the user wants a number: how tall is this berm, how far apart are these two crests. They place two markers on the chart and read the horizontal distance and the height difference between them. The number is for their own judgement — it is not recorded and does not become part of any assessment the platform makes.

**Why this priority**: A natural and frequent follow-on from looking, but the tool delivers real value without it. Deliberately kept manual and unrecorded, per the position stated above.

**Independent Test**: On a chart of terrain with a known height difference, place two markers and confirm the reported values match the known geometry.

**Acceptance Scenarios**:

1. **Given** a chart is displayed, **When** the user places two measurement markers, **Then** the horizontal distance along the line and the elevation difference between them are both displayed.
2. **Given** a measurement is displayed, **When** the vertical exaggeration is changed, **Then** the reported values are unchanged, because exaggeration affects only the drawing.
3. **Given** measurements are on screen, **When** the user leaves the survey and returns, **Then** no measurement is retained.

---

### User Story 4 - Take the slice into another tool (Priority: P4)

The user wants to continue working elsewhere — bring the section into CAD, analyse the points in a spreadsheet, or attach the chart to a report. Before any export is offered, they load the band at full resolution, because what is on screen is only as complete as the detail level loaded so far. Once loading finishes they export the geometry in a CAD or tabular format, or save the chart as an image with its scale and exaggeration factor rendered into it so the picture cannot misrepresent the slope.

**Why this priority**: Valuable but additive; the tool is useful on its own. Placed last also because it carries the completeness risk that the full-resolution step exists to remove.

**Independent Test**: Trace a line, load at full resolution, export in each format, and confirm each file opens in its target application containing the complete set of points within the band.

**Acceptance Scenarios**:

1. **Given** a chart is displayed at partial detail, **When** the user opens the export options, **Then** data exports are unavailable until a full-resolution load has completed.
2. **Given** the user requests a full-resolution load, **When** loading is in progress, **Then** progress is shown and the user can cancel it.
2a. **Given** a selection estimated between 2 and 10 million points, **When** the user requests a full-resolution load, **Then** the estimate is shown and the load proceeds only after explicit confirmation.
2b. **Given** a selection estimated above 10 million points, **When** the user requests a full-resolution load, **Then** the load is refused and the message states how much the line or band must be reduced.
3. **Given** a full-resolution load has completed, **When** the user exports, **Then** they may choose section coordinates (distance along the line and elevation) or real-world coordinates.
4. **Given** a full-resolution load has completed, **When** the user exports point data, **Then** the file contains every point within the band, not only those previously drawn.
5. **Given** a chart is displayed, **When** the user saves it as an image, **Then** the image includes the scale and the vertical exaggeration factor.
6. **Given** the user cancels a full-resolution load, **When** the cancellation completes, **Then** the chart returns to its previous state and data exports become unavailable again.

---

### Edge Cases

- **The survey has no point cloud.** Products are selectable per survey, so a survey may have an elevation surface and no cloud. The tool must be unavailable in that case, consistent with how the 3D view is already gated, and the reason must be stated rather than left as a missing control.
- **The line has fewer than two vertices, or zero length.** Both vertices placed at the same location produce no meaningful section; the tool must refuse to produce a chart and say why.
- **The band contains no points.** A band narrower than the local point spacing, or one traced over a gap in coverage, yields an empty chart. This must be reported as an empty result with a hint to widen the band — never as a blank panel or an error.
- **The line extends beyond the surveyed area.** Portions outside coverage must appear as gaps rather than being silently dropped or compressed, so distances along the line stay true.
- **A full-resolution load would be very large.** A long line with a wide band can request far more points than the browser can hold. The estimate is shown before loading; between 2 and 10 million points the user must confirm, and above 10 million the load is refused with an explanation of how much the selection must shrink.
- **Access to the cloud expires during a long load.** The 3D view already handles expiring access by refreshing it; a full-resolution load must survive the same event without discarding work already done, or must fail with a clear, recoverable message.
- **The user redraws while a full-resolution load is running.** The in-flight load must be abandoned rather than applied to the new line.
- **Extreme vertical exaggeration.** At high factors the chart can become unreadable and slopes visually alarming. The factor must remain visible at all times and be bounded to a sensible range.
- **The point cloud carries no colour or intensity.** Colouring modes that depend on attributes absent from the data must be unavailable rather than producing an all-black chart.

## Requirements *(mandatory)*

### Functional Requirements

#### Drawing the line

- **FR-001**: The system MUST let a user draw a line of two or more vertices over a survey's point cloud.
- **FR-002**: The system MUST present a top-down orthographic view for drawing, so the line can be placed with plan-view accuracy, and MUST let the user return to the previous view afterwards.
- **FR-003**: Users MUST be able to move, add, and remove vertices after the line is drawn, with the chart updating to match.
- **FR-004**: The system MUST make the tool unavailable, with a stated reason, for surveys that have no point cloud.
- **FR-005**: The system MUST discard the line and everything derived from it when the user leaves the survey; nothing is persisted.
- **FR-006**: The system MUST represent each point at most once in the chart, de-duplicating points that fall inside the overlap the band creates on the inner side of a direction change.
- **FR-006a**: The system MUST mark each vertex on the chart with a vertical indicator, so the user can see where the line changes direction and judge the reading accordingly.
- **FR-006b**: The system MUST warn the user when a turn is sharper than approximately 120°, where the band's self-overlap and outer wedge distort the section most severely.

#### The chart

- **FR-007**: The system MUST display the points within the band as a two-dimensional chart of distance along the line against elevation.
- **FR-008**: Users MUST be able to change the band width, with the chart updating as the control is moved rather than on confirmation.
- **FR-008a**: The system MUST redraw at reduced detail while a control is being dragged and refine to full detail once it is released, so responsiveness during the drag never comes at the cost of the fidelity of the settled result.
- **FR-009**: The system MUST derive the default band width from the survey's own point density — approximately 3× the mean point spacing — so the first chart a user sees contains enough points to be legible on dense and sparse surveys alike.
- **FR-009a**: The system MUST bound that derived default between 5 cm and 2 m, so an unusual density estimate cannot produce a band that is uselessly thin or one that blurs the geometry the tool exists to reveal.
- **FR-010**: Users MUST be able to change the vertical exaggeration, and the system MUST keep the active factor visible whenever the chart is shown.
- **FR-011**: Users MUST be able to colour points by elevation, intensity, classification, or captured colour, and the system MUST offer only the modes the data supports.
- **FR-012**: The system MUST display both the number of points shown and the level of detail currently loaded, so the user can tell that what is drawn is not necessarily everything present.
- **FR-013**: Users MUST be able to move the visible portion of the chart along the line using the keyboard, preserving the band width.
- **FR-014**: The system MUST report an empty band as an empty result with guidance, and MUST show terrain gaps as gaps rather than closing over them.

#### Auditing the elevation surface

- **FR-015**: Users MUST be able to overlay the elevation surface's own elevation along the same line, drawn over the raw points and visually distinct from them.
- **FR-016**: The system MUST show gaps in the overlay wherever the surface has no data, rather than interpolating across them.
- **FR-017**: The system MUST make the overlay unavailable, with a stated reason, for surveys that have no elevation surface.

#### Measuring

- **FR-018**: Users MUST be able to place two markers on the chart and read the horizontal distance and elevation difference between them.
- **FR-019**: The system MUST report measurements in true terrain units regardless of the vertical exaggeration in effect.
- **FR-020**: The system MUST NOT persist measurements, and MUST NOT let any measured value feed a stored result, an assessment, or a report.

#### Exporting

- **FR-021**: The system MUST offer an explicit full-resolution load of the band, showing progress and allowing cancellation.
- **FR-022**: The system MUST keep data exports unavailable until a full-resolution load has completed, so no user can export a partial band believing it complete.
- **FR-023**: The system MUST estimate the number of points a full-resolution load would produce, and show that estimate to the user, before starting the load.
- **FR-023a**: The system MUST load without prompting when the estimate is below 2 million points; MUST warn and require confirmation between 2 and 10 million; and MUST refuse above 10 million, stating how far the selection exceeds the limit and asking the user to shorten the line or narrow the band.
- **FR-023b**: The system MUST NEVER produce a truncated data export. When a selection cannot be loaded in full, the outcome is a refusal to load, not a partial file.
- **FR-024**: Users MUST be able to export the slice geometry in a CAD interchange format and in a tabular format, in both section coordinates (distance along the line and elevation) and real-world coordinates.
- **FR-025**: Users MUST be able to export the points as a point cloud file in real-world coordinates.
- **FR-026**: Exported point data MUST contain every point within the band, not only the points previously drawn on screen.
- **FR-027**: Users MUST be able to save the chart as an image with the scale and the vertical exaggeration factor rendered into it.
- **FR-028**: The system MUST abandon an in-flight full-resolution load if the user redraws or edits the line.

#### Presentation

- **FR-029**: All interface text MUST be available in Spanish and English, consistent with the rest of the platform.
- **FR-030**: The tool MUST follow the platform's existing visual design, so it does not read as a separate application embedded in the product.

### Key Entities

This feature stores nothing. The concepts below exist only within a working session.

- **Slice line**: the ordered vertices the user traced, together with the band width. Discarded on leaving the survey.
- **Slice result**: the points falling within the band, each with its distance along the line, its elevation, and the attributes available for colouring. Recomputed whenever the line or width changes.
- **Measurement**: a pair of markers the user placed on the chart and the distance and elevation difference between them. Never stored, never consumed by anything else.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who has not seen the tool before can produce a usable section — line drawn, width and exaggeration adjusted to legibility — within 2 minutes and without consulting documentation.
- **SC-002**: The chart reveals terrain structure the elevation surface does not represent: on a slope face where the surface reports a single averaged height, the section shows the spread of real elevations at that location.
- **SC-003**: With the overlay enabled, a user can point to where the elevation surface departs from the raw terrain and say whether the departure is averaging, missing data, or agreement.
- **SC-004**: While a user drags the band width or vertical exaggeration control, the chart redraws at a sustained rate of at least 30 updates per second, so a legible setting can be found by sweeping the control rather than by trial and confirmation.
- **SC-004a**: Within 1 second of releasing the control, the chart has refined to the full detail available, so the reduced-detail drawing shown during the drag is never mistaken for the final result.
- **SC-005**: Every exported data file contains 100% of the points within the band; no export path can produce a partial file without the user having been told.
- **SC-006**: A measurement taken on terrain of known geometry matches that geometry within the survey's own accuracy, at every vertical exaggeration setting.
- **SC-007**: Exported files open without repair in their target applications: CAD files in a CAD application, tabular files in a spreadsheet, point cloud files in a point cloud application.
- **SC-008**: The entire interface is complete in both Spanish and English, with no untranslated text in either.
- **SC-009**: No value produced by this tool appears in any stored record, assessment, or report anywhere in the platform.

## Assumptions

- **The tool sits inside the existing 3D point cloud view**, not as a separate page. The user is already looking at the cloud when they decide to slice it.
- **Drawing happens in the same coordinate space as the point cloud**, avoiding any conversion between the map view's coordinates and the survey's working coordinate system, which would be a source of positional error.
- **Only one slice line exists at a time.** Drawing a new one replaces the previous. Comparing two sections side by side is not part of this feature.
- **The band is vertical and unbounded in height**: it includes every point within the horizontal distance from the line, at any elevation. Limiting the slice by height is not part of this feature.
- **The chart's own interface is built to the platform's design system** rather than adopting the visual language of the underlying viewing component, so the tool is consistent with the rest of the product and translatable.
- **Point extraction reuses the existing point cloud viewing capability.** No new server-side processing, no new stored data, and no new API endpoints are introduced; the feature is entirely client-side.
- **What is displayed depends on how much detail has been loaded.** The viewing component streams progressively, so the visible point count grows as detail loads. This is why the full-resolution step exists before export, and why the loaded detail level is shown alongside the point count.
- **Measurement is a reading aid, not an analysis capability**, per the position stated in Context.
- **Access to the tool follows the survey's existing access rules.** No new permissions are introduced.

## Dependencies

- A survey must have a **point cloud product** for the tool to be available. Since products are selectable per survey, this cannot be assumed present.
- The **elevation surface product** is required for the overlay only. Its absence disables that one capability, not the tool.
- The **existing 3D viewing capability** provides the point extraction, the top-down orthographic view, and the export formats. Making its export capability usable from a custom interface is a prerequisite of this feature.

## Out of Scope

- Persisting slice lines, band widths, or measurements
- Any automatically computed metric derived from raw points
- Road, berm, slope, or compliance analysis of any kind
- Multiple simultaneous slices or side-by-side comparison
- Slices taken from the elevation surface rather than the point cloud
- Comparing slices across surveys or across time
- Height-bounded slices or arbitrary clipping volumes
- Drawing the line from the 2D map view
