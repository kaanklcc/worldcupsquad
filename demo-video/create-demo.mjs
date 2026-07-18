import { chromium } from 'playwright';
import ffmpegPath from 'ffmpeg-static';
import { existsSync, mkdirSync, rmSync, statSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const generated = join(import.meta.dirname, 'generated');
const audioDir = join(generated, 'audio');
const rawDir = join(generated, 'raw');
const outputPath = join(import.meta.dirname, 'WCAI-Hackathon-Demo.mp4');
const thumbnailPath = join(import.meta.dirname, 'WCAI-Hackathon-Demo-Thumbnail.png');
const ttsPath = join(root, 'backend', 'venv', 'Scripts', 'edge-tts.exe');
const username = process.env.WCAI_DEMO_USERNAME;
const password = process.env.WCAI_DEMO_PASSWORD;

if (!username || !password) {
  throw new Error('Set WCAI_DEMO_USERNAME and WCAI_DEMO_PASSWORD for the local demo account. They are never written to the video scripts or output.');
}
if (!existsSync(ttsPath)) throw new Error(`edge-tts is missing at ${ttsPath}`);
if (!ffmpegPath) throw new Error('ffmpeg-static is not available.');

const segments = [
  {
    title: 'WCAI — WORLD CUP AI COMMAND CENTRE',
    subtitle: 'Injective Global Cup Hackathon 2026',
    narration: 'Welcome to WCAI, the World Cup AI Command Centre built for the Injective Global Cup. WCAI turns a football question into a transparent fantasy decision. It combines the complete World Cup squad pool, source-aware player intelligence, Gemini agent skills, an MCP action layer, x402 access, and Circle CCTP testnet funding in one manager workflow.',
    action: 'intro',
  },
  {
    title: 'SECURE MANAGER ACCESS',
    subtitle: 'Registration, recovery and authenticated sessions',
    narration: 'The experience starts with manager access control. A new user can create an account with a recovery question, while an existing manager can use the password recovery flow. Authentication is handled by the FastAPI backend, and protected squad, analytics, payment and receipt endpoints require the authenticated manager session.',
    action: 'authTour',
  },
  {
    title: 'SIGN IN TO WCAI',
    subtitle: 'The password remains masked throughout the recording',
    narration: 'For this walkthrough I am signing in to the dedicated hackathon demo account. The password is masked and no environment value, wallet private key, seed phrase or API key is shown. The account has a clearly labelled Demo Pro entitlement, so judges can inspect every premium workflow without spending funds.',
    action: 'login',
  },
  {
    title: 'THE TACTICAL COMMAND CENTRE',
    subtitle: 'Pitch, squad controls, AI consultant and budget in one view',
    narration: 'This is the main command centre. The left rail switches between lineup, substitutions, matchday, analytics, Tactical Lab, finance, Tournament Headquarters and the Action Ledger. The centre is an interactive formation-aware pitch. On the right, WCAI AI holds the football conversation and returns structured actions only when the manager explicitly asks for one.',
    action: 'dashboard',
  },
  {
    title: 'x402 ACCESS AND MEMBERSHIP',
    subtitle: 'AI, analytics and finance are protected server-side',
    narration: 'The access console explains exactly what each tier unlocks. Pro Membership enables Gemini chat, unlimited Deep Tactical Analytics, MCP lineup and transfer actions, and CCTP finance. A smaller x402 Match Pass unlocks time-limited AI and analysis. Outside this named demo account, the browser signs an EIP three thousand and nine authorization and access changes only after facilitator verification and settlement.',
    action: 'access',
  },
  {
    title: 'FORMATION-AWARE PITCH',
    subtitle: 'Five shapes with exact position counts',
    narration: 'Formation is a real squad constraint, not decoration. WCAI supports four three three, four four two, four two three one, three five two, and five three two. Changing shape rebuilds the exact number of goalkeeper, defender, midfielder and forward slots while preserving compatible selected players. The backend validates that same formation before a lineup can be saved.',
    action: 'formation',
  },
  {
    title: 'ALL 48 TEAMS — 1,248 PLAYERS',
    subtitle: 'Search, national-team filter, points, price and availability',
    narration: 'Every empty or replacement slot opens the player selector. Managers can search by name or nation, filter across all forty eight teams, and sort by fantasy points or price. Each row carries national colours, shirt number, club, roster snapshot, availability, price and model points. Budget-breaking or unavailable choices are disabled before selection.',
    action: 'playerSelector',
  },
  {
    title: 'PLAYER INTEL CARDS',
    subtitle: 'Verified tournament facts separated from WCAI estimates',
    narration: 'Clicking a selected player opens an individual Intel Card. It separates source-backed roster and World Cup event fields from WCAI modelling. The card includes player identity, national styling, shirt number, price, verified goals and assists when available, radar signals, expected goals, injury risk, tactical trend and a player-specific scouting brief. Premium estimates are never presented as official FIFA ratings.',
    action: 'playerIntel',
  },
  {
    title: 'SUBSTITUTIONS AND DIRECT CONTROLS',
    subtitle: 'Bench slots, one-player replacement and explicit removal',
    narration: 'The Substitutions tab exposes the eight-player bench and keeps every action local until confirmation. The swap control opens a position-compatible replacement list. The red control removes only that player, never the full squad. WCAI also understands single-player replacement requests in chat and produces one transfer instead of rebuilding the starting eleven.',
    action: 'substitutions',
  },
  {
    title: 'CONVERSATIONAL MATCH ANALYSIS',
    subtitle: 'Discussion first — no unwanted lineup mutation',
    narration: 'WCAI is also a football conversation, not just a lineup generator. Here I ask for an Argentina versus England analysis and explicitly say not to change the squad. Gemini receives the current formation, selected player identifiers, access state and source policy. It can discuss tactical advantages, risks and matchup context without returning or applying a lineup unless the request asks for one.',
    action: 'conversation',
  },
  {
    title: 'STRUCTURED AI LINEUP PROPOSAL',
    subtitle: 'Exact formation, player IDs, budget and explicit approval',
    narration: 'Now I explicitly request a three five two featuring Lionel Messi and Lamine Yamal. The Agent Skills layer searches the actual catalog, validates position counts and budget, and returns a structured proposal containing the exact formation and eleven stable player identifiers. The proposal card is separate from Gemini prose, so the screen and the saved squad cannot disagree. I will apply it to demonstrate the MCP-backed action.',
    action: 'lineup',
  },
  {
    title: 'MCP ACTION RECEIPT',
    subtitle: 'The approved eleven is persisted through a constrained tool',
    narration: 'After approval, the backend validates the same eleven again and calls the standalone Model Context Protocol server. MCP tools can apply a lineup, execute one transfer, read the squad, set a formation and fetch player details. The UI updates only after confirmation and displays an auditable MCP receipt. Repeated requests use idempotency keys, preventing an accidental duplicate mutation.',
    action: 'mcpResult',
  },
  {
    title: 'DEEP TACTICAL ANALYTICS',
    subtitle: 'Verified contributions, model xG, risk and price efficiency',
    narration: 'Deep Tactical Analytics evaluates the authenticated squad and server-side budget. It checks positional balance, available verified goals and assists, model expected goals, availability, clean-sheet potential, injury risk and price efficiency. It explains the weakest tactical points and compares alternatives. If one transfer materially improves the squad, WCAI presents a separate confirm or reject card. Reject always leaves the squad unchanged.',
    action: 'analytics',
  },
  {
    title: 'GAFFER MATCHDAY BRIEF',
    subtitle: 'Fixture context, captain signals, risks and scenarios',
    narration: 'Matchday opens a source-aware briefing cockpit. It shows the current fixture context and data confidence, captain and vice-captain signals, a budget-valid recommended eleven, watch-outs and alternative tactical scenarios. Unknown scores and unconfirmed starting lineups remain unknown rather than being invented, which makes the distinction between live facts and application estimates visible to the fan.',
    action: 'matchday',
  },
  {
    title: 'TACTICAL LAB',
    subtitle: 'Non-mutating what-if comparison across every supported shape',
    narration: 'Tactical Lab is a premium decision tool rather than a static illustration. It compares the current baseline with five budget-valid formation simulations, showing points, budget, delta from the best result and readiness. The recommended shape is highlighted, but the laboratory never changes the saved squad automatically. A manager must still make a separate explicit application decision.',
    action: 'tacticalLab',
  },
  {
    title: 'INJECTIVE FINANCE AND CCTP',
    subtitle: 'Manager-signed Sepolia burn, Circle attestation, Injective mint',
    narration: 'Finance reports budget usage and exposes the one-time Circle CCTP backing flow. The user saves a public Injective EVM address, then MetaMask signs each testnet transaction. The sequence is Sepolia USDC approval and burn, Circle Iris attestation, and mint on Injective EVM Testnet. WCAI never receives a private key and credits twenty fantasy budget units only after independently verifying both confirmed receipts.',
    action: 'finance',
  },
  {
    title: 'TOURNAMENT HQ',
    subtitle: 'Live fixture map, animated knockout tree and source-labelled squads',
    narration: 'Tournament Headquarters expands the app beyond a squad builder. The top cards report mapped teams, tracked matches and detailed rosters. Managers can follow the animated knockout route, refresh the tournament feed, filter fixtures by stage, and move into Squad Intel. Every live or fallback state is labelled so the interface does not disguise a community feed as official data.',
    action: 'tournament',
  },
  {
    title: 'SQUAD INTEL COLLECTION',
    subtitle: 'Team directory and individual Scout Cards',
    narration: 'Squad Intel organises all nations by group and opens a dedicated roster collection for the selected team. Each Scout Card uses that national identity and exposes the corresponding player-level source and signal details. This gives a fan a fast route from the tournament map to an individual fantasy decision without leaving the WCAI experience.',
    action: 'squadIntel',
  },
  {
    title: 'ACTION LEDGER',
    subtitle: 'Replay-safe x402, MCP and CCTP intents with durable receipts',
    narration: 'The Manager Ledger is the audit surface for the entire product. It separates access, tactical and funding operations; shows provider, network, receipt, state and whether an entry is a labelled demo or provider-confirmed action; and expands the idempotency key and full structured receipt. This makes premium access and AI-driven changes inspectable instead of opaque.',
    action: 'ledger',
  },
  {
    title: 'EXECUTE CHANGES',
    subtitle: 'Final server validation and persisted squad snapshot',
    narration: 'Execute Changes performs the final squad snapshot sync. The backend recalculates cost and validates catalog identifiers, duplicates, availability, formation positions and budget instead of trusting browser state. A successful confirmation produces a visible receipt and preserves the manager’s tactics for the next session.',
    action: 'execute',
  },
  {
    title: 'BUILT FOR THE INJECTIVE GLOBAL CUP',
    subtitle: 'Useful football intelligence with verifiable protocol boundaries',
    narration: 'WCAI combines a usable World Cup fan product with meaningful Injective technology. x402 protects AI access. Circle CCTP connects testnet USDC backing to the fantasy budget. MCP constrains and receipts squad actions. Gemini Agent Skills turn football language into validated decisions. The result is simple for a fan, transparent for a judge, and structured for future live data and on-chain contributions. Thank you for watching.',
    action: 'outro',
  },
];

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: root, encoding: 'utf8', stdio: options.quiet ? 'pipe' : 'inherit' });
  if (result.status !== 0) throw new Error(`${command} failed with exit code ${result.status}\n${result.stderr || ''}`);
  return result;
}

