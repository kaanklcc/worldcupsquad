import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright';

const frontendUrl = process.env.WCAI_FRONTEND_URL || 'http://localhost:3000';
const backendUrl = process.env.WCAI_BACKEND_URL || 'http://localhost:8000';
const cookieHost = process.env.WCAI_COOKIE_HOST || new URL(backendUrl).hostname;
const outputDir = 'submission-assets';
const stamp = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
const username = `judge${stamp}`.slice(0, 20);
const email = `${username}@example.com`;
const password = 'WcaiDemo2026';

mkdirSync(outputDir, { recursive: true });

async function api(path, body) {
  const response = await fetch(`${backendUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${path} failed (${response.status}): ${payload.detail || payload.message || 'unknown error'}`);
  return payload;
}

const registration = await api('/api/auth/register', { username, email, password });
if (!registration.recoveryCode) throw new Error('Registration did not provide a one-time recovery code.');
const login = await api('/api/auth/login', { username_or_email: username, password });
if (!login.token || !login.csrfToken) throw new Error('Login did not provide a browser session.');

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
await context.addCookies([
  { name: 'wcai_session', value: login.token, domain: cookieHost, path: '/', httpOnly: true, sameSite: 'Lax' },
  { name: 'wcai_csrf', value: login.csrfToken, domain: cookieHost, path: '/', httpOnly: false, sameSite: 'Lax' },
]);

const page = await context.newPage();
await page.goto(frontendUrl, { waitUntil: 'networkidle', timeout: 30_000 });
await page.getByText('WCAI AI', { exact: true }).waitFor({ timeout: 20_000 });

await page.getByRole('button', { name: /Membership Locked/i }).click();
await page.getByText('Hackathon judge checkout', { exact: true }).waitFor({ timeout: 10_000 });
await page.screenshot({ path: `${outputDir}/01-access-demo-checkout.png` });

await page.getByRole('button', { name: /Activate 30-min Demo Pro/i }).click();
await page.getByText('Hackathon judge checkout', { exact: true }).waitFor({ state: 'hidden', timeout: 15_000 });

const prompt = 'Build a budget-valid 3-5-2 with Messi and Yamal. Return one AI Lineup Proposal only.';
const chatInput = page.getByPlaceholder('e.g., How do we counter their 4-4-2?');
await chatInput.fill(prompt);
await chatInput.press('Enter');
await page.getByText('AI Lineup Proposal', { exact: true }).waitFor({ timeout: 35_000 });
await page.screenshot({ path: `${outputDir}/02-ai-lineup-proposal.png` });

await page.goto(`${frontendUrl}/tournament`, { waitUntil: 'networkidle', timeout: 30_000 });
await page.getByText('Tournament HQ', { exact: true }).waitFor({ timeout: 20_000 });
await page.screenshot({ path: `${outputDir}/03-tournament-hq.png` });

await page.goto(`${frontendUrl}/transactions`, { waitUntil: 'networkidle', timeout: 30_000 });
await page.getByText('Manager Ledger', { exact: true }).waitFor({ timeout: 20_000 });
await page.screenshot({ path: `${outputDir}/04-action-ledger.png` });

await browser.close();
console.log(`Screenshots written to ${outputDir} for ${username}.`);
