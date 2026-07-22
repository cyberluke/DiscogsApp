/**
 * visual-judge.mjs — Automated visual feedback loop for the Pioneer OEL display.
 *
 * Pipeline:
 *   1. Playwright screenshot of the display canvas (320×128)
 *   2. Send to Qwen-VL API with a structured evaluation prompt
 *   3. Return JSON scores for dolphin_similarity, waveform_dominance, etc.
 *
 * Usage:
 *   node scripts/visual-judge.mjs [--url http://localhost:4200/ai-dj]
 *
 * Requires: playwright (npx playwright install chromium)
 * Env: DASHSCOPE_API_KEY (or pass --key)
 */

import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = join(__dirname, '..', 'screenshots');
mkdirSync(SCREENSHOT_DIR, { recursive: true });

// --- Config ----------------------------------------------------------------
const API_URL = 'https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions';
const MODEL = 'qwen3.8-max-preview';
function getArg(name, fallback) {
  const eqIdx = process.argv.findIndex((a) => a.startsWith(`--${name}=`));
  if (eqIdx !== -1) return process.argv[eqIdx].split('=')[1];
  const spIdx = process.argv.indexOf(`--${name}`);
  if (spIdx !== -1 && spIdx + 1 < process.argv.length) return process.argv[spIdx + 1];
  return fallback;
}

const DISPLAY_URL = getArg('url', 'http://localhost:4200/ai-dj');
const API_KEY = process.env.DASHSCOPE_API_KEY || getArg('key', '');

if (!API_KEY) {
  console.error('ERROR: Set DASHSCOPE_API_KEY env var or pass --key=<key>');
  process.exit(1);
}

// --- Reference description (Pioneer OEL dolphin, 1998–2003) ----------------
const REFERENCE_DESCRIPTION = `
A late-1990s Pioneer Organic EL (OEL) car head-unit display (1998–2003 era).
Fixed 320×128 pixel monochrome phosphor display (blue or green).

Layout (top to bottom):
- Track text (artist/title) in a tiny 3×5 bitmap font at the very top
- A LEAPING DOLPHIN as the absolute centerpiece — large, graceful, arcing
  across the middle ~50-60% of the display height. The dolphin has a clearly
  defined body, dorsal fin, tail fluke, pectoral fin, and a subtle rim light.
  It is the dominant visual element by far.
- Thin, elegant water-surface lines (2-3 rows) below the dolphin, occupying
  at most 15% of display height. These are subtle, low-contrast, subordinate.
- A short FFT spectrum bar graph at the bottom (~13% height), low contrast.
- VU meter segments in the bottom-left corner.

Visual character:
- Monochrome phosphor glow — NOT a modern HUD or cyberpunk visualizer
- The dolphin should look like a lit phosphor object, not a flat CAD drawing
- Soft afterglow / persistence trails behind moving objects (short, not foggy)
- Bloom is subtle — objects are crisp with a gentle glow halo, NOT blown out
- The eye should travel: dolphin → text → waves → FFT (dolphin dominates)
- Overall brightness is moderate — not a whiteout, not too dim
`;

// --- Evaluation prompt -------------------------------------------------------
const EVALUATION_PROMPT = `You are an expert visual evaluator for a retro Pioneer OEL car display replica.

REFERENCE (what the display SHOULD look like):
${REFERENCE_DESCRIPTION}

TASK: Evaluate the CURRENT screenshot against the reference. Score each dimension 0–10 and provide brief justification.

Return ONLY valid JSON (no markdown, no explanation outside JSON):
{
  "dolphin_recognizability": <0-10>,
  "dolphin_dominance": <0-10>,
  "dolphin_organic_quality": <0-10>,
  "waveform_subordination": <0-10>,
  "fft_subordination": <0-10>,
  "composition_order": <0-10>,
  "glow_quality": <0-10>,
  "bloom_appropriateness": <0-10>,
  "persistence_quality": <0-10>,
  "overall_fidelity": <0-10>,
  "issues": ["list of specific problems, most critical first"],
  "suggestions": ["list of specific improvements, most impactful first"]
}

Scoring guide:
- dolphin_recognizability: Can you clearly see a dolphin (body, fin, tail, head)? 10=perfect silhouette, 0=unrecognizable blob
- dolphin_dominance: Is the dolphin the absolute visual centerpiece? 10=eye goes straight to it, 0=something else dominates
- dolphin_organic_quality: Does it look like a living creature or a CAD drawing? 10=organic/soft, 0=geometric/hard
- waveform_subordination: Are the waves subtle and subordinate? 10=barely visible, 0=competing with dolphin
- fft_subordination: Is the FFT low and unobtrusive? 10=barely there, 0=dominating
- composition_order: Does the eye travel dolphin→text→waves→FFT? 10=perfect hierarchy, 0=reversed
- glow_quality: Is the phosphor glow soft and realistic? 10=perfect OEL look, 0=flat or blown out
- bloom_appropriateness: Is bloom subtle (not blown out)? 10=crisp with gentle halo, 0=whiteout blur
- persistence_quality: Is the afterglow short and clean (not foggy)? 10=short trail, 0=whole-scene smear
- overall_fidelity: How close is this to a real 1999 Pioneer OEL display? 10=indistinguishable, 0=nothing like it
`;