function mediaDurationSeconds(path) {
  const result = spawnSync(ffmpegPath, ['-i', path], { encoding: 'utf8' });
  const match = String(result.stderr || '').match(/Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)/);
  if (!match) throw new Error(`Could not read media duration for ${path}`);
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]);
}

function synthesizeNarration() {
  mkdirSync(audioDir, { recursive: true });
  return segments.map((segment, index) => {
    const path = join(audioDir, `${String(index + 1).padStart(2, '0')}.mp3`);
    if (!existsSync(path)) {
      run(ttsPath, ['--voice', 'en-US-AndrewNeural', '--rate=+4%', '--pitch=-2Hz', '--text', segment.narration, '--write-media', path]);
    }
    return { ...segment, audioPath: path, duration: mediaDurationSeconds(path) };
  });
}

function buildNarrationTrack(timedSegments) {
  const track = join(generated, 'narration.m4a');
  const args = ['-y'];
  timedSegments.forEach((segment) => args.push('-i', segment.audioPath));
  const filters = timedSegments.map((segment, index) =>
    `[${index}:a]apad=pad_dur=0.75,atrim=0:${(segment.duration + 0.75).toFixed(3)}[a${index}]`
  );
  filters.push(`${timedSegments.map((_, index) => `[a${index}]`).join('')}concat=n=${timedSegments.length}:v=0:a=1,adelay=1500|1500[outa]`);
  args.push('-filter_complex', filters.join(';'), '-map', '[outa]', '-c:a', 'aac', '-b:a', '192k', track);
  run(ffmpegPath, args);
  return track;
}

