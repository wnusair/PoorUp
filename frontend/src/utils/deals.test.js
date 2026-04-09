import { describe, expect, it } from 'vitest';
import { getActivePlayerCount, getEffectiveBuildLoanMaxPayout, summarizeClause } from './deals';


describe('deal helpers', () => {
  it('counts only active players', () => {
    expect(getActivePlayerCount([
      { id: 1, bankrupt: false },
      { id: 2, is_bankrupt: false },
      { id: 3, bankrupt: true },
      { id: 4, is_bankrupt: true },
    ])).toBe(2);
  });

  it('adds the heads-up bonus on top of the private-equity bonus in 1v1 games', () => {
    expect(getEffectiveBuildLoanMaxPayout(200, 1.15, 2)).toBeCloseTo(253, 5);
  });

  it('skips the heads-up bonus when more than two active players remain', () => {
    expect(getEffectiveBuildLoanMaxPayout(200, 1.15, 3)).toBeCloseTo(230, 5);
  });

  it('uses the effective build-loan repayment cap in summaries', () => {
    const summary = summarizeClause(
      {
        type: 'development_investment',
        grantor_id: 1,
        beneficiary_id: 2,
        scope: { mode: 'selected_property_ids', property_ids: [9] },
        deadline: { metric: 'beneficiary_turns', remaining: 2 },
        config: {
          escrow_amount: 200,
          profit_share_percent: 0.35,
          max_payout: 200,
        },
      },
      1,
      [
        { id: 1, username: 'Atlas', is_bankrupt: false },
        { id: 2, username: 'Rival', is_bankrupt: false },
      ],
      [
        { id: 9, owner_id: 2, group_color: '#f59e0b' },
      ],
      { private_equity_bonus_multiplier: 1.15 },
    );

    expect(summary).toContain('$253');
    expect(summary).toContain('rent value');
  });
});