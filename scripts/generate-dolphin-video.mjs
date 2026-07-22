/**
 * generate-dolphin-video.mjs
 * --------------------------
 * Generates a dolphin leap animation with Dashscope's text-to-video model,
 * then extracts frames at 12 FPS for use as a dithered OEL sprite animation.
 *
 * Pipeline:
 *   1. POST video-synthesis task (async)
 *   2. Poll GET /tasks/{task_id} every 15s until SUCCEEDED
 *   3. Download the MP4
 *   4. Extract frames at 12 FPS with ffmpeg (or Playwright fallback)
 *
 * Usage:
 *   node scripts/generate-dolphin-video.mjs --key="<DASHSCOPE_KEY>"
 */
import fs from 'node:fs';
import path from 'node:path';
import { execSync, execFileSync } from 'node:child_process';

function getArg(name, fallback) {
  const prefix = `--${name}=`;
  const hit = process.argv.find((a) => a.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : fallback;
}

const WORKSPACE = 'token-plan';
const BASE = `https://${WORKSPACE}.ap-southeast-1.maas.aliyuncs.com`;
const MODEL = getArg('model', 'happyhorse-1.1-t2v');
const API_KEY = process.env.DASHSCOPE_API_KEY || getArg('key', '');
const OUT_DIR = 'src/assets/dolphin-frames';
const VIDEO_PATH = 'src/assets/dolphin-leap.mp4';
const FPS = 12;
const DURATION = 5; // seconds (min, cheapest)

if (!API_KEY) {
  console.error('❌ Missing API key. Pass --key="..." or set DASHSCOPE_API_KEY.');
  process.exit(1);
}

const PROMPT = [
  'A single bottlenose dolphin performing a slow, graceful leap out of dark water.',
  'Full body visible in side profile throughout the entire animation.',
  'Body arched in a smooth upward arc, nose pointing to the right and slightly downward,',
  'tail fluke trailing on the left, dorsal fin at the apex of the arch.',
  'Dramatic bright cyan rim lighting along the back and head, dark shadowed belly (counter-shading).',
  'Pure black background, isolated subject, no splashes, no water droplets, no other objects.',
  'Monochromatic cyan-teal phosphor glow aesthetic, like a 1990s Organic EL display.',
  'Slow motion, smooth continuous arc motion. Clean silhouette, photorealistic.'
].join(' ');

const NEGATIVE = [
  'text, watermark, logo, UI elements, multiple dolphins, splashes, droplets,',
  'bright background, colorful, rainbow, low quality, blurry, deformed'
].join(' ');

async function createTask() {
  console.log(`🎬 Creating video task with ${MODEL}...`);
  const res = await fetch(`${BASE}/api/v1/services/aigc/video-generation/video-synthesis`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`,
      'X-DashScope-Async': 'enable'
    },
    body: JSON.stringify({
      model: MODEL,
      input: { prompt: PROMPT, negative_prompt: NEGATIVE },
      parameters: {
        resolution: '720P',
        ratio: '16:9',
        duration: DURATION,
        prompt_extend: false,
        watermark: false
      }
    })
  });

  const data = await res.json();
  if (!res.ok || !data.output?.task_id) {
    console.error(`❌ Task creation failed (${res.status}):`, JSON.stringify(data, null, 2));
    process.exit(1);
  }
  console.log(`   task_id: ${data.output.task_id}`);
  console.log(`   status:  ${data.output.task_status}`);
  return data.output.task_id;
}

async function pollTask(taskId) {
  const url = `${BASE}/api/v1/tasks/${taskId}`;
  const maxWait = 6 * 60 * 1000; // 6 minutes
  const interval = 15000; // 15 seconds
  const start = Date.now();

  while (Date.now() - start < maxWait) {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await res.json();
    const status = data.output?.task_status;
    const elapsed = Math.round((Date.now() - start) / 1000);
    console.log(`   [${elapsed}s] status: ${status}`);

    if (status === 'SUCCEEDED') {
      return data.output.video_url;
    }
    if (status === 'FAILED' || status === 'CANCELED' || status === 'UNKNOWN') {
      console.error('❌ Task failed:', JSON.stringify(data, null, 2));
      process.exit(1);
    }
    // PENDING or RUNNING — keep polling.
    await new Promise((r) => setTimeout(r, interval));
  }
  console.error('❌ Timed out waiting for video.');
  process.exit(1);
}

async function downloadVideo(videoUrl) {
  console.log(`\n⬇️  Downloading video...`);
  const res = await fetch(videoUrl);
  if (!res.ok) {
    console.error(`❌ Download failed: ${res.status}`);
    process.exit(1);
  }
  const buffer = Buffer.from(await res.arrayBuffer());
  fs.mkdirSync(path.dirname(VIDEO_PATH), { recursive: true });
  fs.writeFileSync(VIDEO_PATH, buffer);
  console.log(`   Saved ${(buffer.length / 1024 / 1024).toFixed(1)} MB → ${VIDEO_PATH}`);
}

function hasFfmpeg() {
  try {
    execSync('ffmpeg -version', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function extractFrames() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  if (hasFfmpeg()) {
    console.log(`\n🎞️  Extracting frames at ${FPS} FPS with ffmpeg...`);
    execFileSync('ffmpeg', [
      '-y',
      '-i', VIDEO_PATH,
      '-vf', `fps=${FPS}`,
      '-q:v', '2',
      path.join(OUT_DIR, 'frame-%04d.png')
    ], { stdio: 'inherit' });

    const frames = fs.readdirSync(OUT_DIR).filter((f) => f.endsWith('.png')).sort();
    console.log(`   Extracted ${frames.length} frames → ${OUT_DIR}/`);
    return frames;
  }

  console.log('\n⚠️  ffmpeg not found. Install it to extract frames:');
  console.log('   winget install ffmpeg');
  console.log(`   Then run: ffmpeg -i ${VIDEO_PATH} -vf fps=${FPS} ${OUT_DIR}/frame-%04d.png`);
  return [];
}

async function main() {
  const taskId = await createTask();
  const videoUrl = await pollTask(taskId);
  await downloadVideo(videoUrl);
  const frames = extractFrames();

  console.log('\n✅ Done!');
  if (frames.length > 0) {
    console.log(`   ${frames.length} frames in ${OUT_DIR}/`);
    console.log('   Next: run the dithering script to build the sprite sheet.');
  }
}

main().catch((e) => {
  console.error('❌', e);
  process.exit(1);
});
