import { BOARD_POSITION_ORDER } from './constants';

const GOVERNMENT_TYPE_ALIASES = {
  minarchism: 'minarchism',
  minarchy: 'minarchism',
  liberal_democracy: 'liberal_democracy',
  'liberal-democracy': 'liberal_democracy',
  'liberal democracy': 'liberal_democracy',
  liberaldemocracy: 'liberal_democracy',
  democracy: 'liberal_democracy',
  democratic: 'liberal_democracy',
  social_democracy: 'social_democracy',
  'social-democracy': 'social_democracy',
  'social democracy': 'social_democracy',
  socialdemocracy: 'social_democracy',
  socialism: 'social_democracy',
};

const GAME_MODE_ALIASES = {
  standard: 'standard',
  speed: 'speed',
  chaos: 'chaos',
  cooperative: 'cooperative',
  coop: 'cooperative',
  co_op: 'cooperative',
  'co-op': 'cooperative',
  'co op': 'cooperative',
};


const SETTINGS_KEY_ALIASES = {
  allow_auctions: 'auction_enabled',
  allow_trading: 'trading_enabled',
  allow_lobbying: 'lobbying_enabled',
  allow_teams: 'deals_enabled',
  teams_enabled: 'deals_enabled',
  free_parking_jackpot: 'free_parking_pot_enabled',
  double_go_salary: 'double_on_go',
};


export function normalizeGovernmentType(value = 'liberal_democracy') {
  const rawValue = String(value ?? '').trim().toLowerCase();
  if (!rawValue) {
    return 'liberal_democracy';
  }

  const normalized = GOVERNMENT_TYPE_ALIASES[rawValue];
  if (normalized) {
    return normalized;
  }

  const collapsed = rawValue.replace(/[-\s]+/g, '_');
  return GOVERNMENT_TYPE_ALIASES[collapsed] || 'liberal_democracy';
}


export function normalizeGameMode(value = 'standard') {
  const rawValue = String(value ?? '').trim().toLowerCase();
  if (!rawValue) {
    return 'standard';
  }

  const normalized = GAME_MODE_ALIASES[rawValue];
  if (normalized) {
    return normalized;
  }

  const collapsed = rawValue.replace(/[-\s]+/g, '_');
  return GAME_MODE_ALIASES[collapsed] || 'standard';
}


export function normalizeSettings(settings = {}) {
  const normalized = {};

  for (const [key, value] of Object.entries(settings || {})) {
    const canonicalKey = SETTINGS_KEY_ALIASES[key] || key;
    normalized[canonicalKey] = canonicalKey === 'government_type'
      ? normalizeGovernmentType(value)
      : canonicalKey === 'game_mode'
      ? normalizeGameMode(value)
      : value;
  }

  if (!normalized.government_type) {
    normalized.government_type = 'liberal_democracy';
  }

  if (!normalized.game_mode) {
    normalized.game_mode = 'standard';
  }

  if (normalized.turn_timer_enabled == null) {
    normalized.turn_timer_enabled = true;
  }

  if (normalized.collect_rent_while_jailed == null) {
    normalized.collect_rent_while_jailed = false;
  }

  return normalized;
}


function toNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}


const ACTIVE_BOARD_POSITIONS = new Set(BOARD_POSITION_ORDER);


function normalizeBoardPosition(position, fallback = 0) {
  const numericPosition = toNumber(position, fallback);

  if (ACTIVE_BOARD_POSITIONS.has(numericPosition)) {
    return numericPosition;
  }

  for (const candidate of BOARD_POSITION_ORDER) {
    if (candidate >= numericPosition) {
      return candidate;
    }
  }

  return BOARD_POSITION_ORDER[0] ?? fallback;
}


function normalizeDealDeadline(deadline = {}) {
  return {
    ...deadline,
    metric: deadline?.metric || 'beneficiary_turns',
    initial: toNumber(deadline?.initial, 0),
    remaining: toNumber(deadline?.remaining ?? deadline?.initial, 0),
  };
}


