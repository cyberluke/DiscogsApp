/**
 * dither-frames.mjs
 * -----------------
 * Converts extracted video frames into an authentic 1-bit Floyd–Steinberg
 * dithered OEL sprite sheet.
 *
 * Pipeline per frame:
 *   1. Load PNG → grayscale luminance
 *   2. Auto-contrast stretch (normalize to full 0–255 range)
 *   3. Crop to tight bounding box (threshold ~20)
 *   4. Resize to target height (bilinear, preserving aspect ratio)
 *   5. Floyd–Steinberg 1-bit dither with a slight edge bias
 *   6. Output as alpha-masked PNG (on = phosphor, off = transparent)
 *
 * Then assembles all frames into a horizontal sprite sheet + a JSON manifest.
 *
 * Usage:
 *   node scripts/dither-frames.mjs [--height=64] [--threshold=25]
 */
import fs from 'node:fs';
import path from 'node:path';
import { PNG } from 'pngjs';

function getArg(name, fallback) {
  const prefix = `--${name}=`;
  const hit = process.argv.find((a) => a.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : fallback;
}

const FRAMES_DIR = 'src/assets/dolphin-frames';
const OUT_DIR = 'src/assets/dolphin-dithered';
const TARGET_HEIGHT = parseInt(getArg('height', '64'), 10);
const THRESHOLD = parseInt(getArg('threshold', '25'), 10);
// White pixels — the renderer tints with the theme's phosphor color at runtime.
const PHOSPHOR = { r: 255, g: 255, b: 255 };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function loadPng(filePath) {
  const buf = fs.readFileSync(filePath);
  return PNG.sync.read(buf);
}

function savePng(filePath, png) {
  const buf = PNG.sync.write(png);
  fs.writeFileSync(filePath, buf);
}

/** Convert RGBA → grayscale luminance array. */
function toGrayscale(png) {
  const { width, height, data } = png;
  const gray = new Float32Array(width * height);
  for (let i = 0; i < width * height; i++) {
    const r = data[i * 4];
    const g = data[i * 4 + 1];
    const b = data[i * 4 + 2];
    gray[i] = 0.299 * r + 0.587 * g + 0.114 * b;
  }
  return gray;
}

/** Auto-contrast: stretch to full 0–255 range. */
function autoContrast(gray) {
  let min = 255, max = 0;
  for (const v of gray) {
    if (v < min) min = v;
    if (v > max) max = v;
  }
  const range = max - min || 1;
  for (let i = 0; i < gray.length; i++) {
    gray[i] = ((gray[i] - min) / range) * 255;
  }
  return gray;
}

/** Find tight bounding box of non-background pixels. */
function boundingBox(gray, width, height, threshold) {
  let minX = width, minY = height, maxX = 0, maxY = 0;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (gray[y * width + x] > threshold) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  if (maxX < minX || maxY < minY) return null; // empty frame
  return { minX, minY, maxX, maxY, w: maxX - minX + 1, h: maxY - minY + 1 };
}

/** Crop grayscale to bounding box. */
function crop(gray, width, box) {
  const out = new Float32Array(box.w * box.h);
  for (let y = 0; y < box.h; y++) {
    for (let x = 0; x < box.w; x++) {
      out[y * box.w + x] = gray[(box.minY + y) * width + (box.minX + x)];
    }
  }
  return out;
}

/** Bilinear resize grayscale to target height, preserving aspect ratio. */
function resize(gray, srcW, srcH, targetH) {
  const targetW = Math.round((srcW / srcH) * targetH);
  const out = new Float32Array(targetW * targetH);
  for (let y = 0; y < targetH; y++) {
    const sy = (y / targetH) * srcH;
    const y0 = Math.floor(sy);
    const y1 = Math.min(y0 + 1, srcH - 1);
    const fy = sy - y0;
    for (let x = 0; x < targetW; x++) {
      const sx = (x / targetW) * srcW;
      const x0 = Math.floor(sx);
      const x1 = Math.min(x0 + 1, srcW - 1);
      const fx = sx - x0;
      const v =
        gray[y0 * srcW + x0] * (1 - fx) * (1 - fy) +
        gray[y0 * srcW + x1] * fx * (1 - fy) +
        gray[y1 * srcW + x0] * (1 - fx) * fy +
        gray[y1 * srcW + x1] * fx * fy;
      out[y * targetW + x] = v;
    }
  }
  return { data: out, width: targetW, height: targetH };
}

/**
 * Volumetric 1-bit dither: solid body core + dithered shading gradients.
 *
 * Three bands:
 *   - Luminance > solidThreshold  → solid ON (body core, reads as filled)
 *   - Luminance in [ditherLow, solidThreshold] → Floyd–Steinberg dither
 *   - Luminance < ditherLow       → OFF (background / deep shadow)
 *
 * This produces a dense, "lit phosphor" look: the body is mostly filled,
 * with dithering only at edges and in volumetric shading gradients — exactly
 * like a real monochrome OEL panel rendering a 3D-shaded sprite.
 */
function volumetricDither(gray, width, height, opts = {}) {
  const solidThreshold = opts.solidThreshold ?? 140;
  const ditherLow = opts.ditherLow ?? 45;
  const bias = opts.bias ?? 12;

  const buf = Float32Array.from(gray);
  const out = new Uint8Array(width * height);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = y * width + x;
      const v = buf[i];

      if (v >= solidThreshold) {
        // Solid body core — fully ON.
        out[i] = 1;
        // No error to diffuse from a clamped pixel.
        continue;
      }
      if (v < ditherLow) {
        // Deep shadow / background — fully OFF.
        out[i] = 0;
        const err = v; // small positive error bleeds into neighbours
        if (x + 1 < width) buf[i + 1] += (err * 7) / 16;
        if (y + 1 < height) {
          if (x > 0) buf[i + width - 1] += (err * 3) / 16;
          buf[i + width] += (err * 5) / 16;
          if (x + 1 < width) buf[i + width + 1] += (err * 1) / 16;
        }
        continue;
      }

      // Shading gradient zone — Floyd–Steinberg dither.
      const newVal = v + bias > 127 ? 255 : 0;
      out[i] = newVal === 255 ? 1 : 0;
      const err = v - newVal;
      if (x + 1 < width) buf[i + 1] += (err * 7) / 16;
      if (y + 1 < height) {
        if (x > 0) buf[i + width - 1] += (err * 3) / 16;
        buf[i + width] += (err * 5) / 16;
        if (x + 1 < width) buf[i + width + 1] += (err * 1) / 16;
      }
    }
  }
  return out;
}

