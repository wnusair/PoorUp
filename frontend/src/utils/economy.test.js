import {
  buildPlayerTaxSchedule,
  calculateIncomeTaxEstimate,
  calculateLuxuryTaxEstimate,
  calculateSuperTaxEstimate,
  getEffectiveTaxRate,
} from './economy';

describe('tax preview helpers', () => {
  it('keeps non-property taxes percentage-based off current cash', () => {
    const economy = { tax_multiplier: 0.15 };

    expect(getEffectiveTaxRate(economy)).toBeCloseTo(0.1304, 4);
    expect(calculateIncomeTaxEstimate(1500, economy)).toBe(195.65);
    expect(calculateLuxuryTaxEstimate(1500, economy)).toBe(97.83);
    expect(calculateSuperTaxEstimate(1500, economy)).toBe(195.65);
  });

  it('builds round-aware schedule rows for the popup', () => {
    const schedule = buildPlayerTaxSchedule({
      player: { id: 7, balance: 900 },
      properties: [{ current_value: 500, is_mortgaged: false }],
      economy: { tax_multiplier: 0.2 },
      settings: {
        income_tax_on_pass_go: true,
        property_tax_every_n_rounds: 5,
        tax_every_turn: false,
      },
      currentRound: 3,
    });

    const incomeTax = schedule.find((entry) => entry.id === 'income_tax');
    const propertyTax = schedule.find((entry) => entry.id === 'property_tax');
    const turnTax = schedule.find((entry) => entry.id === 'turn_tax');

    expect(incomeTax.perRotationAmount).toBe(150);
    expect(propertyTax.amount).toBe(1);
    expect(propertyTax.dueThisRound).toBe(false);
    expect(propertyTax.intervalRounds).toBe(5);
    expect(propertyTax.when).toContain('round 5');
    expect(propertyTax.perTurnAmount).toBe(0);
    expect(turnTax.enabled).toBe(false);
    expect(turnTax.amount).toBe(0);
    expect(turnTax.perTurnAmount).toBe(0);
  });

  it('surfaces guaranteed per-turn taxes separately from pass-go rotations', () => {
    const schedule = buildPlayerTaxSchedule({
      player: { id: 9, balance: 1200 },
      properties: [{ current_value: 500, is_mortgaged: false }],
      economy: { tax_multiplier: 0.25 },
      settings: {
        income_tax_on_pass_go: true,
        property_tax_every_n_rounds: 1,
        tax_every_turn: true,
      },
      currentRound: 1,
    });

    const incomeTax = schedule.find((entry) => entry.id === 'income_tax');
    const propertyTax = schedule.find((entry) => entry.id === 'property_tax');
    const turnTax = schedule.find((entry) => entry.id === 'turn_tax');

    expect(incomeTax.perRotationAmount).toBe(240);
    expect(turnTax.perTurnAmount).toBe(12);
    expect(propertyTax.perTurnAmount).toBe(1.25);
  });
});