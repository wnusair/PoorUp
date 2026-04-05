import { describe, expect, it } from 'vitest';
import {
  calculateDevelopmentCost,
  getPropertyRentSchedule,
  getRentMultiplier,
  isFullyDeveloped,
} from './propertyEconomy';


describe('propertyEconomy', () => {
  it('keeps the standard development cap outside minarchism', () => {
    expect(isFullyDeveloped(5, { gov_type: 'liberal_democracy' })).toBe(true);
    expect(isFullyDeveloped(6, { gov_type: 'minarchism' })).toBe(false);
  });

  it('scales minarchism development costs after four houses', () => {
    expect(calculateDevelopmentCost(200, 4, { gov_type: 'minarchism' })).toBe(100);
    expect(calculateDevelopmentCost(200, 5, { gov_type: 'minarchism' })).toBe(135);
    expect(calculateDevelopmentCost(200, 6, { gov_type: 'minarchism' })).toBe(205);
  });

  it('extends the rent schedule beyond the current level in minarchism', () => {
    const property = {
      id: 11,
      owner_id: 1,
      property_type: 'property',
      group_color: '#f59e0b',
      base_price: 200,
      dev_level: 6,
    };
    const properties = {
      1: property,
      2: { ...property, id: 12, dev_level: 6 },
    };

    const schedule = getPropertyRentSchedule(property, properties, { gov_type: 'minarchism' });

    expect(schedule.at(-1)?.level).toBe(10);
    expect(getRentMultiplier(5, { gov_type: 'minarchism' })).toBe(38);
    expect(getRentMultiplier(6, { gov_type: 'minarchism' })).toBe(46);
  });
});