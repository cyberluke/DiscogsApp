/**
 * analyze-reference.mjs
 * ---------------------
 * Sends a reference image (the Pioneer OEL dolphin the user likes) to Qwen-VL
 * and asks for a precise, buildable description of the dolphin sprite:
 * pose, orientation, proportions, dithering/shading style, and surrounding
 * elements (water, splash). The output drives the dithered-sprite renderer.
 *
 * Usage:
 *   node scripts/analyze-reference.mjs --image="<path>" --key="<DASHSCOPE_KEY>"
 */
import fs from 'node:fs';
import path from 'node:path';

function getArg(name, fallback) {
  const prefix = `--${name}=`;
  const hit = process.argv.find((a) => a.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : fallback;
}

const API_URL =
  'https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions';
const MODEL = 'qwen3.8-max-preview';
const IMAGE_PATH = getArg('image', 'C:\\Users\\lukes.COREI9\\Downloads\\Screenshot 2026-07-22 035001.png');
const API_KEY = process.env.DASHSCOPE_API_KEY || getArg('key', '');

if (!API_KEY) {
  console.error('❌ Missing API key. Pass --key="..." or set DASHSCOPE_API_KEY.');
  process.exit(1);
}
if (!fs.existsSync(IMAGE_PATH)) {
  console.error(`❌ Image not found: ${IMAGE_PATH}`);
  process.exit(1);
}

const PROMPT = `You are analyzing a screenshot of a Pioneer Organic EL (OEL) car head-unit display from the late 1990s. It shows an animated dolphin rendered as a DITHERED pixel sprite on a monochrome phosphor panel.

Describe the dolphin sprite with extreme precision so an engineer can recreate it pixel-by-pixel. Cover:

1. POSE & ORIENTATION: Is it leaping/arcing, swimming horizontally, or diving? Which direction does the nose point (left/right/up)? Where is the tail? Is the body curved (arched) or straight? Describe the exact body curve.
2. PROPORTIONS: Roughly what fraction of the display width and height does the dolphin occupy? Where is it positioned (center, upper, lower)?
3. DITHERING & SHADING: How is shading achieved? Is it 1-bit dithering (on/off pixels only) or multi-level? Describe the dither pattern (dense dots, checkerboard, Bayer-like). Which parts are brightest (edges? back? top?) and which are darkest (belly? interior?)? Is there a bright rim/outline? Is the interior solid, hollow, or gradient-dithered?
4. ANATOMY: Describe the dorsal fin, tail fluke (shape, spread), pectoral fin, rostrum/beak, melon/head. How detailed is each?
5. SURROUNDINGS: Is there water, a splash, waves below/around the dolphin? Describe them. Any other elements (stars, text)?
6. OVERALL: What makes this dolphin read as "good"/organic rather than a flat CAD shape?

Be concrete and quantitative (percentages, directions, densities). This is a technical spec, not poetry.`;

async function main() {
  console.log(`🔍 Analyzing reference: ${path.basename(IMAGE_PATH)}\n`);
  const buf = fs.readFileSync(IMAGE_PATH);
  const ext = path.extname(IMAGE_PATH).toLowerCase().replace('.', '') || 'png';
  const mime = ext === 'jpg' ? 'jpeg' : ext;
  const dataUrl = `data:image/${mime};base64,${buf.toString('base64')}`;

  const res = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`
    },
    body: JSON.stringify({
      model: MODEL,
      messages: [
        {
          role: 'user',
          content: [
            { type: 'text', text: PROMPT },
            { type: 'image_url', image_url: { url: dataUrl } }
          ]
        }
      ],
      temperature: 0.2
    })
  });

  if (!res.ok) {
    console.error(`❌ API error ${res.status}: ${await res.text()}`);
    process.exit(1);
  }
  const data = await res.json();
  const text = data.choices?.[0]?.message?.content ?? '(no content)';
  console.log('──────────────────────────────────────────────────');
  console.log(text);
  console.log('──────────────────────────────────────────────────');

  const out = path.join('screenshots', `reference-analysis-${Date.now()}.md`);
  fs.writeFileSync(out, text, 'utf8');
  console.log(`\n💾 Saved: ${path.resolve(out)}`);
}

main().catch((e) => {
  console.error('❌', e);
  process.exit(1);
});
