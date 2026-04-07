import { render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGameStore } from './useGameState';

const handlers = {};

const fakeSocket = {
  connected: true,
  active: true,
  id: 'socket-1',
  auth: {},
  on: vi.fn((event, handler) => {
    handlers[event] = handler;
  }),
  off: vi.fn((event, handler) => {
    if (handlers[event] === handler) {
      delete handlers[event];
    }
  }),
  emit: vi.fn(),
  disconnect: vi.fn(),
  connect: vi.fn(),
};

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => fakeSocket),
}));

import { useSocket } from './useSocket';

function SocketHarness() {
  useSocket({ matchId: 77, playerId: 1, enabled: true });
  return null;
}

describe('useSocket trade presentation', () => {
  beforeEach(() => {
    Object.keys(handlers).forEach((key) => delete handlers[key]);
    fakeSocket.on.mockClear();
    fakeSocket.off.mockClear();
    fakeSocket.emit.mockClear();
    fakeSocket.disconnect.mockClear();
    fakeSocket.connect.mockClear();

    const storage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    };
    Object.defineProperty(window, 'localStorage', {
      value: storage,
      configurable: true,
    });
    Object.defineProperty(globalThis, 'localStorage', {
      value: storage,
      configurable: true,
    });

    useGameStore.setState({
      players: [
        { id: 1, username: 'Atlas', bankrupt: false },
        { id: 2, username: 'Bot Prime', bankrupt: false },
      ],
      properties: {},
      myPlayerId: 1,
      activeModal: 'card',
      activeTrade: null,
      trades: [],
      deals: [],
      activeDeal: null,
      auctionState: null,
      modalQueue: [],
      movingPlayerId: null,
      pendingEventFns: [],
      logEntries: [],
    });
  });

  afterEach(() => {
    useGameStore.setState({
      activeModal: null,
      activeTrade: null,
      trades: [],
      deals: [],
      activeDeal: null,
      auctionState: null,
      modalQueue: [],
      movingPlayerId: null,
      pendingEventFns: [],
    });
  });

  it('waits until the card modal closes before showing an incoming trade', () => {
    render(<SocketHarness />);

    handlers.trade_proposed({
      trade: {
        id: 99,
        proposer_id: 2,
        receiver_id: 1,
        proposer_name: 'Bot Prime',
        receiver_name: 'Atlas',
        offer_money: 120,
        request_money: 0,
        offer_properties: [],
        request_properties: [],
      },
    });

    expect(useGameStore.getState().activeModal).toBe('card');
    expect(useGameStore.getState().activeTrade).toBeNull();
    expect(useGameStore.getState().trades).toHaveLength(1);
    expect(useGameStore.getState().modalQueue).toEqual([{ modal: 'trade', entityId: 99 }]);

    useGameStore.getState().closeModal();

    expect(useGameStore.getState().activeModal).toBe('trade');
    expect(useGameStore.getState().activeTrade?.receiver_id).toBe(1);
  });

  it('does not replace an open trade composer with an incoming trade', () => {
    useGameStore.setState({
      activeModal: 'trade',
      activeTrade: null,
      trades: [],
      modalQueue: [],
    });

    render(<SocketHarness />);

    handlers.trade_proposed({
      trade: {
        id: 101,
        proposer_id: 2,
        receiver_id: 1,
        proposer_name: 'Bot Prime',
        receiver_name: 'Atlas',
        offer_money: 60,
        request_money: 0,
        offer_properties: [],
        request_properties: [],
      },
    });

    expect(useGameStore.getState().activeModal).toBe('trade');
    expect(useGameStore.getState().activeTrade).toBeNull();
    expect(useGameStore.getState().modalQueue).toEqual([{ modal: 'trade', entityId: 101 }]);

    useGameStore.getState().closeModal();

    expect(useGameStore.getState().activeModal).toBe('trade');
    expect(useGameStore.getState().activeTrade?.id).toBe(101);
  });

  it('queues an incoming deal until the current modal closes', () => {
    useGameStore.setState({
      activeModal: 'taxation',
      deals: [],
      activeDeal: null,
      modalQueue: [],
    });

    render(<SocketHarness />);

    handlers.deal_proposed({
      deal: {
        id: 301,
        proposer_id: 2,
        counterparty_id: 1,
        proposer_name: 'Bot Prime',
        counterparty_name: 'Atlas',
        status: 'proposed',
        clauses: [
          {
            id: 1,
            type: 'rent_immunity',
            grantor_id: 2,
            beneficiary_id: 1,
            scope: { mode: 'all_grantor_properties' },
            config: {},
            deadline: { metric: 'beneficiary_turns', initial: 2, remaining: 2 },
          },
        ],
      },
    });

    expect(useGameStore.getState().activeModal).toBe('taxation');
    expect(useGameStore.getState().activeDeal).toBeNull();
    expect(useGameStore.getState().modalQueue).toEqual([{ modal: 'deals', entityId: 301 }]);

    useGameStore.getState().closeModal();

    expect(useGameStore.getState().activeModal).toBe('deals');
    expect(useGameStore.getState().activeDeal?.id).toBe(301);
  });

  it('upserts bundled deals when a trade resolves', () => {
    useGameStore.setState({
      activeModal: 'trade',
      activeTrade: {
        id: 212,
        proposer_id: 2,
        receiver_id: 1,
      },
      trades: [
        {
          id: 212,
          proposer_id: 2,
          receiver_id: 1,
        },
      ],
      deals: [],
    });

    render(<SocketHarness />);

    handlers.trade_resolved({
      trade: {
        id: 212,
        proposer_id: 2,
        receiver_id: 1,
        proposer_name: 'Bot Prime',
        receiver_name: 'Atlas',
      },
      accepted: true,
      created_deals: [
        {
          id: 451,
          proposer_id: 2,
          counterparty_id: 1,
          proposer_name: 'Bot Prime',
          counterparty_name: 'Atlas',
          status: 'accepted',
          clauses: [
            {
              id: 1,
              type: 'rent_immunity',
              grantor_id: 2,
              beneficiary_id: 1,
              scope: { mode: 'all_grantor_properties' },
              config: {},
              deadline: { metric: 'beneficiary_turns', initial: 2, remaining: 2 },
            },
          ],
        },
      ],
    });

    expect(useGameStore.getState().deals).toHaveLength(1);
    expect(useGameStore.getState().deals[0].id).toBe(451);
    expect(useGameStore.getState().deals[0].status).toBe('accepted');
    expect(useGameStore.getState().trades).toHaveLength(0);
  });
});