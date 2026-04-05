import { isFullyDeveloped } from './propertyEconomy';

export function getPropertyDevelopmentLevel(property) {
  return property?.dev_level ?? property?.development_level ?? 0;
}


export function getPropertySet(property, properties) {
  if (!property) return [];

  const allProperties = Object.values(properties || {});
  const groupProperties = allProperties.filter((entry) => {
    if (entry.property_type !== property.property_type) return false;
    return entry.group_color === property.group_color;
  });

  return groupProperties.sort(
    (left, right) => (left.board_position ?? left.position ?? 0) - (right.board_position ?? right.position ?? 0),
  );
}

export function hasMonopoly(property, properties) {
  if (!property?.owner_id || property.property_type !== 'property') return false;

  const groupProperties = getPropertySet(property, properties)
    .filter((entry) => entry.property_type === 'property');

  return groupProperties.length > 0 && groupProperties.every((entry) => entry.owner_id === property.owner_id);
}


export function getDevelopmentBlockReason(property, properties, playerId, economy = {}) {
  if (!property) return 'Property unavailable.';
  if (property.property_type !== 'property') return 'Only standard properties can be developed.';
  if (property.owner_id !== playerId) return 'You must own this property to develop it.';
  if (property.is_mortgaged) return 'Mortgaged properties cannot be developed.';

  const setProperties = getPropertySet(property, properties)
    .filter((entry) => entry.property_type === 'property');

  if (setProperties.length === 0) {
    return 'This property is not part of a developable set.';
  }

  if (setProperties.some((entry) => entry.owner_id !== playerId)) {
    return 'You must own the full set before building here.';
  }

  if (setProperties.some((entry) => entry.is_mortgaged)) {
    return 'Unmortgage the full set before developing it.';
  }

  const currentLevel = getPropertyDevelopmentLevel(property);
  if (isFullyDeveloped(currentLevel, economy)) return 'This property is fully developed.';

  const minimumLevel = Math.min(...setProperties.map(getPropertyDevelopmentLevel));
  if (currentLevel > minimumLevel) {
    return 'Build evenly across the set before adding another house here.';
  }

  return null;
}


export function canDevelopProperty(property, properties, playerId, economy = {}) {
  return getDevelopmentBlockReason(property, properties, playerId, economy) == null;
}


export function getSellDevelopmentBlockReason(property, properties, playerId) {
  if (!property) return 'Property unavailable.';
  if (property.property_type !== 'property') return 'Only standard properties can sell houses.';
  if (property.owner_id !== playerId) return 'You must own this property to sell houses.';

  const currentLevel = getPropertyDevelopmentLevel(property);
  if (currentLevel <= 0) return 'There are no houses to sell here.';

  const setProperties = getPropertySet(property, properties)
    .filter((entry) => entry.property_type === 'property');

  if (setProperties.length === 0) {
    return 'This property is not part of a developable set.';
  }

  const maximumLevel = Math.max(...setProperties.map(getPropertyDevelopmentLevel));
  if (currentLevel < maximumLevel) {
    return 'Sell evenly across the set before removing a house here.';
  }

  return null;
}


export function canSellPropertyDevelopment(property, properties, playerId) {
  return getSellDevelopmentBlockReason(property, properties, playerId) == null;
}