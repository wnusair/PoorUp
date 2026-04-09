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
  market_deregulation: 'Looser investor rules',
  capital_controls: 'Stricter investor rules',
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