function normalizeDealTranche(tranche = {}) {
  return {
    ...tranche,
    id: toNumber(tranche.id, null),
    property_id: toNumber(tranche.property_id, null),
    investor_id: toNumber(tranche.investor_id, null),
    recipient_id: toNumber(tranche.recipient_id, null),
    funded_cost: toNumber(tranche.funded_cost, 0),
    baseline_dev_level: toNumber(tranche.baseline_dev_level, 0),
    funded_dev_level: toNumber(tranche.funded_dev_level, 0),
    baseline_rent: toNumber(tranche.baseline_rent, 0),
    funded_rent: toNumber(tranche.funded_rent, 0),
    profit_share_percent: toNumber(tranche.profit_share_percent, 0),
    max_payout: toNumber(tranche.max_payout, 0),
    payout_to_date: toNumber(tranche.payout_to_date, 0),
    active: Boolean(tranche.active),
  };
}


function normalizeDealClause(clause = {}) {
  const normalizedConfig = {
    ...(clause.config || {}),
    rent_multiplier: toNumber(clause?.config?.rent_multiplier, clause?.config?.rent_multiplier ?? 1),
    escrow_amount: toNumber(clause?.config?.escrow_amount, 0),
    escrow_remaining: toNumber(clause?.config?.escrow_remaining, 0),
    profit_share_percent: toNumber(clause?.config?.profit_share_percent, 0),
    max_payout: toNumber(clause?.config?.max_payout, 0),
    payout_to_date: toNumber(clause?.config?.payout_to_date, 0),
  };

  return {
    ...clause,
    id: toNumber(clause.id, null),
    deal_id: toNumber(clause.deal_id, null),
    grantor_id: toNumber(clause.grantor_id, null),
    beneficiary_id: toNumber(clause.beneficiary_id, null),
    type: clause.type || clause.clause_type || 'rent_immunity',
    scope: clause.scope || { mode: 'all_grantor_properties' },
    config: normalizedConfig,
    deadline: normalizeDealDeadline(clause.deadline),
    tranches: Array.isArray(clause.tranches) ? clause.tranches.map(normalizeDealTranche) : [],
  };
}


export function normalizeDeal(deal = {}) {
  return {
    ...deal,
    id: toNumber(deal.id, null),
    match_id: toNumber(deal.match_id, null),
    proposer_id: toNumber(deal.proposer_id, null),
    counterparty_id: toNumber(deal.counterparty_id, null),
    proposal_version: toNumber(deal.proposal_version, 1),
    counter_of_deal_id: toNumber(deal.counter_of_deal_id, null),
    termination_requested_by_id: toNumber(deal.termination_requested_by_id, null),
    status: deal.status || 'proposed',
    clauses: Array.isArray(deal.clauses) ? deal.clauses.map(normalizeDealClause) : [],
  };
}


export function normalizeDeals(deals = []) {
  if (!Array.isArray(deals)) {
    return [];
  }

  return deals
    .map(normalizeDeal)
    .sort((left, right) => {
      const leftStamp = left.last_updated_at || left.accepted_at || left.responded_at || left.created_at || '';
      const rightStamp = right.last_updated_at || right.accepted_at || right.responded_at || right.created_at || '';
      return String(rightStamp).localeCompare(String(leftStamp));
    });
}


export function normalizePendingDebt(debt = {}) {
  return {
    ...debt,
    debtor_id: toNumber(debt.debtor_id, null),
    creditor_id: debt.creditor_id == null ? null : toNumber(debt.creditor_id, null),
    amount_due: toNumber(debt.amount_due, 0),
    original_amount: toNumber(debt.original_amount, toNumber(debt.amount_due, 0)),
  };
}


export function normalizePendingDebts(debts = []) {
  return Array.isArray(debts) ? debts.map(normalizePendingDebt) : [];
}


export function normalizeEconomy(economy = {}, gameState = {}) {
  const governmentType = normalizeGovernmentType(
    economy.gov_type || economy.government_type || gameState.gov_type || gameState.government_type || 'liberal_democracy',
  );
  const roundNumber = toNumber(
    economy.round_number ?? economy.current_round ?? gameState.current_round ?? gameState.round_number,
    1,
  );

  return {
    ...economy,
    gov_type: governmentType,
    government_type: governmentType,
    inflation_rate: toNumber(economy.inflation_rate, 0),
    interest_rate: toNumber(economy.interest_rate, 0),
    tax_multiplier: toNumber(economy.tax_multiplier, 0),
    stability: toNumber(economy.stability, 0.7),
    rage: toNumber(economy.rage ?? gameState.social?.overall_rage ?? gameState.rage, 0),
    welfare_payout: toNumber(economy.welfare_payout, 0),
    treasury_balance: toNumber(economy.treasury_balance, 0),
    free_parking_pot: toNumber(gameState.free_parking_pot ?? economy.free_parking_pot, 0),
    bailout_enabled: Boolean(economy.bailout_enabled ?? gameState.bailout_enabled ?? false),
    round_number: roundNumber,
    current_round: roundNumber,
  };
}