// --- Main --------------------------------------------------------------------
async function main() {
  console.log(`\n🔍 Visual Judge — Pioneer OEL Display Evaluator`);
  console.log(`   URL: ${DISPLAY_URL}`);
  console.log(`   Model: ${MODEL}\n`);

  // 1. Screenshot
  console.log('📸 Taking screenshot...');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(DISPLAY_URL, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000); // let the display animate

  const canvas = await page.$('.display-host canvas');
  if (!canvas) {
    console.error('ERROR: No .display-host canvas found');
    await browser.close();
    process.exit(1);
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const screenshotPath = join(SCREENSHOT_DIR, `display-${timestamp}.png`);
  await canvas.screenshot({ path: screenshotPath });
  console.log(`   Saved: ${screenshotPath}`);
  await browser.close();

  // 2. Read screenshot as base64
  const { readFileSync } = await import('fs');
  const imageBase64 = readFileSync(screenshotPath).toString('base64');
  const imageDataUrl = `data:image/png;base64,${imageBase64}`;

  // 3. Call Qwen-VL API
  console.log('🤖 Sending to Qwen-VL for evaluation...');
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`
    },
    body: JSON.stringify({
      model: MODEL,
      messages: [
        {
          role: 'user',
          content: [
            { type: 'text', text: EVALUATION_PROMPT },
            { type: 'image_url', image_url: { url: imageDataUrl } }
          ]
        }
      ],
      temperature: 0.1,
      max_tokens: 2000
    })
  });

  if (!response.ok) {
    const errText = await response.text();
    console.error(`ERROR: API returned ${response.status}: ${errText}`);
    process.exit(1);
  }

  const data = await response.json();
  const content = data.choices?.[0]?.message?.content || '';

  // 4. Parse JSON from response
  let evaluation;
  try {
    // Try to extract JSON from the response (might have markdown fences)
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) throw new Error('No JSON found');
    evaluation = JSON.parse(jsonMatch[0]);
  } catch (e) {
    console.error('ERROR: Failed to parse evaluation JSON');
    console.error('Raw response:', content);
    process.exit(1);
  }

  // 5. Output
  console.log('\n📊 EVALUATION RESULTS:\n');
  console.log('─'.repeat(50));
  const dims = [
    ['Dolphin Recognizability', evaluation.dolphin_recognizability],
    ['Dolphin Dominance', evaluation.dolphin_dominance],
    ['Dolphin Organic Quality', evaluation.dolphin_organic_quality],
    ['Waveform Subordination', evaluation.waveform_subordination],
    ['FFT Subordination', evaluation.fft_subordination],
    ['Composition Order', evaluation.composition_order],
    ['Glow Quality', evaluation.glow_quality],
    ['Bloom Appropriateness', evaluation.bloom_appropriateness],
    ['Persistence Quality', evaluation.persistence_quality],
    ['Overall Fidelity', evaluation.overall_fidelity]
  ];
  for (const [name, score] of dims) {
    const bar = '█'.repeat(score) + '░'.repeat(10 - score);
    const flag = score >= 7 ? '✅' : score >= 5 ? '⚠️' : '❌';
    console.log(`  ${flag} ${name.padEnd(28)} ${bar} ${score}/10`);
  }
  console.log('─'.repeat(50));

  if (evaluation.issues?.length) {
    console.log('\n🔴 ISSUES:');
    for (const issue of evaluation.issues) {
      console.log(`   • ${issue}`);
    }
  }
  if (evaluation.suggestions?.length) {
    console.log('\n💡 SUGGESTIONS:');
    for (const s of evaluation.suggestions) {
      console.log(`   • ${s}`);
    }
  }

  // 6. Save evaluation JSON
  const evalPath = join(SCREENSHOT_DIR, `eval-${timestamp}.json`);
  writeFileSync(evalPath, JSON.stringify(evaluation, null, 2));
  console.log(`\n💾 Evaluation saved: ${evalPath}`);

  // 7. Summary score
  const scores = dims.map(([, s]) => s);
  const avg = (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1);
  console.log(`\n🎯 OVERALL SCORE: ${avg}/10`);
  console.log(`   Screenshot: ${screenshotPath}\n`);
}

main().catch((err) => {
  console.error('FATAL:', err);
  process.exit(1);
});
