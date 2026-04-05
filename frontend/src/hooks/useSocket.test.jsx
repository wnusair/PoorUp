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
      auctionState: null,
      movingPlayerId: null,
      pendingEventFns: [],
      logEntries: [],
    });
  });

  afterEach(() => {
    useGameStore.setState({
      activeModal: null,
      activeTrade: null,
      auctionState: null,
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
    expect(useGameStore.getState().activeTrade?.receiver_id).toBe(1);

    useGameStore.getState().closeModal();

    expect(useGameStore.getState().activeModal).toBe('trade');
  });
});