export function normalizePlayer(player = {}) {
  return {
    ...player,
    position: normalizeBoardPosition(player.current_position ?? player.position ?? 0),
    current_position: normalizeBoardPosition(player.current_position ?? player.position ?? 0),
    bankrupt: player.is_bankrupt ?? player.bankrupt ?? false,
    in_jail: player.is_jailed ?? player.in_jail ?? false,
    jail_cards: player.has_jail_card ? 1 : (player.jail_cards ?? 0),
    deal_summary: {
      active_deal_count: toNumber(player?.deal_summary?.active_deal_count, 0),
      pending_incoming_count: toNumber(player?.deal_summary?.pending_incoming_count, 0),
      pending_outgoing_count: toNumber(player?.deal_summary?.pending_outgoing_count, 0),
      incoming_immunities_from: Array.isArray(player?.deal_summary?.incoming_immunities_from) ? player.deal_summary.incoming_immunities_from : [],
      discounts_from: Array.isArray(player?.deal_summary?.discounts_from) ? player.deal_summary.discounts_from : [],
      investor_in: Array.isArray(player?.deal_summary?.investor_in) ? player.deal_summary.investor_in : [],
      recipient_in: Array.isArray(player?.deal_summary?.recipient_in) ? player.deal_summary.recipient_in : [],
    },
  };
}


export function normalizePlayers(players = []) {
  return players.map(normalizePlayer);
}


export function normalizeProperty(property = {}) {
  const rawPosition = property.board_position ?? property.position ?? null;
  const position = rawPosition == null ? null : normalizeBoardPosition(rawPosition, null);
  const devLevel = property.dev_level ?? property.development_level ?? 0;
  const groupColor = property.group_color ?? property.groupColor ?? null;
  const basePrice = property.base_price ?? property.basePrice ?? null;
  const currentValue = property.current_value ?? property.currentValue ?? basePrice;

  return {
    ...property,
    position,
    board_position: position,
    dev_level: devLevel,
    development_level: devLevel,
    group_color: groupColor,
    groupColor,
    base_price: basePrice,
    basePrice,
    current_value: currentValue,
    currentValue,
    property_type: property.property_type ?? property.type ?? 'property',
    social_incident_type: property.social_incident_type ?? null,
    social_watch_state: property.social_watch_state ?? 'stable',
    social_tension: toNumber(property.social_tension, 0),
    social_territory_instability: toNumber(property.social_territory_instability, 0),
    social_unionized: Boolean(property.social_unionized),
    social_former_owner_id: property.social_former_owner_id ?? null,
    social_dominant_grievance: property.social_dominant_grievance ?? null,
    social_next_state: property.social_next_state ?? null,
    social_eta_to_next_threshold: property.social_eta_to_next_threshold ?? null,
    social_spread_block_active: Boolean(property.social_spread_block_active),
    social_recommended_lobby_targets: Array.isArray(property.social_recommended_lobby_targets) ? property.social_recommended_lobby_targets : [],
    deal_modifiers: Array.isArray(property.deal_modifiers) ? property.deal_modifiers : [],
    deal_investment_options: Array.isArray(property.deal_investment_options) ? property.deal_investment_options : [],
    deal_profit_obligations: Array.isArray(property.deal_profit_obligations) ? property.deal_profit_obligations : [],
    deal_trade_warning: Boolean(property.deal_trade_warning),
  };
}


function mergePropertySocial(property = {}, socialProperties = {}) {
  const social = socialProperties[String(property.id)] || {};
  return {
    ...property,
    social_incident_type: social.incident_type ?? null,
    social_watch_state: social.watch_state ?? 'stable',
    social_tension: toNumber(social.tension, 0),
    social_territory_instability: toNumber(social.territory_instability, 0),
    social_unionized: Boolean(social.former_owner_id != null),
    social_former_owner_id: social.former_owner_id ?? null,
    social_dominant_grievance: social.dominant_grievance ?? null,
    social_negotiation_target: toNumber(social.negotiation_target, 0),
    social_negotiation_committed: toNumber(social.negotiation_committed, 0),
    social_reintegration_progress: toNumber(social.reintegration_progress, 0),
    social_remaining_rounds: toNumber(social.remaining_rounds, 0),
    social_next_state: social.next_state ?? null,
    social_eta_to_next_threshold: social.eta_to_next_threshold ?? null,
    social_spread_block_active: Boolean(social.spread_block_active),
    social_recommended_lobby_targets: Array.isArray(social.recommended_lobby_targets) ? social.recommended_lobby_targets : [],
  };
}