async function installVideoChrome(page) {
  await page.addStyleTag({ content: `
    nextjs-portal { display: none !important; }
    @keyframes wcaiDemoPulse { 0%,100% { box-shadow: 0 0 0 3px rgba(52,211,153,.25), 0 0 28px rgba(52,211,153,.25); } 50% { box-shadow: 0 0 0 6px rgba(251,191,36,.35), 0 0 42px rgba(251,191,36,.38); } }
    .wcai-demo-highlight { position: relative !important; z-index: 99990 !important; animation: wcaiDemoPulse 1.25s ease-in-out infinite !important; outline: 2px solid rgba(251,191,36,.95) !important; outline-offset: 3px !important; }
  `});
}

async function caption(page, title, subtitle, fullScreen = false) {
  await page.evaluate(({ title, subtitle, fullScreen }) => {
    document.querySelectorAll('.wcai-demo-highlight').forEach((element) => element.classList.remove('wcai-demo-highlight'));
    let overlay = document.getElementById('wcai-demo-caption');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'wcai-demo-caption';
      document.body.appendChild(overlay);
    }
    overlay.style.cssText = fullScreen
      ? 'position:fixed;inset:0;z-index:999999;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:80px;background:radial-gradient(circle at 50% 25%,rgba(16,185,129,.28),transparent 35%),linear-gradient(135deg,#020617 0%,#052e2b 55%,#111827 100%);color:white;pointer-events:none;font-family:Arial,sans-serif;'
      : 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:999999;width:min(760px,calc(100vw - 48px));padding:14px 20px;border:1px solid rgba(251,191,36,.55);border-radius:14px;background:linear-gradient(135deg,rgba(2,6,23,.94),rgba(6,78,59,.94));box-shadow:0 18px 55px rgba(0,0,0,.42);color:white;pointer-events:none;font-family:Arial,sans-serif;backdrop-filter:blur(12px);';
    overlay.innerHTML = fullScreen
      ? `<div style="font-size:13px;font-weight:800;letter-spacing:.32em;color:#fcd34d;margin-bottom:18px">INJECTIVE GLOBAL CUP 2026</div><div style="font-size:56px;line-height:1.02;font-weight:900;letter-spacing:-.035em;max-width:1050px">${title}</div><div style="font-size:19px;line-height:1.5;color:#d1fae5;margin-top:20px;max-width:900px">${subtitle}</div><div style="display:flex;gap:12px;margin-top:30px;font-size:12px;font-weight:800;letter-spacing:.14em"><span style="padding:9px 14px;border-radius:999px;background:#10b981;color:#022c22">x402</span><span style="padding:9px 14px;border-radius:999px;background:#22d3ee;color:#083344">CCTP</span><span style="padding:9px 14px;border-radius:999px;background:#fbbf24;color:#422006">MCP</span><span style="padding:9px 14px;border-radius:999px;background:#a78bfa;color:#2e1065">AGENT SKILLS</span></div>`
      : `<div style="font-size:11px;font-weight:900;letter-spacing:.19em;color:#fcd34d;margin-bottom:5px">WCAI DEMO</div><div style="font-size:22px;line-height:1.1;font-weight:900;letter-spacing:-.01em">${title}</div><div style="font-size:13px;line-height:1.35;color:#d1fae5;margin-top:5px">${subtitle}</div>`;
  }, { title, subtitle, fullScreen });
}

