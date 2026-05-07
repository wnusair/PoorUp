import { describe, expect, it } from 'vitest';

import { BOARD_SPACES, BOARD_SPACE_SHORT_NAMES, GOVERNMENT_TYPES } from './constants';

describe('board constants', () => {
  it('uses abbreviated airport names everywhere', () => {
    const transitNames = BOARD_SPACES
      .filter((space) => space.type === 'transit')
      .map((space) => space.name);

    expect(transitNames).toEqual(['BOM', 'DXB', 'LHR', 'JFK']);
    expect(BOARD_SPACE_SHORT_NAMES[15]).toBe('DXB');
    expect(BOARD_SPACE_SHORT_NAMES[25]).toBe('LHR');
    expect(BOARD_SPACE_SHORT_NAMES[36]).toBe('JFK');
  });

  it('normalizes the renamed region groups and government description', () => {
    const oceaniaCities = BOARD_SPACES
      .filter((space) => ['Tokyo', 'Seoul', 'Sydney'].includes(space.name))
      .map((space) => space.region);
    const americasCities = BOARD_SPACES
      .filter((space) => ['São Paulo', 'Buenos Aires', 'New York'].includes(space.name))
      .map((space) => space.region);

    expect(new Set(oceaniaCities)).toEqual(new Set(['Oceania']));
    expect(new Set(americasCities)).toEqual(new Set(['Americas']));
    expect(GOVERNMENT_TYPES.liberal_democracy.description).toMatch(/Corporate ownership, jobs, markets, bank accounts, and tax-bracket politics/i);
  });
});
