import { formatMoney } from './formatters';
import { calculatePropertyRent } from './propertyEconomy';


export function getPropertiesArray(properties) {
  if (Array.isArray(properties)) {
    return properties;
  }
  return Object.values(properties || {});
}


export function getDealCounterpartyId(deal, myPlayerId) {
  if (!deal) {
    return null;
  }
  return deal.proposer_id === myPlayerId ? deal.counterparty_id : deal.proposer_id;
}


export function getDealCounterpartyName(deal, myPlayerId, players = []) {
  if (!deal) {
    return 'Unknown player';
  }

  if (deal.proposer_id === myPlayerId) {
    return deal.counterparty_name || players.find((player) => player.id === deal.counterparty_id)?.username || 'Unknown player';
  }

  return deal.proposer_name || players.find((player) => player.id === deal.proposer_id)?.username || 'Unknown player';
}


export function formatDealDeadline(deadline = {}) {
  const remaining = Number(deadline?.remaining ?? deadline?.initial ?? 0) || 0;
  const metric = deadline?.metric || 'beneficiary_turns';
  const labels = {
    beneficiary_landings_on_grantor: remaining === 1 ? '1 landing on payer left' : `${remaining} landings on payer left`,
    beneficiary_turns: remaining === 1 ? '1 receiver turn left' : `${remaining} receiver turns left`,
    grantor_turns: remaining === 1 ? '1 payer turn left' : `${remaining} payer turns left`,
    full_rounds: remaining === 1 ? '1 round left' : `${remaining} rounds left`,
    beneficiary_rotations: remaining === 1 ? '1 receiver lap left' : `${remaining} receiver laps left`,
  };
  return labels[metric] || `${remaining} steps left`;
}


export function getClauseTone(type) {
  if (type === 'rent_immunity') {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100';
  }
  if (type === 'rent_discount') {
    return 'border-sky-500/30 bg-sky-500/10 text-sky-100';
  }
  if (type === 'development_investment') {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-100';
  }
  return 'border-slate-700 bg-slate-900/80 text-slate-200';
}


export function getClauseLabel(type) {
  if (type === 'rent_immunity') {
    return 'No rent';
  }
  if (type === 'rent_discount') {
    return 'Rent cut';
  }
  if (type === 'development_investment') {
    return 'Build loan';
  }
  return 'Clause';
}


export function scopeMatchesProperty(scope = {}, property = {}, ownerId) {
  if (!property || Number(property.owner_id) !== Number(ownerId)) {
    return false;
  }

  const mode = scope?.mode || 'all_grantor_properties';
  if (mode === 'all_grantor_properties') {
    return true;
  }
  if (mode === 'selected_group_colors') {
    return (scope.group_colors || []).includes(property.group_color);
  }
  if (mode === 'selected_property_ids') {
    return (scope.property_ids || []).map(Number).includes(Number(property.id));
  }
  return false;
}

export function getActivePlayerCount(players = []) {
  return (players || []).filter((player) => !player?.bankrupt && !player?.is_bankrupt).length;
}

export function getBuildLoanHeadsUpMultiplier(activePlayerCount = 0) {
  return 1;
}

export function getEffectiveBuildLoanMaxPayout(maxPayout = 0, privateEquityBonus = 1, activePlayerCount = 0) {
  return Number(maxPayout || 0);
}

export function estimatePropertyRent(property, properties, economy = {}) {
  if (!property?.owner_id || property?.is_mortgaged) {
    return 0;
  }
  return calculatePropertyRent(property, properties, economy);
}


export function estimateScopeValue(scope, ownerId, properties, uses = 1, multiplier = 1, economy = {}) {
  const coveredProperties = getPropertiesArray(properties).filter((property) => scopeMatchesProperty(scope, property, ownerId));
  if (!coveredProperties.length) {
    return 0;
  }

  const averageRent = coveredProperties.reduce((sum, property) => sum + estimatePropertyRent(property, properties, economy), 0) / coveredProperties.length;
  return Math.round(averageRent * Math.max(1, Number(uses) || 1) * Math.max(0, Number(multiplier) || 0) * 100) / 100;
}


