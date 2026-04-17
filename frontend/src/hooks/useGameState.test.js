import { beforeEach, describe, expect, it } from 'vitest';
import { useGameStore } from './useGameState';

describe('useGameStore retention', () => {
  beforeEach(() => {
    useGameStore.setState({
      logEntries: [],
      trades: [],
      activeTrade: null,
      deals: [],
      activeDeal: null,
      modalQueue: [],
    });
  });

  it('keeps only the most recent log entries in memory', () => {
    const { addLogEntry } = useGameStore.getState();

    for (let index = 0; index < 250; index += 1) {
      addLogEntry({
        type: 'move',
        message: `log ${index}`,
        timestamp: new Date(2024, 0, 1, 0, 0, index).toISOString(),
      });
    }

    const { logEntries } = useGameStore.getState();
    expect(logEntries).toHaveLength(200);
    expect(logEntries[0].message).toBe('log 50');
    expect(logEntries.at(-1)?.message).toBe('log 249');
  });

  it('preserves an active trade while trimming older trade history', () => {
    const trades = Array.from({ length: 60 }, (_, index) => ({
      id: index + 1,
      created_at: new Date(2024, 0, index + 1).toISOString(),
    }));

    useGameStore.setState({
      activeTrade: { id: 1 },
    });
    useGameStore.getState().setTrades(trades);

    const { trades: nextTrades } = useGameStore.getState();
    expect(nextTrades).toHaveLength(41);
    expect(nextTrades.some((trade) => trade.id === 1)).toBe(true);
    expect(nextTrades.some((trade) => trade.id === 60)).toBe(true);
  });

  it('preserves active deals and trims terminal deal history', () => {
    const terminalDeals = Array.from({ length: 55 }, (_, index) => ({
      id: index + 1,
      status: 'expired',
      created_at: new Date(2024, 0, index + 1).toISOString(),
      last_updated_at: new Date(2024, 0, index + 1).toISOString(),
    }));
    const activeDeal = {
      id: 999,
      status: 'accepted',
      created_at: new Date(2023, 0, 1).toISOString(),
      last_updated_at: new Date(2023, 0, 1).toISOString(),
    };

    useGameStore.setState({
      activeDeal: { id: 999 },
    });
    useGameStore.getState().setDeals([...terminalDeals, activeDeal]);

    const { deals } = useGameStore.getState();
    expect(deals).toHaveLength(41);
    expect(deals.some((deal) => deal.id === 999)).toBe(true);
    expect(deals.filter((deal) => deal.status === 'expired')).toHaveLength(40);
  });
});