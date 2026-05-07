import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useGameStore } from '../../hooks/useGameState';
import LiberalDemocracyRail from './LiberalDemocracyRail';

describe('LiberalDemocracyRail', () => {
  const socketActions = {
    submitMarketOrder: vi.fn(),
    depositBankFunds: vi.fn(),
    withdrawBankFunds: vi.fn(),
    requestBankLoan: vi.fn(),
    repayBankLoan: vi.fn(),
  };

  beforeEach(() => {
    Object.values(socketActions).forEach((mockFn) => mockFn.mockReset());
    socketActions.submitMarketOrder.mockResolvedValue({ ok: true });
    socketActions.depositBankFunds.mockResolvedValue({ ok: true });

    act(() => {
      useGameStore.setState({
        matchId: 77,
        myPlayerId: 1,
        currentPlayerId: 1,
        players: [
          {
            id: 1,
            username: 'Atlas',
            balance: 1200,
            portfolio: { stocks: { CORP1: 3 }, crypto: { BTC: 1.5 }, recent_orders: [] },
          },
        ],
        properties: {
          2: { id: 11, owner_id: 1, base_price: 120, board_position: 2 },
        },
        economy: {
          market: {
            sentiment: 74,
            volatility_index: 0.16,
            assets: {
              BTC: { asset_key: 'BTC', label: 'Bitcoin', kind: 'crypto', price: 82, price_change_last_round: 0.03 },
              CORP1: {
                asset_key: 'CORP1',
                label: 'Atlas Capital',
                kind: 'stock',
                price: 21,
                price_change_last_round: 0.01,
                history: [
                  { round: 1, price: 18, change: 0 },
                  { round: 2, price: 19.5, change: 0.08 },
                  { round: 3, price: 21, change: 0.01 },
                ],
              },
            },
            cycle: { phase: 'growth', rounds_remaining: 2, policy_pressure: 0.01 },
          },
          bank: {
            players: {
              1: {
                savings_balance: 300,
                loan_principal: 150,
                loan_interest_rate: 0.09,
                missed_payments: 1,
              },
            },
          },
          jobs: {
            players: {
              1: {
                employment_status: 'employed',
                employer_name: 'Atlas Capital',
                salary: 240,
                unemployment_rounds_remaining: 0,
              },
            },
          },
          tax_brackets: {
            brackets: [
              { label: 'Tier 1', min_net_worth: 0, max_net_worth: 1999, rate: 0 },
              { label: 'Tier 2', min_net_worth: 2000, max_net_worth: 3999, rate: 0.04 },
            ],
          },
          corporations: {
            by_id: {
              corp_1: {
                id: 'corp_1',
                name: 'Atlas Capital',
                stock_symbol: 'CORP1',
                stock_price: 21,
                pricing_modifier: 1.08,
                cash_reserve: 900,
              },
            },
          },
        },
      });
    });
  });

  afterEach(() => {
    act(() => {
      useGameStore.setState({
        matchId: null,
        myPlayerId: null,
        currentPlayerId: null,
        players: [],
        properties: {},
        economy: {},
      });
    });
  });

  it('renders nested tax brackets and submits market and bank actions', async () => {
    render(<LiberalDemocracyRail socketActions={socketActions} />);

    expect(screen.getByText('Investments')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Market' }));
    await waitFor(() => {
      expect(screen.getByLabelText(/Asset/i).value).toBe('CORP1');
    });
    expect(screen.getByRole('img', { name: /Atlas Capital price chart/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Asset/i), { target: { value: 'BTC' } });
    fireEvent.change(screen.getByLabelText(/Quantity/i), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Place Order' }));

    await waitFor(() => {
      expect(socketActions.submitMarketOrder).toHaveBeenCalledWith({
        match_id: 77,
        asset_key: 'BTC',
        side: 'buy',
        quantity: 2,
      });
    });

    fireEvent.click(screen.getByRole('button', { name: 'Bank' }));
    fireEvent.change(screen.getByLabelText(/Amount/i), { target: { value: '125' } });
    fireEvent.click(screen.getByRole('button', { name: 'Deposit' }));

    await waitFor(() => {
      expect(socketActions.depositBankFunds).toHaveBeenCalledWith({ match_id: 77, amount: 125 });
    });

    fireEvent.click(screen.getByRole('button', { name: 'Taxes' }));
    expect(screen.getByText('Tier 1')).toBeInTheDocument();
    expect(screen.getByText('Tier 2')).toBeInTheDocument();
  });
});