export function summarizeClause(clause, myPlayerId, players = [], properties = {}, economy = {}) {
  const grantorName = players.find((player) => player.id === clause.grantor_id)?.username || (clause.grantor_id === myPlayerId ? 'You' : 'Grantor');
  const beneficiaryName = players.find((player) => player.id === clause.beneficiary_id)?.username || (clause.beneficiary_id === myPlayerId ? 'You' : 'Beneficiary');
  const deadlineText = formatDealDeadline(clause.deadline);

  if (clause.type === 'rent_immunity') {
    return `${beneficiaryName} pays no rent to ${grantorName} for ${deadlineText.toLowerCase()}.`;
  }
  if (clause.type === 'rent_discount') {
    const percent = Math.round((1 - Number(clause?.config?.rent_multiplier || 1)) * 100);
    return `${beneficiaryName} gets ${percent}% off ${grantorName}'s rent for ${deadlineText.toLowerCase()}.`;
  }

  const escrowAmount = Number(clause?.config?.escrow_amount || 0);
  const profitSharePercent = Math.round(Number(clause?.config?.profit_share_percent || 0) * 100);
  const maxPayout = Number(clause?.config?.max_payout || 0);
  const scopedProperties = getPropertiesArray(properties).filter((property) => scopeMatchesProperty(clause.scope, property, clause.beneficiary_id));
  const scopeLabel = scopedProperties.length > 0
    ? `${scopedProperties.length} eligible propert${scopedProperties.length === 1 ? 'y' : 'ies'}`
    : 'selected assets';
  return `${grantorName} puts up ${formatMoney(escrowAmount)} for ${beneficiaryName}'s builds on ${scopeLabel}. ${grantorName} gets ${profitSharePercent}% of the rent value from those funded upgrades until repaid, up to ${formatMoney(maxPayout)}.`;
}


export function summarizeDeal(deal, myPlayerId, players = [], properties = {}, economy = {}) {
  const counterparty = getDealCounterpartyName(deal, myPlayerId, players);
  const firstClause = deal?.clauses?.[0];
  const clauseTypes = [...new Set((deal?.clauses || []).map((clause) => getClauseLabel(clause.type)))];
  const deadline = firstClause ? formatDealDeadline(firstClause.deadline) : 'No deadline';
  return {
    title: deal?.status === 'proposed'
      ? `Proposal with ${counterparty}`
      : `${counterparty}`,
    body: `${clauseTypes.join(' + ')}${clauseTypes.length ? ' • ' : ''}${deadline}`,
  };
}


export function sortDealsForPlayer(deals = [], myPlayerId) {
  const involvedDeals = (deals || []).filter(
    (deal) => deal.proposer_id === myPlayerId || deal.counterparty_id === myPlayerId,
  );

  return [...involvedDeals].sort((left, right) => {
    const score = (deal) => {
      if (deal.status === 'proposed' && deal.counterparty_id === myPlayerId) {
        return 4;
      }
      if (deal.status === 'accepted') {
        return 3;
      }
      if (deal.status === 'proposed') {
        return 2;
      }
      return 1;
    };
    const scoreDelta = score(right) - score(left);
    if (scoreDelta !== 0) {
      return scoreDelta;
    }

    const leftStamp = left.last_updated_at || left.accepted_at || left.responded_at || left.created_at || '';
    const rightStamp = right.last_updated_at || right.accepted_at || right.responded_at || right.created_at || '';
    return String(rightStamp).localeCompare(String(leftStamp));
  });
}


export function createEmptyDealClause() {
  return {
    key: `${Date.now()}-${Math.random()}`,
    type: 'rent_immunity',
    beneficiarySide: 'me',
    investorSide: 'them',
    scopeMode: 'all_grantor_properties',
    groupColors: [],
    propertyIds: [],
    deadlineMetric: 'beneficiary_turns',
    deadlineAmount: 2,
    rentMultiplier: 0.5,
    escrowAmount: 300,
    profitSharePercent: 0.35,
    maxPayout: 450,
  };
}


export function buildDraftFromDeal(deal, myPlayerId) {
  const counterpartyId = getDealCounterpartyId(deal, myPlayerId);
  return {
    title: deal?.title || '',
    counterpartyId,
    clauses: (deal?.clauses || []).map((clause) => ({
      key: `${clause.id || Date.now()}-${Math.random()}`,
      type: clause.type,
      beneficiarySide: clause.beneficiary_id === myPlayerId ? 'me' : 'them',
      investorSide: clause.grantor_id === myPlayerId ? 'me' : 'them',
      scopeMode: clause?.scope?.mode || 'all_grantor_properties',
      groupColors: Array.isArray(clause?.scope?.group_colors) ? clause.scope.group_colors : [],
      propertyIds: Array.isArray(clause?.scope?.property_ids) ? clause.scope.property_ids.map(Number) : [],
      deadlineMetric: clause?.deadline?.metric || 'beneficiary_turns',
      deadlineAmount: Number(clause?.deadline?.remaining ?? clause?.deadline?.initial ?? 1) || 1,
      rentMultiplier: Number(clause?.config?.rent_multiplier || 0.5) || 0.5,
      escrowAmount: Number(clause?.config?.escrow_amount || clause?.config?.escrow_remaining || 300) || 300,
      profitSharePercent: Number(clause?.config?.profit_share_percent || 0.35) || 0.35,
      maxPayout: Number(clause?.config?.max_payout || 450) || 450,
    })),
  };
}