async function highlight(locator) {
  try {
    await locator.first().scrollIntoViewIfNeeded({ timeout: 5000 });
    await locator.first().evaluate((element) => element.classList.add('wcai-demo-highlight'));
  } catch { /* The narration remains valid if an optional visual is unavailable. */ }
}

async function closeCaption(page) {
  await page.evaluate(() => document.getElementById('wcai-demo-caption')?.remove());
}

async function waitForAgent(page, previousCount, timeout = 65000) {
  await page.waitForFunction((count) => {
    const labels = [...document.querySelectorAll('div')].filter((element) => /^(GEMINI LIVE|STATIC FALLBACK)$/.test((element.textContent || '').trim()));
    return labels.length > count;
  }, previousCount, { timeout });
}

async function providerCount(page) {
  return page.locator('div').filter({ hasText: /^(GEMINI LIVE|STATIC FALLBACK)$/ }).count();
}

function sidebarButton(page, label) {
  return page.locator('button').filter({ hasText: new RegExp(label, 'i') }).first();
}

async function perform(page, action) {
  const input = () => page.getByPlaceholder('e.g., How do we counter their 4-4-2?');
  switch (action) {
    case 'intro':
      return;
    case 'authTour': {
      await page.getByRole('button', { name: 'Create manager account' }).click();
      await highlight(page.getByRole('button', { name: 'CREATE MANAGER ACCOUNT' }));
      await page.waitForTimeout(1800);
      await page.getByRole('button', { name: 'Sign in' }).click();
      await page.getByRole('button', { name: 'Forgot password?' }).click();
      await highlight(page.getByRole('button', { name: 'VERIFY SECURITY QUESTION' }));
      await page.waitForTimeout(1800);
      await page.getByRole('button', { name: 'Cancel and return to sign in' }).click();
      return;
    }
    case 'login':
      await page.getByPlaceholder('Manager username or email').fill(username);
      await page.locator('input[type="password"]').fill(password);
      await highlight(page.getByRole('button', { name: 'SIGN IN TO WCAI' }));
      await page.waitForTimeout(900);
      await page.getByRole('button', { name: 'SIGN IN TO WCAI' }).click();
      await page.getByText('WCAI AI', { exact: true }).waitFor({ timeout: 30000 });
      return;
    case 'dashboard':
      await highlight(page.getByText('INJ CONTROL', { exact: true }));
      return;
    case 'access':
      await page.getByRole('button', { name: /DEMO PRO|PRO MEMBER|MEMBERSHIP LOCKED/i }).click();
      await page.getByText('AI, Analytics & Injective Finance', { exact: true }).waitFor();
      await highlight(page.getByText('x402 Match Pass', { exact: true }));
      await page.waitForTimeout(2200);
      await page.getByRole('button', { name: 'Close membership dialog' }).click({ position: { x: 8, y: 8 } });
      return;
    case 'formation':
      await highlight(page.getByRole('button', { name: '3-5-2', exact: true }));
      await page.getByRole('button', { name: '3-5-2', exact: true }).click();
      await page.waitForTimeout(2200);
      await page.getByRole('button', { name: '4-3-3', exact: true }).click();
      return;
    case 'playerSelector': {
      const addButton = page.locator('button').filter({ hasText: '+ ADD' }).first();
      if (await addButton.count()) await addButton.click();
      else await page.locator('button').filter({ hasText: 'swap_horiz' }).first().click();
      await page.getByPlaceholder('Search by name or team...').waitFor();
      await page.getByPlaceholder('Search by name or team...').fill('Yamal');
      await page.getByLabel('Filter players by national team').selectOption({ label: 'Spain' }).catch(() => {});
      await highlight(page.getByText(/Lamine Yamal/i).first());
      await page.waitForTimeout(2600);
      await page.locator('div.fixed.inset-0.z-50 > div.absolute.inset-0').first().click({ position: { x: 8, y: 8 } });
      return;
    }
    case 'playerIntel': {
      const intelButton = page.locator('button').filter({ hasText: 'OPEN INTEL' }).first();
      await intelButton.click();
      const modalTitle = page.getByText(/Player Intel \/\//i).first();
      await modalTitle.waitFor({ timeout: 30000 });
      const tacticalSignal = page.getByText(/WCAI tactical signal/i).first();
      await tacticalSignal.waitFor({ timeout: 30000 });
      await highlight(tacticalSignal);
      await page.waitForTimeout(4200);
      const modal = modalTitle.locator('xpath=ancestor::div[contains(@class,"fixed") and contains(@class,"inset-0")][1]');
      const card = modal.locator('section').first();
      await card.evaluate((element) => { element.scrollTop = element.scrollHeight * 0.55; }).catch(() => {});
      await page.waitForTimeout(1700);
      await modal.locator('section header button').click();
      await modalTitle.waitFor({ state: 'hidden', timeout: 10000 });
      return;
    }
    case 'substitutions':
      await sidebarButton(page, 'SUBSTITUTIONS').click();
      await highlight(page.locator('button').filter({ hasText: 'close' }).first());
      return;
    case 'conversation': {
      await sidebarButton(page, 'LINEUP').click();
      const before = await providerCount(page);
      await input().fill('Analyse Argentina versus England for me. Discuss tactical strengths, risks and key players, but do not build or change my lineup.');
      await input().press('Enter');
      await waitForAgent(page, before);
      await highlight(page.locator('div').filter({ hasText: /^(GEMINI LIVE|STATIC FALLBACK)$/ }).last());
      return;
    }
    case 'lineup': {
      await page.getByRole('button', { name: '3-5-2', exact: true }).click();
      const before = await providerCount(page);
      await input().fill('Build a budget-valid attacking 3-5-2 World Cup lineup. Lionel Messi and Lamine Yamal must be included. Return an exact lineup proposal and do not apply it until I confirm.');
      await input().press('Enter');
      await waitForAgent(page, before);
      await page.getByText('AI Lineup Proposal', { exact: true }).waitFor({ timeout: 65000 });
      await highlight(page.getByText('AI Lineup Proposal', { exact: true }));
      await page.waitForTimeout(2800);
      const apply = page.getByRole('button', { name: 'APPLY LINEUP', exact: true });
      if (await apply.isVisible()) {
        await apply.click();
        await page.getByText(/AI lineup applied/i).last().waitFor({ timeout: 45000 });
      }
      return;
    }
    case 'mcpResult':
      await highlight(page.getByText(/MCP receipt:/i).last());
      return;
    case 'analytics': {
      const before = await providerCount(page);
      await sidebarButton(page, 'ANALYTICS').click();
      await waitForAgent(page, before, 75000);
      const reject = page.getByRole('button', { name: 'Reject', exact: true }).last();
      if (await reject.isVisible().catch(() => false)) {
        await highlight(reject);
        await page.waitForTimeout(2200);
        await reject.click();
      }
      return;
    }
    case 'matchday':
      await sidebarButton(page, 'MATCHDAY').click();
      await page.getByText('Gaffer Matchday Brief', { exact: true }).waitFor({ timeout: 30000 });
      await highlight(page.getByText('Captain signal', { exact: true }));
      return;
    case 'tacticalLab':
      if (await page.getByRole('button', { name: 'Close tactical panel' }).isVisible().catch(() => false)) await page.getByRole('button', { name: 'Close tactical panel' }).click();
      await sidebarButton(page, 'TACTICAL LAB').click();
      await page.getByText('Which shape wins your budget?', { exact: true }).waitFor({ timeout: 30000 });
      await highlight(page.getByText(/Recommended shape:/).first());
      return;
    case 'finance': {
      if (await page.getByRole('button', { name: 'Close tactical panel' }).isVisible().catch(() => false)) await page.getByRole('button', { name: 'Close tactical panel' }).click();
      await sidebarButton(page, 'FINANCE').click();
      await page.getByText(/FINANCE & BUDGET REPORTS/).last().waitFor();
      await page.getByRole('button', { name: 'ACQUIRE BACKING', exact: true }).click();
      await page.getByText('AI, Analytics & Injective Finance', { exact: true }).waitFor();
      await highlight(page.getByPlaceholder('inj1... or 0x...'));
      return;
    }
    case 'tournament':
      await page.goto('http://localhost:3000/tournament', { waitUntil: 'domcontentloaded' });
      await page.getByText('Tournament HQ', { exact: true }).waitFor({ timeout: 30000 });
      await installVideoChrome(page);
      await page.getByRole('button', { name: /FIXTURES/i }).click();
      await page.getByText('Matchday filter', { exact: true }).waitFor();
      await page.waitForTimeout(2200);
      await page.getByRole('button', { name: /BRACKET/i }).click();
      await highlight(page.getByText('From round of 32 to the final', { exact: true }));
      return;
    case 'squadIntel':
      await page.getByRole('button', { name: /SQUAD INTEL/i }).click();
      await page.getByText('Scout card collection', { exact: true }).waitFor();
      await highlight(page.getByText('Scout card collection', { exact: true }));
      await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight * 0.48, behavior: 'smooth' }));
      return;
    case 'ledger':
      await page.goto('http://localhost:3000/transactions', { waitUntil: 'domcontentloaded' });
      await page.getByText('Manager Ledger', { exact: true }).waitFor({ timeout: 30000 });
      await installVideoChrome(page);
      await page.getByRole('button', { name: 'tactical', exact: true }).click();
      await page.waitForTimeout(1500);
      const receipt = page.locator('article button').first();
      if (await receipt.count()) await receipt.click();
      await highlight(page.getByText('Action history', { exact: true }));
      return;
    case 'execute':
      await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
      await page.getByText('WCAI AI', { exact: true }).waitFor({ timeout: 30000 });
      await installVideoChrome(page);
      await page.locator('button').filter({ hasText: /EXECUTE CHANGES/i }).first().click();
      await page.getByText('Sync Successful!', { exact: true }).waitFor({ timeout: 30000 });
      await highlight(page.getByText('Sync Successful!', { exact: true }));
      return;
    case 'outro':
      if (await page.getByRole('button', { name: 'Done', exact: true }).isVisible().catch(() => false)) await page.getByRole('button', { name: 'Done', exact: true }).click();
      return;
    default:
      throw new Error(`Unknown action: ${action}`);
  }
}