/**
 * Top-lit volumetric shading (counter-shading) + dorsal rim light.
 *
 * The reference Pioneer OEL dolphin is lit from above: a bright specular rim
 * traces the dorsal contour, the upper body is a dense lit fill, and the belly
 * falls off to a solid black crescent. This models a rounded, lit cylinder
 * rather than a flat dithered blob.
 *
 * For each object pixel we compute its depth within the local body column
 * (0 = dorsal/top, 1 = ventral/bottom) and remap luminance:
 *   - depth < rimDepth  → forced to 255 (continuous bright rim along the back)
 *   - otherwise         → luminance scaled by a top-bright → bottom-dark curve
 */
function applyTopLighting(gray, objectMask, width, height, opts = {}) {
  const topBoost = opts.topBoost ?? 1.6;
  const bottomCut = opts.bottomCut ?? 0.1;
  const rimDepth = opts.rimDepth ?? 0.15;

  // Per-column dorsal (top) and ventral (bottom) extent of the object.
  const topY = new Int32Array(width).fill(height);
  const bottomY = new Int32Array(width).fill(-1);
  for (let x = 0; x < width; x++) {
    for (let y = 0; y < height; y++) {
      if (objectMask[y * width + x]) {
        if (y < topY[x]) topY[x] = y;
        if (y > bottomY[x]) bottomY[x] = y;
      }
    }
  }

  const out = Float32Array.from(gray);
  for (let x = 0; x < width; x++) {
    if (bottomY[x] < 0) continue; // empty column
    const span = Math.max(1, bottomY[x] - topY[x]);
    for (let y = topY[x]; y <= bottomY[x]; y++) {
      const i = y * width + x;
      if (!objectMask[i]) continue;
      const depth = (y - topY[x]) / span; // 0 = dorsal, 1 = ventral
      // Continuous specular rim along the dorsal contour.
      if (depth < rimDepth) {
        out[i] = 255;
        continue;
      }
      // Counter-shading: bright back → dark belly.
      const mult = topBoost - (topBoost - bottomCut) * depth;
      out[i] = Math.min(255, gray[i] * mult);
    }
  }
  return out;
}

/**
 * Add a continuous bright rim along the silhouette edge.
 *
 * The reference Pioneer OEL dolphin has a 1–2 px specular rim tracing the
 * entire contour. In a 1-bit image this means a continuous band of edge
 * pixels is solid ON (no dither gaps) while the interior keeps its shading.
 *
 * We erode the object mask by `rimWidth`; the rim is the set difference
 * (objectMask − eroded), i.e. a continuous band along the inside edge. Those
 * pixels are forced solid ON in the dithered mask, producing a crisp outline.
 */
