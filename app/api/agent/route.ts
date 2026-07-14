import { NextResponse } from 'next/server';
import playersData from '@/data/worldcup_players.json';
import type { Player, SuggestedAction, AgentResponse } from '@/types';

// ─── Agent Skills ──────────────────────────────────────────────────────────────

const players: Player[] = playersData as Player[];

function findPlayerByName(query: string): Player | undefined {
  const q = query.toLowerCase();
  return players.find(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      q.includes(p.name.split(' ').pop()!.toLowerCase())
  );
}

function findPlayersByPosition(position: Player['position']): Player[] {
  return players.filter((p) => p.position === position && p.isAvailable);
}

function findPlayerById(id: string): Player | undefined {
  return players.find((p) => p.id === id);
}

function findMentionedPlayers(prompt: string): Player[] {
  const promptLower = prompt.toLowerCase();
  return players.filter((p) => {
    const lastName = p.name.split(' ').pop()!.toLowerCase();
    const fullName = p.name.toLowerCase();
    return promptLower.includes(lastName) || promptLower.includes(fullName);
  });
}

function detectPositionFromPrompt(prompt: string): Player['position'] | null {
  const p = prompt.toLowerCase();
  if (p.includes('goalkeeper') || p.includes(' gk') || p.includes('keeper')) return 'GK';
  if (p.includes('defender') || p.includes('defense') || p.includes('centre-back') || p.includes('fullback') || p.includes('right-back') || p.includes('left-back') || p.includes(' df') || p.includes('backline')) return 'DF';
  if (p.includes('midfielder') || p.includes('midfield') || p.includes(' mf') || p.includes('central mid') || p.includes('box-to-box')) return 'MF';
  if (p.includes('forward') || p.includes('striker') || p.includes('attacker') || p.includes('winger') || p.includes(' fw')) return 'FW';
  return null;
}

function analyzeBestTransfer(
  squadPlayerIds: string[],
  prompt: string
): { sell: Player; buy: Player; reasoning: string } | null {
  const squadPlayers = squadPlayerIds
    .map((id) => findPlayerById(id))
    .filter((p): p is Player => p !== undefined);

  if (squadPlayers.length === 0) return null;

  const nonSquadPlayers = players.filter(
    (p) => !squadPlayerIds.includes(p.id) && p.isAvailable
  );

  if (nonSquadPlayers.length === 0) return null;

  // Detect if the prompt targets a specific position
  const targetPosition = detectPositionFromPrompt(prompt);

  // Find the weakest player in the squad (or in the targeted position)
  const candidates = targetPosition
    ? squadPlayers.filter((p) => p.position === targetPosition)
    : squadPlayers;

  if (candidates.length === 0) return null;

  const weakest = candidates.reduce((worst, p) =>
    p.points < worst.points ? p : worst
  );

  // Find the best available replacement at the same position
  const replacements = nonSquadPlayers.filter(
    (p) => p.position === weakest.position
  );

  if (replacements.length === 0) return null;

  const bestReplacement = replacements.reduce((best, p) =>
    p.points > best.points ? p : best
  );

  // Only suggest if the replacement is actually better
  if (bestReplacement.points <= weakest.points) return null;

  const priceDiff = bestReplacement.price - weakest.price;
  const priceDiffStr =
    priceDiff > 0
      ? `This move costs an additional ${priceDiff.toFixed(1)}M`
      : priceDiff < 0
        ? `This move frees up ${Math.abs(priceDiff).toFixed(1)}M in budget`
        : 'This is a like-for-like price swap';

  const reasoning =
    `Sell ${weakest.name} (${weakest.points} pts, ${weakest.price}M) → Buy ${bestReplacement.name} (${bestReplacement.points} pts, ${bestReplacement.price}M). ` +
    `${bestReplacement.name} offers a ${bestReplacement.points - weakest.points}-point upgrade based on current tournament form. ` +
    `${priceDiffStr}. ` +
    `xG differential: ${bestReplacement.premium_stats.xg_per_game.toFixed(2)} vs ${weakest.premium_stats.xg_per_game.toFixed(2)} per game. ` +
    `${bestReplacement.premium_stats.scout_note.split('.')[0]}.`;

  return { sell: weakest, buy: bestReplacement, reasoning };
}

