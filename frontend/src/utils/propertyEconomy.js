import { normalizeGovernmentType } from './gameState';

export const STANDARD_RENT_MULTIPLIERS = { 0: 1, 1: 5, 2: 10, 3: 20, 4: 30, 5: 50 };
export const STANDARD_MAX_DEVELOPMENT_LEVEL = 5;

const MINARCHISM_BASE_HOUSE_LEVEL = 4;
const MINARCHISM_EXTRA_RENT_INCREMENT = 8;
const MINARCHISM_PROGRESSIVE_COST_STEP = 0.35;

function normalizeLevel(level) {
  return Math.max(0, Number(level) || 0);
}

function hasMonopoly(property, properties) {
  if (!property?.owner_id || property.property_type !== 'property') {
    return false;
  }

  const group = Object.values(properties || {}).filter(
    (entry) => entry.property_type === 'property' && entry.group_color === property.group_color,
  );
  if (!group.length) {
    return false;
  }

  return group.every((entry) => entry.owner_id === property.owner_id);
}

export function getGovernmentType(economy = {}) {
  return normalizeGovernmentType(economy?.gov_type || economy?.government_type || 'liberal_democracy');
}

export function isMinarchismEconomy(economy = {}) {
  return getGovernmentType(economy) === 'minarchism';
}

export function getDevelopmentCap(economy = {}) {
  return isMinarchismEconomy(economy) ? null : STANDARD_MAX_DEVELOPMENT_LEVEL;
}

function getInflationMultiplier(economy = {}) {
  return 1 + Math.max(0, Number(economy?.inflation_rate || 0));
}

export function isFullyDeveloped(level, economy = {}) {
  const cap = getDevelopmentCap(economy);
  return cap != null && normalizeLevel(level) >= cap;
}

export function getRentMultiplier(level, economy = {}) {
  const developmentLevel = normalizeLevel(level);
  if (!isMinarchismEconomy(economy)) {
    return STANDARD_RENT_MULTIPLIERS[developmentLevel] ?? STANDARD_RENT_MULTIPLIERS[STANDARD_MAX_DEVELOPMENT_LEVEL];
  }

  if (developmentLevel <= MINARCHISM_BASE_HOUSE_LEVEL) {
    return STANDARD_RENT_MULTIPLIERS[developmentLevel] ?? 1;
  }

  return STANDARD_RENT_MULTIPLIERS[MINARCHISM_BASE_HOUSE_LEVEL] + ((developmentLevel - MINARCHISM_BASE_HOUSE_LEVEL) * MINARCHISM_EXTRA_RENT_INCREMENT);
}

export function calculateDevelopmentCost(basePrice, targetLevel, economy = {}) {
  const baseCost = Math.round((Number(basePrice || 0) * 0.5) * 100) / 100;
  const level = Math.max(1, Number(targetLevel) || 1);
  const inflationMultiplier = getInflationMultiplier(economy);
  if (!isMinarchismEconomy(economy) || level <= MINARCHISM_BASE_HOUSE_LEVEL) {
    return Math.round(baseCost * inflationMultiplier * 100) / 100;
  }

  const extraHouses = level - MINARCHISM_BASE_HOUSE_LEVEL;
  const progressiveFactor = (extraHouses * (extraHouses + 1)) / 2;
  return Math.round(baseCost * (1 + (MINARCHISM_PROGRESSIVE_COST_STEP * progressiveFactor)) * inflationMultiplier * 100) / 100;
}

export function calculateDevelopmentRefund(basePrice, currentLevel, economy = {}) {
  const level = normalizeLevel(currentLevel);
  if (level <= 0) {
    return 0;
  }
  return Math.round(calculateDevelopmentCost(basePrice, level, economy) * 0.5 * 100) / 100;
}

export function getDevelopmentLabel(level, economy = {}) {
  const developmentLevel = normalizeLevel(level);
  if (developmentLevel <= 0) {
    return 'No houses';
  }
  if (!isMinarchismEconomy(economy) && developmentLevel >= STANDARD_MAX_DEVELOPMENT_LEVEL) {
    return '4 houses + hotel';
  }
  if (developmentLevel === 1) {
    return '1 house';
  }
  return `${developmentLevel} houses`;
}

export function getBoardDevelopmentDisplay(level, economy = {}) {
  const developmentLevel = normalizeLevel(level);
  if (developmentLevel <= 0) {
    return { houses: 0, hasHotel: false, extraHouses: 0 };
  }
  if (!isMinarchismEconomy(economy) && developmentLevel >= STANDARD_MAX_DEVELOPMENT_LEVEL) {
    return { houses: 4, hasHotel: true, extraHouses: 0 };
  }
  return {
    houses: Math.min(developmentLevel, 4),
    hasHotel: false,
    extraHouses: Math.max(0, developmentLevel - 4),
  };
}

export function calculatePropertyRent(property, properties, economy = {}, levelOverride = null) {
  if (!property?.base_price) {
    return 0;
  }
  if (property.social_unionized || ['strike', 'uprising', 'revolution'].includes(property.social_incident_type)) {
    return 0;
  }

  if (property.property_type === 'transit') {
    const transitCount = Object.values(properties || {}).filter(
      (entry) => entry.property_type === 'transit' && entry.owner_id === property.owner_id,
    ).length;
    return { 1: 25, 2: 50, 3: 100, 4: 200 }[transitCount || 1] || 25;
  }

  const developmentLevel = levelOverride == null
    ? normalizeLevel(property.dev_level ?? property.development_level)
    : normalizeLevel(levelOverride);
  const baseRent = Number(property.base_price || property.current_value || 0) * 0.1;
  let rent = baseRent * getRentMultiplier(developmentLevel, economy) * (1 + Number(economy?.inflation_rate || 0));
  if (developmentLevel === 0 && hasMonopoly(property, properties)) {
    rent *= 2;
  }
  return Math.round(rent * 100) / 100;
}

export function getPropertyRentSchedule(property, properties, economy = {}) {
  if (property?.property_type !== 'property') {
    return [];
  }

  const currentLevel = normalizeLevel(property.dev_level ?? property.development_level);
  const cap = getDevelopmentCap(economy);
  const maxLevel = cap == null ? Math.max(8, currentLevel + 4) : cap;

  return Array.from({ length: maxLevel + 1 }, (_, level) => ({
    level,
    rent: calculatePropertyRent(property, properties, economy, level),
  }));
}