async function record(timedSegments) {
  mkdirSync(rawDir, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
    recordVideo: { dir: rawDir, size: { width: 1440, height: 900 } },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'SIGN IN TO WCAI' }).waitFor({ timeout: 30000 });
  await installVideoChrome(page);
  await page.waitForTimeout(1500);

  for (let index = 0; index < timedSegments.length; index += 1) {
    const segment = timedSegments[index];
    const fullScreen = segment.action === 'intro' || segment.action === 'outro';
    if (segment.action === 'outro') await caption(page, segment.title, segment.subtitle, true);
    else await caption(page, segment.title, segment.subtitle, fullScreen);

    const start = Date.now();
    console.log(`Recording segment ${index + 1}/${timedSegments.length}: ${segment.action}`);
    try {
      await perform(page, segment.action);
    } catch (error) {
      console.warn(`Segment ${index + 1} (${segment.action}) continued after an optional UI step failed:`, error.message);
      const requiredActions = new Set(['login', 'access', 'playerIntel', 'conversation', 'lineup', 'mcpResult', 'analytics', 'matchday', 'tacticalLab', 'tournament', 'squadIntel', 'ledger', 'execute']);
      if (requiredActions.has(segment.action)) throw error;
    }
    if (segment.action === 'intro') await page.waitForTimeout(500);
    const target = Math.round((segment.duration + 0.75) * 1000);
    const remaining = Math.max(600, target - (Date.now() - start));
    await page.waitForTimeout(remaining);
    if (!fullScreen) await closeCaption(page);
  }

  const video = page.video();
  await page.close();
  const rawPath = await video.path();
  await context.close();
  await browser.close();
  return rawPath;
}

function renderFinal(rawVideo, narrationTrack) {
  run(ffmpegPath, [
    '-y', '-i', rawVideo, '-i', narrationTrack,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', outputPath,
  ]);
  run(ffmpegPath, ['-y', '-ss', '00:00:04', '-i', outputPath, '-frames:v', '1', '-update', '1', '-vf', 'scale=1280:-1', thumbnailPath]);
}

mkdirSync(generated, { recursive: true });
if (existsSync(rawDir)) rmSync(rawDir, { recursive: true, force: true });
for (const url of ['http://localhost:8000/health', 'http://localhost:3000', 'http://localhost:3000/tournament', 'http://localhost:3000/transactions']) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Demo preflight failed: ${url} returned ${response.status}`);
}
const timedSegments = synthesizeNarration();
const narrationTrack = buildNarrationTrack(timedSegments);
const rawVideo = await record(timedSegments);
renderFinal(rawVideo, narrationTrack);

const megabytes = (statSync(outputPath).size / 1024 / 1024).toFixed(1);
console.log(`Created ${outputPath} (${megabytes} MB)`);
console.log(`Created ${thumbnailPath}`);