function validateSquadBudget(squadPlayerIds: string[], maxBudget: number = 100): { total: number; remaining: number; isValid: boolean } {
  const total = squadPlayerIds.reduce((sum, id) => {
    const player = findPlayerById(id);
    return sum + (player?.price ?? 0);
  }, 0);
  return { total, remaining: maxBudget - total, isValid: total <= maxBudget };
}

// ─── Response Builders ─────────────────────────────────────────────────────────

function buildFreeResponse(prompt: string, squadPlayerIds: string[]): AgentResponse {
  const mentioned = findMentionedPlayers(prompt);
  const position = detectPositionFromPrompt(prompt);
  const promptLower = prompt.toLowerCase();

  // Handle greetings
  if (promptLower.match(/^(hi|hello|hey|sup|yo|greetings)/)) {
    return {
      message:
        "Hey gaffer! 👋 I'm your Auto-Gaffer AI assistant. I can help you build your World Cup 2026 squad with tactical analysis, transfer advice, and player comparisons. Ask me about any player, position, or your squad composition. For premium scouting reports with xG data, injury risk analysis, and one-click transfer suggestions — unlock X402 Premium.",
      isPremium: false,
    };
  }

  // Handle squad analysis
  if (promptLower.includes('squad') || promptLower.includes('team') || promptLower.includes('lineup')) {
    const squadPlayers = squadPlayerIds
      .map((id) => findPlayerById(id))
      .filter((p): p is Player => p !== undefined);

    if (squadPlayers.length === 0) {
      return {
        message:
          "Your squad is empty, gaffer. Head to the pitch board and start picking players to fill your formation. I'd recommend starting with a premium forward — they tend to be the biggest points differentiators at World Cup level. Once you've got a few players in, come back and I'll give you tactical advice.",
        isPremium: false,
      };
    }

    const totalPoints = squadPlayers.reduce((sum, p) => sum + p.points, 0);
    const budget = validateSquadBudget(squadPlayerIds);
    const positionCounts = { GK: 0, DF: 0, MF: 0, FW: 0 };
    squadPlayers.forEach((p) => positionCounts[p.position]++);

    return {
      message:
        `📋 **Squad Overview**\n\n` +
        `Total Points: **${totalPoints}** | Budget Used: **${budget.total.toFixed(1)}M** | Remaining: **${budget.remaining.toFixed(1)}M**\n\n` +
        `Formation breakdown: ${positionCounts.GK} GK, ${positionCounts.DF} DF, ${positionCounts.MF} MF, ${positionCounts.FW} FW\n\n` +
        `Your squad has a ${totalPoints > 200 ? 'strong' : totalPoints > 100 ? 'decent' : 'developing'} core. ` +
        `${positionCounts.FW < 2 ? 'You could use more firepower up front. ' : ''}` +
        `${positionCounts.DF < 3 ? 'Your backline looks light — consider adding defensive cover. ' : ''}` +
        `For detailed scouting reports and AI-powered transfer recommendations, upgrade to Premium.`,
      isPremium: false,
    };
  }

  // Handle player-specific queries
  if (mentioned.length > 0) {
    const player = mentioned[0];
    return {
      message:
        `⚽ **${player.name}** | ${player.position} | ${player.team}\n\n` +
        `Price: **${player.price}M** | Points: **${player.points}** | Status: ${player.isAvailable ? '✅ Available' : '🚑 Unavailable'}\n\n` +
        `${player.name} is ${player.points >= 70 ? 'an elite-tier pick' : player.points >= 50 ? 'a solid mid-range option' : 'a budget selection'} at the ${player.position} position. ` +
        `${player.isAvailable ? 'He is fit and available for selection.' : '⚠️ He is currently unavailable — check back closer to matchday.'} ` +
        `Want deeper analysis with xG data, injury risk assessment, and scouting intel? Unlock Premium with X402.`,
      isPremium: false,
    };
  }

  // Handle position queries
  if (position) {
    const positionPlayers = findPlayersByPosition(position);
    const sorted = positionPlayers.sort((a, b) => b.points - a.points);
    const top3 = sorted.slice(0, 3);
    const posNames: Record<string, string> = { GK: 'Goalkeepers', DF: 'Defenders', MF: 'Midfielders', FW: 'Forwards' };

    return {
      message:
        `📊 **Top ${posNames[position]}**\n\n` +
        top3
          .map(
            (p, i) =>
              `${i + 1}. **${p.name}** (${p.team}) — ${p.points} pts, ${p.price}M`
          )
          .join('\n') +
        `\n\nThese are the highest-scoring available ${posNames[position].toLowerCase()} in the tournament. ` +
        `Price doesn't always equal value — consider form, fixtures, and minutes. ` +
        `Unlock Premium for xG breakdowns, injury risk flags, and personalised transfer suggestions.`,
      isPremium: false,
    };
  }

  // Handle transfer / advice queries
  if (promptLower.includes('transfer') || promptLower.includes('swap') || promptLower.includes('replace') || promptLower.includes('upgrade') || promptLower.includes('improve')) {
    return {
      message:
        "Looking to strengthen your squad? Good instinct, gaffer. In the free tier, I can tell you that the key to World Cup fantasy is balancing premium attackers with budget defenders who have clean sheet potential. " +
        "Don't over-invest in goalkeepers — the points differential between a 5.5M and 6.0M keeper is marginal. " +
        "For specific transfer recommendations with sell/buy suggestions and the reasoning behind each move, unlock Premium via X402.",
      isPremium: false,
    };
  }

  // Default
  return {
    message:
      "Good question, gaffer. I can help you with player analysis, squad composition, position rankings, and transfer strategy for the 2026 World Cup. " +
      "Try asking me about a specific player (e.g. 'Tell me about Mbappe'), a position (e.g. 'Best midfielders'), or your squad. " +
      "For premium scouting intel with xG stats, injury reports, and AI-generated transfer actions — unlock X402 Premium.",
    isPremium: false,
  };
}

