/**
 * generate-dolphin-image.mjs
 * --------------------------
 * Generates a reference dolphin image with Dashscope's `wan2.7-image-pro`
 * model (OpenAI-compatible images endpoint). The output is a high-contrast,
 * rim-lit dolphin on a black background — ideal source material for
 * downscaling + 1-bit Floyd–Steinberg dithering into an OEL sprite.
 *
 * Usage:
 *   node scripts/generate-dolphin-image.mjs --key="<DASHSCOPE_KEY>" [--out="path.png"]
 */
import fs from 'node:fs';
import path from 'node:path';

function getArg(name, fallback) {
  const prefix = `--${name}=`;
  const hit = process.argv.find((a) => a.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : fallback;
}

const BASE = 'https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode';
const MODEL = 'wan2.7-image-pro';
const API_KEY = process.env.DASHSCOPE_API_KEY || getArg('key', '');
const OUT = getArg('out', 'src/assets/dolphin-source.png');

if (!API_KEY) {
  console.error('❌ Missing API key. Pass --key="..." or set DASHSCOPE_API_KEY.');
  process.exit(1);
}

const PROMPT = [
  'A single bottlenose dolphin leaping out of dark water, full body in side profile,',
  'body arched in a graceful upward arc, nose pointing to the right and slightly downward,',
  'tail fluke on the left, one pectoral fin visible, dorsal fin at the apex of the arch.',
  'Dramatic bright rim lighting along the back and head, dark shadowed belly (counter-shading),',
  'glossy wet skin with a strong specular highlight along the top edge.',
  'Pure black background, isolated subject, no splashes, no water droplets, no other objects.',
  'High contrast, monochromatic cyan-teal palette, photorealistic, crisp edges, clean silhouette.'
].join(' ');

async function main() {
  console.log(`🎨 Generating dolphin with ${MODEL}...\n`);

  const res = await fetch(`${BASE}/v1/images/generations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`
    },
    body: JSON.stringify({
      model: MODEL,
      prompt: PROMPT,
      n: 1,
      size: '1024x1024'
    })
  });

  if (!res.ok) {
    console.error(`❌ API error ${res.status}: ${await res.text()}`);
    process.exit(1);
  }

  const data = await res.json();
  const item = data.data?.[0];
  if (!item) {
    console.error('❌ No image in response:', JSON.stringify(data, null, 2));
    process.exit(1);
  }

  // The image may come back as a URL or inline base64.
  let buffer;
  if (item.b64_json) {
    buffer = Buffer.from(item.b64_json, 'base64');
  } else if (item.url) {
    console.log(`   Downloading: ${item.url}`);
    const imgRes = await fetch(item.url);
    if (!imgRes.ok) {
      console.error(`❌ Download failed ${imgRes.status}`);
      process.exit(1);
    }
    buffer = Buffer.from(await imgRes.arrayBuffer());
  } else {
    console.error('❌ Unexpected response shape:', JSON.stringify(data, null, 2));
    process.exit(1);
  }

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, buffer);
  console.log(`\n💾 Saved ${buffer.length} bytes → ${path.resolve(OUT)}`);
}

main().catch((e) => {
  console.error('❌', e);
  process.exit(1);
});