function addRimLight(mask, objectMask, width, height, rimWidth = 1) {
  // Erode the object mask by rimWidth (8-connected).
  let eroded = Uint8Array.from(objectMask);
  for (let pass = 0; pass < rimWidth; pass++) {
    const src = Uint8Array.from(eroded);
    const next = new Uint8Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const i = y * width + x;
        if (!src[i]) continue;
        let allOn = true;
        for (let dy = -1; dy <= 1 && allOn; dy++) {
          for (let dx = -1; dx <= 1 && allOn; dx++) {
            const nx = x + dx, ny = y + dy;
            if (nx < 0 || nx >= width || ny < 0 || ny >= height || !src[ny * width + nx]) {
              allOn = false;
            }
          }
        }
        next[i] = allOn ? 1 : 0;
      }
    }
    eroded = next;
  }
  // Rim = objectMask AND NOT eroded → continuous inside-edge band.
  const out = Uint8Array.from(mask);
  for (let i = 0; i < width * height; i++) {
    if (objectMask[i] && !eroded[i]) out[i] = 1;
  }
  return out;
}

/**
 * 3×3 Gaussian blur on grayscale data. Gently smooths video compression
 * artifacts and noise before dithering, without losing silhouette detail.
 */
function gaussianBlur(gray, width, height) {
  const out = new Float32Array(width * height);
  const k = [1, 2, 1, 2, 4, 2, 1, 2, 1]; // 3×3 Gaussian kernel (sum=16)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let sum = 0;
      let ki = 0;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const nx = Math.min(Math.max(x + dx, 0), width - 1);
          const ny = Math.min(Math.max(y + dy, 0), height - 1);
          sum += gray[ny * width + nx] * k[ki++];
        }
      }
      out[y * width + x] = sum / 16;
    }
  }
  return out;
}

/**
 * Dilate a binary mask by 1 pixel (8-connected). Expands the object mask
 * slightly so soft edges are included in the dither zone.
 */
function dilateMask(mask, width, height) {
  const out = Uint8Array.from(mask);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (mask[y * width + x]) continue;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const nx = x + dx, ny = y + dy;
          if (nx >= 0 && nx < width && ny >= 0 && ny < height && mask[ny * width + nx]) {
            out[y * width + x] = 1;
            dy = 2; // break outer
            break;
          }
        }
      }
    }
  }
  return out;
}

/**
 * Volumetric 1-bit dither constrained to a binary object mask.
 * Pixels outside the mask are always OFF. Inside the mask, three bands apply:
 *   - Luminance > solidThreshold  → solid ON
 *   - Luminance in [ditherLow, solidThreshold] → Floyd–Steinberg dither
 *   - Luminance < ditherLow       → OFF
 */
function volumetricDitherMasked(gray, objectMask, width, height, opts = {}) {
  const solidThreshold = opts.solidThreshold ?? 90;
  const ditherLow = opts.ditherLow ?? 35;
  const bias = opts.bias ?? 14;

  const buf = Float32Array.from(gray);
  const out = new Uint8Array(width * height);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = y * width + x;
      if (!objectMask[i]) {
        out[i] = 0;
        continue;
      }
      const v = buf[i];
      if (v >= solidThreshold) {
        out[i] = 1;
        continue;
      }
      if (v < ditherLow) {
        out[i] = 0;
        const err = v;
        if (x + 1 < width && objectMask[i + 1]) buf[i + 1] += (err * 7) / 16;
        if (y + 1 < height) {
          if (x > 0 && objectMask[i + width - 1]) buf[i + width - 1] += (err * 3) / 16;
          if (objectMask[i + width]) buf[i + width] += (err * 5) / 16;
          if (x + 1 < width && objectMask[i + width + 1]) buf[i + width + 1] += (err * 1) / 16;
        }
        continue;
      }
      const newVal = v + bias > 127 ? 255 : 0;
      out[i] = newVal === 255 ? 1 : 0;
      const err = v - newVal;
      if (x + 1 < width && objectMask[i + 1]) buf[i + 1] += (err * 7) / 16;
      if (y + 1 < height) {
        if (x > 0 && objectMask[i + width - 1]) buf[i + width - 1] += (err * 3) / 16;
        if (objectMask[i + width]) buf[i + width] += (err * 5) / 16;
        if (x + 1 < width && objectMask[i + width + 1]) buf[i + width + 1] += (err * 1) / 16;
      }
    }
  }
  return out;
}

/**
 * Remove isolated ON pixels: any ON pixel with fewer than `minNeighbors`
 * ON neighbours (8-connected) is turned OFF. Cleans up scatter noise from
 * the video background that survives auto-contrast + dithering.
 */
function removeIsolated(mask, width, height, minNeighbors = 2) {
  const out = Uint8Array.from(mask);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = y * width + x;
      if (!mask[i]) continue;
      let count = 0;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if (dx === 0 && dy === 0) continue;
          const nx = x + dx, ny = y + dy;
          if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
            count += mask[ny * width + nx];
          }
        }
      }
      if (count < minNeighbors) out[i] = 0;
    }
  }
  return out;
}

