**TECHNICAL SPECIFICATION — DOLPHIN SPRITE (Pioneer OEL panel, monochrome phosphor, 1‑bit/pixel, perceived grays via spatial dither). Coordinate convention: origin (0,0) = top‑left; X = % of frame width, Y = % of frame height. All values ±2%. Photo cyan tint = panel emission color, not a separate channel.**

---

### 1. POSE & ORIENTATION
- **Action:** mid‑leap arc (not horizontal swim, not dive). The body is a single **convex‑up parabola / inverted‑U**, i.e. arched, not straight.
- **Heading:** rostrum (nose) points to the **RIGHT and downward** (vector ≈ +X, +Y, ~25° below horizontal).
- **Tail:** at the **LEFT**, trailing **down‑left** (vector ≈ −X, +Y, ~30° below horizontal).
- **Curve geometry:** dorsal (back) contour is a smooth convex spline passing through tail‑peduncle (17, 53) → back‑apex (≈45, 6) → melon‑top (82, 28) → rostrum‑tip (94, 72). Apex of the arch sits **left of centre** (≈ X45–49), coincident with the dorsal fin. Ventral (belly) contour is a shallower concentric arch through (17, 56) → (40, 33) → (75, 52). The gap between the two arches = body thickness: **max ≈ 27 % of frame height at mid‑body**, tapering to ≈ 0 % at both the tail peduncle and the beak. Net read: head and tail both dipping toward the bottom corners while the back humps at the top = classic leap silhouette.

### 2. PROPORTIONS & PLACEMENT
- **Bounding box:** X 2 %→94 % (**≈ 92 % of width**); Y 1 %→73 % (**≈ 72 % of height**).
- **Centroid of lit mass:** ≈ (48 %, 30 %) → horizontally centred, vertically **upper‑middle**. The lower ~25 % of the frame is empty black (reserved for the bottom text line).
- The sprite therefore dominates the panel; it is not a small icon.

### 3. DITHERING & SHADING
- Panel is **binary (on/off)**; every gray is spatial dither. **≥ 4 perceived levels** are used:
  1. **100 % solid runs** (specular highlights / rim) — pure white‑cyan.
  2. **High‑density field ≈ 75–85 % on‑pixels** (the light‑blue dorsal fill) — fine high‑frequency pattern that photographs as flat light‑blue.
  3. **Mid‑tone ≈ 40–55 % on‑pixels** rendered as **irregular, worm‑like / clustered dark patches on a light field** → characteristic of **error‑diffusion (Floyd–Steinberg‑type) dither**, NOT a regular Bayer/ordered matrix (no visible grid, no checkerboard banding).
  4. **0 % (black)** — belly shadow + background.
- **Vertical shade stack at mid‑body (top→bottom):** 1–2 px white rim (Y≈6 %) → light‑blue fill (Y≈8–17 %) → irregular dark‑cluster flank band (Y≈18–32 %) → solid black belly crescent (Y≈33–50 %) → 1 px bright ventral highlight line (Y≈46–50 %) → black.
- **Brightest zones:** dorsal rim line, dorsal‑fin leading edge, the **pectoral fin (largest solid white blob)**, the rostrum tip, and the thin ventral highlight line.
- **Darkest zones:** the thick **ventral black crescent** (counter‑shade / underside shadow), the interior of the tail fluke, the mouth groove.
- **Rim/outline:** YES — a continuous **1–2 px bright rim** traces the entire dorsal convex contour from tail peduncle to melon; the ventral contour has only a partial bright line (around the pectoral fin and belly). The tail fluke is **rim‑only** (interior black).
- **Interior:** neither fully solid nor fully hollow — it is a **gradient‑dithered top half + hollow black bottom half** (crescent).

### 4. ANATOMY (detail level per part)
- **Dorsal fin:** apex (49, 1); leading base (44, 8); trailing base (56, 9). Stubby **falcate/triangular block**, ~12 % W × ~8 % H, bright leading edge + dithered fill. Low‑medium detail (stepped pixels visible on the slope).
- **Tail fluke (left):** rendered as **two thin bright arcs, interior black** (wireframe look). Upper lobe: peduncle (17, 53) curving to tip (2, 73). Lower lobe: faint broken hook of scattered pixels ending ≈ (13, 85). Least detailed part — outline only, 1–2 px stroke.
- **Pectoral fin (near):** the **brightest solid mass**, a rounded trapezoid/blob from front corner (49, 47) to rear tip (66, 56), ≈ 17 % W × 13 % H, angled aft‑down. A thin bright line extends left from it along the belly to (30, 41) (far fin / belly edge) and right toward the head to ≈ (80, 64).
- **Rostrum / beak (right):** distinct pointed beak, bright outline + dithered fill, from mouth notch (80, 60) to tip (94, 72); separated from the melon by a **dark mouth groove** (1‑px dark line).
- **Melon / head:** bulbous rounded right cap, X≈73–92 %, Y≈28–60 %; smooth bright rim on the upper‑right quadrant.
- **Eye:** a single isolated bright pixel ≈ (79, 52) at the lower head — minimal but present.

### 5. SURROUNDINGS
- **No water, no splash, no waves, no horizon.** Background is uniform 0 % black.
- A few isolated stray on‑pixels (panel noise / "stars"), e.g. ≈ (91, 22) and a couple near the left edge — not part of the sprite.
- **Text overlays (separate UI layer, segmented/dot‑matrix font, white):** top‑right ≈ "128.9" + unit glyph (FM frequency); bottom‑right ≈ "128 ‹glyphs› 50" (track/time). These sit in the corners and do **not** overlap the dolphin's lit body.

### 6. WHY IT READS AS ORGANIC (not a flat CAD blob)
1. **Volumetric shading:** the 3‑band vertical gradient (rim → light fill → dithered flank → black belly) models a rounded, lit cylinder; the dark ventral crescent alone supplies the illusion of a 3‑D underside in shadow (counter‑shading).
2. **Specular rim light:** the continuous 1–2 px bright dorsal edge mimics wet specular highlight and separates the form from the black field.
3. **Dynamic asymmetry:** head and tail both pitched downward against a high central arch = kinetic leap, not a static profile; the off‑centre solid pectoral blob breaks bilateral symmetry.
4. **Tapered extremities:** beak and flukes narrow to 1–2 px points, giving silhouette grace that a blocky fill could not.
5. **Noise‑type (error‑diffusion) dither:** the irregular clustered mid‑tone avoids the mechanical cross‑hatch / banding of ordered dither, so the flank looks like soft curved shading rather than a flat patterned fill.
6. **Anatomical landmarks at correct ratios** (small dorsal fin at the apex, large rounded melon, short pointed beak, single swept pectoral) let the eye parse it instantly as a dolphin despite the low resolution.

**Landmark table for pixel reconstruction (X %, Y %):**
Dorsal apex (49,1) · Dorsal lead base (44,8) · Dorsal trail base (56,9) · Back apex (45,6) · Tail peduncle (17,53) · Fluke upper tip (2,73) · Fluke lower tip (13,85) · Melon top (82,28) · Mouth notch (80,60) · Rostrum tip (94,72) · Pectoral front (49,47) · Pectoral rear (66,56) · Belly‑line left (30,41) · Eye (79,52).

Connect dorsal landmarks with a convex quadratic/Bezier for the back, a concentric shallower curve for the belly, fill the enclosed top band with the 3‑level dither stack above, leave the belly crescent black, then stamp the solid pectoral blob and the rim‑only fluke arcs.