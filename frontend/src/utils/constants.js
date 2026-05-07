export const PLAYER_COLORS = [
  "#E63946", "#2196F3", "#4CAF50", "#FF9800", "#9C27B0",
  "#00BCD4", "#F44336", "#FFEB3B", "#795548", "#607D8B"
];

export const BOARD_SPACES = [
  { position: 0, name: "START", type: "start" },
  { position: 2, name: "Nairobi", type: "property", region: "Africa", groupColor: "#8B4513", basePrice: 60 },
  { position: 4, name: "Cairo", type: "property", region: "Africa", groupColor: "#8B4513", basePrice: 100 },
  { position: 5, name: "Income Tax", type: "tax" },
  { position: 6, name: "BOM", type: "transit", groupColor: "#6B7280", basePrice: 200 },
  { position: 9, name: "Karachi", type: "property", region: "South Asia", groupColor: "#EC4899", basePrice: 120 },
  { position: 10, name: "Dhaka", type: "property", region: "South Asia", groupColor: "#EC4899", basePrice: 140 },
  { position: 11, name: "Jail / Just Visiting", type: "jail" },
  { position: 12, name: "Istanbul", type: "property", region: "Middle East", groupColor: "#F59E0B", basePrice: 140 },
  { position: 13, name: "Tehran", type: "property", region: "Middle East", groupColor: "#F59E0B", basePrice: 160 },
  { position: 14, name: "Riyadh", type: "property", region: "Middle East", groupColor: "#F59E0B", basePrice: 180 },
  { position: 15, name: "DXB", type: "transit", groupColor: "#6B7280", basePrice: 200 },
  { position: 16, name: "Moscow", type: "property", region: "Eastern Europe", groupColor: "#DC2626", basePrice: 180 },
  { position: 17, name: "Community Chest", type: "community_chest" },
  { position: 18, name: "St. Petersburg", type: "property", region: "Eastern Europe", groupColor: "#DC2626", basePrice: 200 },
  { position: 19, name: "Kiev", type: "property", region: "Eastern Europe", groupColor: "#DC2626", basePrice: 220 },
  { position: 20, name: "Free Space", type: "free" },
  { position: 22, name: "Chance", type: "chance" },
  { position: 23, name: "Paris", type: "property", region: "Western Europe", groupColor: "#EAB308", basePrice: 240 },
  { position: 24, name: "London", type: "property", region: "Western Europe", groupColor: "#EAB308", basePrice: 260 },
  { position: 25, name: "LHR", type: "transit", groupColor: "#6B7280", basePrice: 200 },
  { position: 26, name: "Shanghai", type: "property", region: "China", groupColor: "#F97316", basePrice: 260 },
  { position: 27, name: "Beijing", type: "property", region: "China", groupColor: "#F97316", basePrice: 280 },
  { position: 30, name: "Go To Jail", type: "go_to_jail" },
  { position: 31, name: "Tokyo", type: "property", region: "Oceania", groupColor: "#06B6D4", basePrice: 300 },
  { position: 32, name: "Seoul", type: "property", region: "Oceania", groupColor: "#06B6D4", basePrice: 320 },
  { position: 34, name: "Sydney", type: "property", region: "Oceania", groupColor: "#06B6D4", basePrice: 320 },
  { position: 36, name: "JFK", type: "transit", groupColor: "#6B7280", basePrice: 200 },
  { position: 37, name: "São Paulo", type: "property", region: "Americas", groupColor: "#16A34A", basePrice: 350 },
  { position: 38, name: "Buenos Aires", type: "property", region: "Americas", groupColor: "#16A34A", basePrice: 370 },
  { position: 39, name: "Luxury Tax", type: "tax" },
  { position: 40, name: "New York", type: "property", region: "Americas", groupColor: "#16A34A", basePrice: 400 },
  { position: 47, name: "Super Tax", type: "tax" },
];

export const BOARD_POSITION_ORDER = BOARD_SPACES.map((space) => space.position);

export const LOG_EVENT_COLORS = {
  dice_roll: "text-gray-400",
  move: "text-gray-400",
  turn_timeout: "text-amber-300",
  rent_collected: "text-red-400",
  property_purchased: "text-blue-400",
  auction_won: "text-blue-400",
  income_tax: "text-orange-400",
  property_tax: "text-orange-400",
  turn_tax: "text-orange-400",
  luxury_tax: "text-orange-400",
  super_tax: "text-orange-400",
  welfare_paid: "text-green-400",
  welfare_failed: "text-red-500",
  lobby_pending: "text-indigo-300",
  trade_proposed: "text-yellow-400",
  trade_completed: "text-green-400",
  trade_rejected: "text-gray-400",
  deal_proposed: "text-emerald-300",
  deal_countered: "text-cyan-300",
  deal_accepted: "text-green-400",
  deal_rejected: "text-gray-400",
  deal_cancelled: "text-gray-400",
  deal_expired: "text-rose-400",
  deal_immunity_applied: "text-emerald-400",
  deal_discount_applied: "text-sky-400",
  deal_investment_spent: "text-amber-300",
  deal_profit_paid: "text-amber-200",
  lobby_success: "text-purple-400",
  lobby_failed: "text-gray-400",
  uprising: "text-red-600 font-bold",
  bankruptcy: "text-red-800 font-bold",
  hyper_inflation: "text-red-500 animate-pulse",
  chance_card: "text-yellow-400",
  community_chest: "text-yellow-400",
  jail_sent: "text-orange-400",
  jail_released: "text-gray-400",
};

export const GOVERNMENT_TYPES = {
  minarchism: {
    label: "Minarchism",
    description: "Minimal government with no lobbying, no welfare, and low taxes.",
  },
  liberal_democracy: {
    label: "Liberal Democracy",
    description: "Corporate ownership, jobs, markets, bank accounts, and tax-bracket politics decide the last player standing.",
  },
  social_democracy: {
    label: "Social Democracy",
    description: "Higher welfare and redistribution with higher property taxes.",
  },
};

export const GAME_MODES = {
  standard: { label: "Standard", description: "Normal rules and pacing." },
  speed: { label: "Speed", description: "Shorter game with faster escalation." },
  chaos: { label: "Chaos", description: "More social crises and faster unrest spread." },
  cooperative: { label: "Cooperative", description: "More deal-making and fewer hard negotiation blocks." },
};

export const SPACE_ICONS = {
  start: "🏁",
  jail: "🚔",
  free: "🅿️",
  go_to_jail: "⛓️",
  chance: "🎲",
  community_chest: "🎁",
  tax: "🧾",
  transit: "",
};

export const BOARD_SPACE_SHORT_NAMES = {
  11: 'Jail',
  15: 'DXB',
  17: 'Chest',
  18: 'St. Pete',
  25: 'LHR',
  30: 'Go To Jail',
  36: 'JFK',
};

// Light color detection — if luminance is high, use dark text
export function needsDarkText(hexColor) {
  if (!hexColor) return false;
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  // Perceived luminance
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6;
}