function buildPremiumResponse(prompt: string, squadPlayerIds: string[]): AgentResponse {
  const mentioned = findMentionedPlayers(prompt);
  const position = detectPositionFromPrompt(prompt);
  const promptLower = prompt.toLowerCase();

  // Handle squad analysis (premium)
  if (promptLower.includes('squad') || promptLower.includes('team') || promptLower.includes('lineup') || promptLower.includes('analyse') || promptLower.includes('analyze')) {
    const squadPlayers = squadPlayerIds
      .map((id) => findPlayerById(id))
      .filter((p): p is Player => p !== undefined);

    if (squadPlayers.length === 0) {
      return {
        message:
          "🔓 **Premium Analysis** — Your squad is empty. Let me help you build from scratch.\n\n" +
          "Based on the current tournament data, here's my recommended skeleton:\n\n" +
          "• **GK**: Donnarumma (5.5M) — best value keeper, Italy's defensive structure is solid.\n" +
          "• **DF**: Saliba (6.5M) + Alexander-Arnold (7.0M) — clean sheet floor + attacking ceiling.\n" +
          "• **MF**: Bellingham (11.0M) — non-negotiable, highest floor among all midfielders.\n" +
          "• **FW**: Mbappe (13.0M) + Lamine Yamal (10.0M) — the premium strike partnership.\n\n" +
          "Start there and fill the gaps with budget picks. Total: ~53.5M, leaving room for depth.",
        isPremium: true,
      };
    }

    const budget = validateSquadBudget(squadPlayerIds);
    const totalPoints = squadPlayers.reduce((sum, p) => sum + p.points, 0);
    const avgXg =
      squadPlayers.reduce((sum, p) => sum + p.premium_stats.xg_per_game, 0) /
      squadPlayers.length;
    const highRiskPlayers = squadPlayers.filter(
      (p) => p.premium_stats.injury_risk === 'High'
    );

    let message =
      `🔓 **Premium Squad Analysis**\n\n` +
      `📈 Total Points: **${totalPoints}** | Avg xG/game: **${avgXg.toFixed(3)}** | Budget: **${budget.total.toFixed(1)}M / ${budget.remaining.toFixed(1)}M remaining**\n\n`;

    if (highRiskPlayers.length > 0) {
      message +=
        `⚠️ **Injury Alert**: ${highRiskPlayers.map((p) => p.name).join(', ')} ${highRiskPlayers.length === 1 ? 'carries' : 'carry'} HIGH injury risk. ` +
        `Consider having replacements ready on your bench.\n\n`;
    }

    message += `**Player-by-Player Breakdown:**\n`;
    squadPlayers.forEach((p) => {
      message += `\n• **${p.name}** (${p.position}, ${p.team}) — ${p.points} pts, ${p.premium_stats.xg_per_game.toFixed(2)} xG/g, Risk: ${p.premium_stats.injury_risk}\n  _${p.premium_stats.scout_note.split('.')[0]}._`;
    });

    // Generate transfer suggestion
    const transfer = analyzeBestTransfer(squadPlayerIds, prompt);

    if (transfer) {
      const suggestedAction: SuggestedAction = {
        type: 'transfer',
        sellPlayerId: transfer.sell.id,
        buyPlayerId: transfer.buy.id,
        reasoning: transfer.reasoning,
      };

      message += `\n\n🔄 **Recommended Transfer:**\n${transfer.reasoning}`;

      return { message, suggestedAction, isPremium: true };
    }

    return { message, isPremium: true };
  }

  // Handle player-specific queries (premium)
  if (mentioned.length > 0) {
    const player = mentioned[0];
    let message =
      `🔓 **Premium Scouting Report: ${player.name}**\n\n` +
      `| Metric | Value |\n|---|---|\n` +
      `| Position | ${player.position} |\n` +
      `| Team | ${player.team} |\n` +
      `| Price | ${player.price}M |\n` +
      `| Points | ${player.points} |\n` +
      `| xG / Game | ${player.premium_stats.xg_per_game.toFixed(2)} |\n` +
      `| Injury Risk | ${player.premium_stats.injury_risk} |\n` +
      `| Availability | ${player.isAvailable ? '✅ Fit' : '🚑 Out'} |\n\n` +
      `**Scout's Assessment:**\n${player.premium_stats.scout_note}\n\n`;

    // Compare with alternatives
    const alternatives = players
      .filter(
        (p) =>
          p.position === player.position &&
          p.id !== player.id &&
          p.isAvailable
      )
      .sort((a, b) => b.points - a.points)
      .slice(0, 2);

    if (alternatives.length > 0) {
      message += `**Positional Alternatives:**\n`;
      alternatives.forEach((alt) => {
        const diff = alt.points - player.points;
        message += `• ${alt.name} (${alt.price}M, ${alt.points} pts, ${alt.premium_stats.xg_per_game.toFixed(2)} xG/g) — ${diff > 0 ? `+${diff} pts advantage` : diff < 0 ? `${diff} pts behind` : 'level on points'}\n`;
      });
    }

    // Suggest transfer if the player is in the squad and there's someone better
    const inSquad = squadPlayerIds.includes(player.id);
    if (inSquad && alternatives.length > 0 && alternatives[0].points > player.points) {
      const best = alternatives[0];
      const suggestedAction: SuggestedAction = {
        type: 'transfer',
        sellPlayerId: player.id,
        buyPlayerId: best.id,
        reasoning:
          `Upgrade from ${player.name} to ${best.name}: +${best.points - player.points} points, xG improvement of ${(best.premium_stats.xg_per_game - player.premium_stats.xg_per_game).toFixed(2)} per game. ` +
          `${best.premium_stats.scout_note.split('.')[0]}.`,
      };
      message += `\n🔄 **Suggested Upgrade Available** — I recommend swapping ${player.name} for ${best.name}.`;
      return { message, suggestedAction, isPremium: true };
    }

    if (!inSquad && player.isAvailable) {
      // Player not in squad — suggest adding by replacing weakest at that position
      const weakestInSquad = squadPlayerIds
        .map((id) => findPlayerById(id))
        .filter((p): p is Player => p !== undefined && p.position === player.position)
        .sort((a, b) => a.points - b.points)[0];

      if (weakestInSquad && player.points > weakestInSquad.points) {
        const suggestedAction: SuggestedAction = {
          type: 'transfer',
          sellPlayerId: weakestInSquad.id,
          buyPlayerId: player.id,
          reasoning:
            `Bring in ${player.name} for ${weakestInSquad.name}: +${player.points - weakestInSquad.points} points upgrade. ` +
            `Price change: ${weakestInSquad.price}M → ${player.price}M (${player.price > weakestInSquad.price ? '+' : ''}${(player.price - weakestInSquad.price).toFixed(1)}M). ` +
            `${player.premium_stats.scout_note.split('.')[0]}.`,
        };
        message += `\n🔄 **Transfer Suggestion** — Sell ${weakestInSquad.name} to fund ${player.name}.`;
        return { message, suggestedAction, isPremium: true };
      }
    }

    return { message, isPremium: true };
  }

  // Handle position queries (premium)
  if (position) {
    const positionPlayers = findPlayersByPosition(position);
    const sorted = positionPlayers.sort((a, b) => b.points - a.points);
    const posNames: Record<string, string> = { GK: 'Goalkeepers', DF: 'Defenders', MF: 'Midfielders', FW: 'Forwards' };

    let message = `🔓 **Premium ${posNames[position]} Rankings**\n\n`;

    sorted.forEach((p, i) => {
      message +=
        `${i + 1}. **${p.name}** (${p.team}) — ${p.points} pts, ${p.price}M\n` +
        `   xG: ${p.premium_stats.xg_per_game.toFixed(2)}/g | Risk: ${p.premium_stats.injury_risk}\n` +
        `   _${p.premium_stats.scout_note.split('.')[0]}._\n\n`;
    });

    // Best value pick
    const bestValue = [...sorted].sort(
      (a, b) => b.points / b.price - a.points / a.price
    )[0];
    message += `💡 **Best Value**: ${bestValue.name} at ${(bestValue.points / bestValue.price).toFixed(1)} pts/M — highest points-per-million in the ${posNames[position].toLowerCase()} bracket.`;

    // Suggest transfer for this position
    const transfer = analyzeBestTransfer(squadPlayerIds, prompt);
    if (transfer) {
      const suggestedAction: SuggestedAction = {
        type: 'transfer',
        sellPlayerId: transfer.sell.id,
        buyPlayerId: transfer.buy.id,
        reasoning: transfer.reasoning,
      };
      return { message, suggestedAction, isPremium: true };
    }

    return { message, isPremium: true };
  }

  // Handle transfer / upgrade queries (premium)
  if (promptLower.includes('transfer') || promptLower.includes('swap') || promptLower.includes('replace') || promptLower.includes('upgrade') || promptLower.includes('improve') || promptLower.includes('suggest') || promptLower.includes('recommend')) {
    const transfer = analyzeBestTransfer(squadPlayerIds, prompt);

    if (transfer) {
      const suggestedAction: SuggestedAction = {
        type: 'transfer',
        sellPlayerId: transfer.sell.id,
        buyPlayerId: transfer.buy.id,
        reasoning: transfer.reasoning,
      };

      return {
        message:
          `🔓 **Premium Transfer Recommendation**\n\n` +
          `After analysing your squad's xG distribution, injury exposure, and points trajectory, here's my top suggestion:\n\n` +
          `${transfer.reasoning}\n\n` +
          `This transfer optimises your squad's expected output while managing injury risk. Click "Apply" to execute.`,
        suggestedAction,
        isPremium: true,
      };
    }

    return {
      message:
        "🔓 **Premium Transfer Analysis**\n\n" +
        "I've analysed your squad and couldn't identify a clear upgrade at this time — your current lineup looks well-optimised. " +
        "Keep monitoring form and injury news as the group stages progress. " +
        "Try asking about a specific position or player for targeted recommendations.",
      isPremium: true,
    };
  }

  // Default premium
  const transfer = analyzeBestTransfer(squadPlayerIds, prompt);
  if (transfer) {
    const suggestedAction: SuggestedAction = {
      type: 'transfer',
      sellPlayerId: transfer.sell.id,
      buyPlayerId: transfer.buy.id,
      reasoning: transfer.reasoning,
    };

    return {
      message:
        `🔓 **Premium AI Analysis**\n\n` +
        `Based on your query, I've run a full diagnostic on your squad. Here's what I found:\n\n` +
        `${transfer.reasoning}\n\n` +
        `I can also provide detailed scouting reports on any player — just ask by name, or request position rankings for a deeper look.`,
      suggestedAction,
      isPremium: true,
    };
  }

  return {
    message:
      "🔓 **Premium Access Active**\n\n" +
      "You've got full access to my scouting database, gaffer. I can provide:\n\n" +
      "• **Player Reports** — xG, injury risk, tactical breakdowns\n" +
      "• **Position Rankings** — every position ranked by expected output\n" +
      "• **Transfer Engine** — AI-powered buy/sell recommendations\n" +
      "• **Squad Diagnostics** — budget analysis, risk flags, optimisation\n\n" +
      "Try: 'Analyse my squad', 'Best forwards', 'Tell me about Bellingham', or 'Suggest a transfer'.",
    isPremium: true,
  };
}