/** Convert a 1-bit mask to an alpha-masked phosphor PNG. */
function maskToPng(mask, width, height) {
  const png = new PNG({ width, height });
  for (let i = 0; i < width * height; i++) {
    png.data[i * 4] = PHOSPHOR.r;
    png.data[i * 4 + 1] = PHOSPHOR.g;
    png.data[i * 4 + 2] = PHOSPHOR.b;
    png.data[i * 4 + 3] = mask[i] ? 255 : 0;
  }
  return png;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  if (!fs.existsSync(FRAMES_DIR)) {
    console.error(`❌ Frames directory not found: ${FRAMES_DIR}`);
    console.error('   Run generate-dolphin-video.mjs first.');
    process.exit(1);
  }

  const frameFiles = fs
    .readdirSync(FRAMES_DIR)
    .filter((f) => f.endsWith('.png'))
    .sort();

  if (frameFiles.length === 0) {
    console.error(`❌ No PNG frames in ${FRAMES_DIR}`);
    process.exit(1);
  }

  console.log(`🐬 Dithering ${frameFiles.length} frames → ${TARGET_HEIGHT}px height\n`);
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const processed = [];
  let maxW = 0;

  for (const file of frameFiles) {
    const png = loadPng(path.join(FRAMES_DIR, file));
    let gray = toGrayscale(png);
    gray = autoContrast(gray);

    const box = boundingBox(gray, png.width, png.height, 45);
    if (!box) {
      console.log(`   ⏭️  ${file}: empty frame, skipping`);
      continue;
    }

    const cropped = crop(gray, png.width, box);
    const resized = resize(cropped, box.w, box.h, TARGET_HEIGHT);
    // Gentle 3×3 smoothing to tame video compression noise without losing detail.
    const blurred = gaussianBlur(resized.data, resized.width, resized.height);

    // Volumetric dither: solid body core + dithered shading at the edges.
    // This is the proven best config (scored 6.8): solid core + dithered edges.
    let mask = volumetricDither(blurred, resized.width, resized.height, {
      solidThreshold: 95,
      ditherLow: 25,
      bias: 16
    });
    // Morphological cleanup: remove isolated ON pixels (spray noise).
    // minNeighbors=3 keeps the body dense while killing stray scatter.
    mask = removeIsolated(mask, resized.width, resized.height, 3);
    const outPng = maskToPng(mask, resized.width, resized.height);

    const outName = file.replace('.png', '.dither.png');
    savePng(path.join(OUT_DIR, outName), outPng);
    processed.push({ file: outName, width: resized.width, height: resized.height });
    maxW = Math.max(maxW, resized.width);
    console.log(`   ✅ ${file} → ${outName} (${resized.width}×${resized.height})`);
  }

  if (processed.length === 0) {
    console.error('❌ No frames processed.');
    process.exit(1);
  }

  // Build a GRID sprite sheet (cols × rows) to stay within GPU texture limits.
  const COLS = 8;
  const rows = Math.ceil(processed.length / COLS);
  const sheetW = maxW * COLS;
  const sheetH = TARGET_HEIGHT * rows;
  const sheet = new PNG({ width: sheetW, height: sheetH });

  for (let f = 0; f < processed.length; f++) {
    const framePng = loadPng(path.join(OUT_DIR, processed[f].file));
    const col = f % COLS;
    const row = Math.floor(f / COLS);
    const offsetX = col * maxW;
    const offsetY = row * TARGET_HEIGHT;
    for (let y = 0; y < framePng.height; y++) {
      for (let x = 0; x < framePng.width; x++) {
        const si = ((offsetY + y) * sheetW + offsetX + x) * 4;
        const fi = (y * framePng.width + x) * 4;
        sheet.data[si] = framePng.data[fi];
        sheet.data[si + 1] = framePng.data[fi + 1];
        sheet.data[si + 2] = framePng.data[fi + 2];
        sheet.data[si + 3] = framePng.data[fi + 3];
      }
    }
  }

  savePng(path.join(OUT_DIR, 'sprite-sheet.png'), sheet);

  // Write manifest for the renderer.
  const manifest = {
    frameWidth: maxW,
    frameHeight: TARGET_HEIGHT,
    frameCount: processed.length,
    cols: COLS,
    rows,
    fps: 12,
    phosphor: PHOSPHOR,
    frames: processed
  };
  fs.writeFileSync(
    path.join(OUT_DIR, 'manifest.json'),
    JSON.stringify(manifest, null, 2)
  );

  console.log(`\n✅ Sprite sheet: ${OUT_DIR}/sprite-sheet.png (${sheetW}×${sheetH})`);
  console.log(`   ${processed.length} frames in ${COLS}×${rows} grid, each ${maxW}×${TARGET_HEIGHT}px`);
  console.log(`   Manifest: ${OUT_DIR}/manifest.json`);
}

main();