export function normalizeProperties(properties = {}, socialProperties = {}) {
  if (Array.isArray(properties)) {
    const propertiesByPosition = {};
    for (const property of properties) {
      const normalized = normalizeProperty(mergePropertySocial(property, socialProperties));
      if (normalized.board_position != null && ACTIVE_BOARD_POSITIONS.has(normalized.board_position)) {
        propertiesByPosition[normalized.board_position] = normalized;
      }
    }
    return propertiesByPosition;
  }

  const normalizedProperties = {};
  for (const [positionKey, property] of Object.entries(properties || {})) {
    const normalized = normalizeProperty(
      mergePropertySocial(
        { ...property, board_position: property?.board_position ?? Number(positionKey) },
        socialProperties,
      ),
    );
    if (normalized.board_position != null && ACTIVE_BOARD_POSITIONS.has(normalized.board_position)) {
      normalizedProperties[normalized.board_position] = normalized;
    }
  }
  return normalizedProperties;
}


export function normalizeSocial(social = {}, gameState = {}) {
  const normalizedProperties = Object.fromEntries(
    Object.entries(social?.properties || {}).map(([propertyId, entry]) => [
      String(propertyId),
      {
        ...entry,
        property_id: toNumber(entry?.property_id, toNumber(propertyId, null)),
        tension: toNumber(entry?.tension, 0),
        territory_instability: toNumber(entry?.territory_instability, 0),
        negotiation_target: toNumber(entry?.negotiation_target, 0),
        negotiation_committed: toNumber(entry?.negotiation_committed, 0),
        reintegration_progress: toNumber(entry?.reintegration_progress, 0),
        remaining_rounds: toNumber(entry?.remaining_rounds, 0),
        union_development_level: toNumber(entry?.union_development_level, 0),
        eta_to_next_threshold: entry?.eta_to_next_threshold == null ? null : toNumber(entry.eta_to_next_threshold, null),
        recommended_lobby_targets: Array.isArray(entry?.recommended_lobby_targets) ? entry.recommended_lobby_targets : [],
        recommended_actions: Array.isArray(entry?.recommended_actions) ? entry.recommended_actions : [],
        spread_block_active: Boolean(entry?.spread_block_active),
      },
    ]),
  );

  const normalizedIncidents = (Array.isArray(social?.active_incidents) ? social.active_incidents : []).map((incident) => ({
    ...incident,
    property_id: toNumber(incident?.property_id, null),
    remaining_rounds: toNumber(incident?.remaining_rounds, 0),
    negotiation_target: toNumber(incident?.negotiation_target, 0),
    negotiation_committed: toNumber(incident?.negotiation_committed, 0),
    reintegration_progress: toNumber(incident?.reintegration_progress, 0),
    eta_to_next_threshold: incident?.eta_to_next_threshold == null ? null : toNumber(incident.eta_to_next_threshold, null),
    recommended_lobby_targets: Array.isArray(incident?.recommended_lobby_targets) ? incident.recommended_lobby_targets : [],
    recommended_actions: Array.isArray(incident?.recommended_actions) ? incident.recommended_actions : [],
    spread_block_active: Boolean(incident?.spread_block_active),
  }));

  return {
    overall_rage: toNumber(social?.overall_rage ?? gameState?.rage, 0),
    stability_percent: toNumber(
      social?.stability_percent,
      Math.round(toNumber(gameState?.econ?.stability ?? gameState?.economy?.stability, 0.7) * 100),
    ),
    grievance_mix: social?.grievance_mix || {},
    territories: Array.isArray(social?.territories) ? social.territories : [],
    properties: normalizedProperties,
    active_incidents: normalizedIncidents,
    incident_history: Array.isArray(social?.incident_history) ? social.incident_history : [],
    active_effects: Array.isArray(social?.active_effects) ? social.active_effects : [],
    emergency_reforms: Array.isArray(social?.emergency_reforms) ? social.emergency_reforms : [],
    unionized_property_count: toNumber(social?.unionized_property_count, 0),
    national_flashpoint: social?.national_flashpoint || {},
  };
}