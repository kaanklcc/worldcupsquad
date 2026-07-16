export type TeamTheme = {
  primary: string;
  secondary: string;
  accent: string;
  ink: string;
};

// National-colour palettes are presentation metadata only. They intentionally
// live in one shared registry so pitch cards, scout cards and player intel do
// not drift apart as new FIFA squads are added.
const THEMES: Record<string, TeamTheme> = {
  Algeria: { primary: '#006233', secondary: '#ffffff', accent: '#d21034', ink: '#062d20' },
  Argentina: { primary: '#75aadb', secondary: '#ffffff', accent: '#f6b40e', ink: '#0b3b5b' },
  Australia: { primary: '#00843d', secondary: '#ffcd00', accent: '#ffffff', ink: '#063c27' },
  Austria: { primary: '#ed2939', secondary: '#ffffff', accent: '#ed2939', ink: '#550b14' },
  Belgium: { primary: '#171717', secondary: '#fdda24', accent: '#ef3340', ink: '#111111' },
  'Bosnia And Herzegovina': { primary: '#002395', secondary: '#f6c700', accent: '#ffffff', ink: '#061850' },
  Brazil: { primary: '#009b3a', secondary: '#ffdf00', accent: '#002776', ink: '#052d20' },
  'Cabo Verde': { primary: '#003893', secondary: '#ffffff', accent: '#cf2027', ink: '#071c52' },
  Canada: { primary: '#d80621', secondary: '#ffffff', accent: '#d80621', ink: '#5c0713' },
  Colombia: { primary: '#fcd116', secondary: '#003893', accent: '#ce1126', ink: '#2f2600' },
  'Congo DR': { primary: '#007fff', secondary: '#f7d618', accent: '#ce1126', ink: '#061f4c' },
  "Cote D'Ivoire": { primary: '#f77f00', secondary: '#ffffff', accent: '#009e60', ink: '#512400' },
  "Côte D'Ivoire": { primary: '#f77f00', secondary: '#ffffff', accent: '#009e60', ink: '#512400' },
  Croatia: { primary: '#ef3340', secondary: '#ffffff', accent: '#171796', ink: '#5a0a15' },
  Curacao: { primary: '#003da5', secondary: '#f9e300', accent: '#ffffff', ink: '#061b54' },
  'Curaçao': { primary: '#003da5', secondary: '#f9e300', accent: '#ffffff', ink: '#061b54' },
  Czechia: { primary: '#ffffff', secondary: '#d7141a', accent: '#11457e', ink: '#172033' },
  Ecuador: { primary: '#fcd116', secondary: '#003893', accent: '#ce1126', ink: '#332900' },
  Egypt: { primary: '#ce1126', secondary: '#ffffff', accent: '#000000', ink: '#550814' },
  England: { primary: '#ffffff', secondary: '#c8102e', accent: '#0b3d91', ink: '#162238' },
  France: { primary: '#002395', secondary: '#ffffff', accent: '#ed2939', ink: '#081b59' },
  Germany: { primary: '#1b1b1b', secondary: '#dd0000', accent: '#ffce00', ink: '#111111' },
  Ghana: { primary: '#ce1126', secondary: '#fcd116', accent: '#006b3f', ink: '#501016' },
  Haiti: { primary: '#00209f', secondary: '#d21034', accent: '#ffffff', ink: '#08154b' },
  'IR Iran': { primary: '#239f40', secondary: '#ffffff', accent: '#da0000', ink: '#073719' },
  Iraq: { primary: '#ce1126', secondary: '#ffffff', accent: '#007a3d', ink: '#4e1016' },
  Japan: { primary: '#ffffff', secondary: '#bc002d', accent: '#1d3b72', ink: '#1a2434' },
  Jordan: { primary: '#111111', secondary: '#ffffff', accent: '#ce1126', ink: '#171717' },
  'Korea Republic': { primary: '#ffffff', secondary: '#cd2e3a', accent: '#0047a0', ink: '#1c2635' },
  Mexico: { primary: '#006847', secondary: '#ffffff', accent: '#ce1126', ink: '#062e22' },
  Morocco: { primary: '#c1272d', secondary: '#006233', accent: '#ffffff', ink: '#500a13' },
  Netherlands: { primary: '#f36c21', secondary: '#ffffff', accent: '#21468b', ink: '#5a2606' },
  'New Zealand': { primary: '#101820', secondary: '#ffffff', accent: '#e4002b', ink: '#101820' },
  Norway: { primary: '#ef2b2d', secondary: '#ffffff', accent: '#002868', ink: '#59080f' },
  Panama: { primary: '#ffffff', secondary: '#005293', accent: '#d21034', ink: '#1b2944' },
  Paraguay: { primary: '#d52b1e', secondary: '#ffffff', accent: '#0038a8', ink: '#55100e' },
  Portugal: { primary: '#006600', secondary: '#ff0000', accent: '#f8d24a', ink: '#06351d' },
  Qatar: { primary: '#8a1538', secondary: '#ffffff', accent: '#8a1538', ink: '#3c0719' },
  'Saudi Arabia': { primary: '#006c35', secondary: '#ffffff', accent: '#c7a529', ink: '#07351f' },
  Scotland: { primary: '#005eb8', secondary: '#ffffff', accent: '#005eb8', ink: '#061f49' },
  Senegal: { primary: '#00853f', secondary: '#fdef42', accent: '#e31b23', ink: '#06371f' },
  'South Africa': { primary: '#007749', secondary: '#ffb81c', accent: '#de3831', ink: '#06351f' },
  Spain: { primary: '#aa151b', secondary: '#f1bf00', accent: '#aa151b', ink: '#520b0f' },
  Sweden: { primary: '#006aa7', secondary: '#fecc00', accent: '#ffffff', ink: '#062b4a' },
  Switzerland: { primary: '#d52b1e', secondary: '#ffffff', accent: '#d52b1e', ink: '#5a0d0b' },
  Tunisia: { primary: '#e70013', secondary: '#ffffff', accent: '#e70013', ink: '#5c0710' },
  Turkiye: { primary: '#e30a17', secondary: '#ffffff', accent: '#e30a17', ink: '#5c0710' },
  'Türkiye': { primary: '#e30a17', secondary: '#ffffff', accent: '#e30a17', ink: '#5c0710' },
  Uruguay: { primary: '#5dade2', secondary: '#ffffff', accent: '#f4d03f', ink: '#0c3d62' },
  USA: { primary: '#3c3b6e', secondary: '#ffffff', accent: '#b22234', ink: '#15152e' },
  Uzbekistan: { primary: '#0099b5', secondary: '#ffffff', accent: '#1eb53a', ink: '#063244' },
};

const FALLBACK: TeamTheme = { primary: '#0f6b51', secondary: '#dfb53b', accent: '#f8fafc', ink: '#062d28' };

export function getTeamTheme(team?: string): TeamTheme {
  return (team && THEMES[team]) || FALLBACK;
}

export function teamGradient(team?: string): string {
  const theme = getTeamTheme(team);
  return `linear-gradient(118deg, ${theme.primary} 0%, ${theme.primary} 43%, ${theme.secondary} 43%, ${theme.secondary} 68%, ${theme.accent} 68%, ${theme.accent} 100%)`;
}
