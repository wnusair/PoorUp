const GRIEVANCE_LABELS = {
  low_stability: 'The whole economy feels shaky',
  inequality: 'This owner is much richer than everyone else',
  ownership_concentration: 'One owner controls too much property',
  hostile_lobbying: 'A powerful owner is pushing harsh policies',
  shareholder_pressure: 'Growth is pricing people out',
  fiscal_backlash: 'People are angry about how public money is being used',
  welfare_shortfall: 'Help is not reaching struggling players fast enough',
  tax_pressure: 'Taxes are hitting this area hard',
  rent_extraction: 'Rents here are too punishing',
  treasury_distress: 'The treasury is too weak to calm things down',
  inflation_pressure: 'Prices are rising too fast',
  region_momentum: 'This area has been unstable for several rounds',
};

const INCIDENT_LABELS = {
  protest: 'Protest',
  strike: 'Strike',
  uprising: 'Uprising',
  revolution: 'Takeover',
};

const LOBBY_TARGET_LABELS = {
  welfare_increase: 'Raise welfare',
  economic_stimulus: 'Give direct cash relief',
  tax_multiplier_decrease: 'Lower taxes',
  stabilization_fund: 'Refill the treasury',
  bailout_enable: 'Turn bailouts on',
  bailout_disable: 'Turn bailouts off',
  rent_control: 'Cap rent growth',
  tax_bracket_rate_up: 'Raise a tax bracket rate',
  tax_bracket_rate_down: 'Lower a tax bracket rate',
  tax_bracket_boundary_up: 'Lift a tax bracket threshold',
  tax_bracket_boundary_down: 'Lower a tax bracket threshold',
  treasury_transfer_players: 'Send treasury money to players',
  treasury_transfer_treasury: 'Rebuild treasury reserves',
  money_supply_expand: 'Expand money supply',
  money_supply_contract: 'Tighten money supply',
};

function humanizeToken(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function getGrievanceLabel(value) {
  return GRIEVANCE_LABELS[value] || humanizeToken(value);
}

export function getIncidentLabel(value) {
  return INCIDENT_LABELS[value] || humanizeToken(value);
}

export function getLobbyTargetLabel(value) {
  return LOBBY_TARGET_LABELS[value] || humanizeToken(value);
}

export function humanizeSocialToken(value) {
  return GRIEVANCE_LABELS[value] || INCIDENT_LABELS[value] || LOBBY_TARGET_LABELS[value] || humanizeToken(value);
}