// ─── Route Handler ─────────────────────────────────────────────────────────────

interface AgentRequest {
  prompt: string;
  hasPaidX402: boolean;
  squadPlayerIds: string[];
}

export async function POST(request: Request) {
  try {
    // API Route Protection Check
    const authHeader = request.headers.get('authorization');
    if (!authHeader) {
      return NextResponse.json(
        { message: 'Yetkisiz erişim. Oturum açmanız gerekmektedir.' },
        { status: 401 }
      );
    }

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const authRes = await fetch(`${API_URL}/api/auth/me`, {
      headers: { 'Authorization': authHeader }
    });

    if (!authRes.ok) {
      return NextResponse.json(
        { message: 'Oturum geçersiz veya süresi dolmuş. Lütfen tekrar giriş yapın.' },
        { status: 401 }
      );
    }

    const body: AgentRequest = await request.json();
    const { prompt, hasPaidX402, squadPlayerIds } = body;

    if (!prompt || prompt.trim() === '') {
      return NextResponse.json(
        { message: 'Please provide a prompt.', isPremium: false },
        { status: 400 }
      );
    }

    const response: AgentResponse = hasPaidX402
      ? buildPremiumResponse(prompt, squadPlayerIds ?? [])
      : buildFreeResponse(prompt, squadPlayerIds ?? []);

    return NextResponse.json(response);
  } catch {
    return NextResponse.json(
      { message: 'Invalid request body.', isPremium: false },
      { status: 400 }
    );
  }
}
