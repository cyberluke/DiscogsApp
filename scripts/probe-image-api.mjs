/**
 * probe-image-api.mjs — find the working Dashscope image-generation endpoint.
 * Tries several endpoint shapes and reports which one responds.
 */
function getArg(name, fallback) {
  const prefix = `--${name}=`;
  const hit = process.argv.find((a) => a.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : fallback;
}
const API_KEY = process.env.DASHSCOPE_API_KEY || getArg('key', '');
const PROMPT = 'A dolphin leaping, black background, cyan rim light.';

const attempts = [
  {
    label: 'native text2image SYNC (token-plan host, no async header)',
    url: 'https://token-plan.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`
    },
    body: JSON.stringify({
      model: 'wan2.7-image-pro',
      input: { prompt: PROMPT },
      parameters: { size: '1024*1024', n: 1 }
    })
  },
  {
    label: 'compatible-mode images (token-plan host)',
    url: 'https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/images/generations',
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${API_KEY}` },
    body: JSON.stringify({ model: 'wan2.7-image-pro', prompt: PROMPT, n: 1, size: '1024x1024' })
  },
  {
    label: 'native text2image (token-plan host)',
    url: 'https://token-plan.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`,
      'X-DashScope-Async': 'enable'
    },
    body: JSON.stringify({
      model: 'wan2.7-image-pro',
      input: { prompt: PROMPT },
      parameters: { size: '1024*1024', n: 1 }
    })
  },
  {
    label: 'native text2image (dashscope-intl host)',
    url: 'https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`,
      'X-DashScope-Async': 'enable'
    },
    body: JSON.stringify({
      model: 'wan2.7-image-pro',
      input: { prompt: PROMPT },
      parameters: { size: '1024*1024', n: 1 }
    })
  },
  {
    label: 'compatible-mode images (dashscope-intl host)',
    url: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/images/generations',
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${API_KEY}` },
    body: JSON.stringify({ model: 'wan2.7-image-pro', prompt: PROMPT, n: 1, size: '1024x1024' })
  }
];

for (const a of attempts) {
  try {
    const res = await fetch(a.url, { method: a.method, headers: a.headers, body: a.body });
    const text = await res.text();
    console.log(`\n=== ${a.label} ===`);
    console.log(`    ${a.url}`);
    console.log(`    status: ${res.status}`);
    console.log(`    body: ${text.slice(0, 600)}`);
    if (res.ok) {
      console.log('\n✅ THIS ENDPOINT WORKS');
      break;
    }
  } catch (e) {
    console.log(`\n=== ${a.label} ===`);
    console.log(`    ERROR: ${e.message}`);
  }
}
