/**
 * Format a number as currency (PoorUp uses $)
 */
export function formatMoney(amount) {
  if (amount === null || amount === undefined) return '$0';
  const num = Number(amount);
  if (isNaN(num)) return '$0';
  const sign = num < 0 ? '-' : '';
  const absolute = Math.abs(num);
  if (absolute >= 1_000_000) {
    return `${sign}$${(absolute / 1_000_000).toFixed(2)}M`;
  }
  if (absolute >= 1_000) {
    return `${sign}$${(absolute / 1_000).toFixed(1)}K`;
  }
  return `${sign}$${Math.round(absolute).toLocaleString()}`;
}

export function formatExactMoney(amount) {
  if (amount === null || amount === undefined) return '$0.00';
  const num = Number(amount);
  if (isNaN(num)) return '$0.00';
  const sign = num < 0 ? '-' : '';
  return `${sign}$${Math.abs(num).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Format a timestamp (ISO string or Date) as HH:MM:SS
 */
export function formatTimestamp(ts) {
  if (!ts) return '';
  const d = typeof ts === 'string' ? new Date(ts) : ts;
  if (isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('en-US', { hour12: false });
}

/**
 * Format a timestamp as relative time (e.g. "2m ago")
 */
export function formatRelativeTime(ts) {
  if (!ts) return '';
  const d = typeof ts === 'string' ? new Date(ts) : ts;
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return `${Math.floor(diffSec / 3600)}h ago`;
}

/**
 * Format inflation rate as percentage string
 */
export function formatInflation(rate) {
  if (rate === null || rate === undefined) return '0.0%';
  return `${(Number(rate) * 100).toFixed(1)}%`;
}

/**
 * Format a number as a short string (for balances etc.)
 */
export function formatShort(num) {
  const n = Number(num);
  if (isNaN(n)) return '0';
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

/**
 * Pad a number with leading zeros to a fixed length
 */
export function padZero(num, length = 2) {
  return String(num).padStart(length, '0');
}

/**
 * Format seconds into MM:SS countdown string
 */
export function formatCountdown(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return '00:00';
  const s = Math.max(0, Math.floor(seconds));
  return `${padZero(Math.floor(s / 60))}:${padZero(s % 60)}`;
}

/**
 * Calculate net worth for a player given the properties object (keyed by position or array).
 * Mirrors the backend formula: balance + prop_value - mortgage_debt
 */
export function calculateNetWorth(player, properties) {
  const balance = parseFloat(player.balance || 0);
  const props = Array.isArray(properties)
    ? properties.filter(p => p.owner_id === player.id)
    : Object.values(properties || {}).filter(p => p.owner_id === player.id);

  const propValue = props
    .filter(p => !p.is_mortgaged)
    .reduce((sum, p) => sum + parseFloat(p.current_value || p.base_price || 0) + (p.dev_level || 0) * 50, 0);

  const mortgageDebt = props
    .filter(p => p.is_mortgaged)
    .reduce((sum, p) => sum + parseFloat(p.base_price || 0) * 0.5, 0);

  return Math.round(balance + propValue - mortgageDebt);
}
