import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TradePanel from './TradePanel';
import { useGameStore } from '../../hooks/useGameState';


function seedStore() {
  useGameStore.setState({
    players: [
      { id: 1, username: 'Atlas', balance: 900, bankrupt: false, color_hex: '#2563eb' },
      { id: 2, username: 'Bot Prime', balance: 700, bankrupt: false, color_hex: '#ef4444' },
    ],
    properties: {},
    settings: {
      trading_enabled: true,
      deals_enabled: true,
      lobbying_enabled: false,
    },
    economy: {
      gov_type: 'liberal_democracy',
    },
    lobbyingStats: {
      policy_pools: {},
    },
    activeTrade: null,
    tradeDealDrafts: [
      {
        id: 'draft-1',
        title: 'Revenue Shield',
        counterparty_id: 2,
        updated_at: '2026-04-06T12:00:00.000Z',
        payload: {
          title: 'Revenue Shield',
          counterparty_id: 2,
          clauses: [
            {
              type: 'rent_immunity',
              grantor_id: 2,
              beneficiary_id: 1,
              scope: { mode: 'all_grantor_properties' },
              config: {},
              deadline: { metric: 'beneficiary_turns', initial: 2 },
            },
          ],
        },
        clauses: [
          {
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
}


describe('TradePanel', () => {
  beforeEach(() => {
    seedStore();
  });

  it('shows saved deal drafts before choosing a trade partner and uses the draft counterparty', () => {
    const onSubmit = vi.fn();

    render(
      <TradePanel
        myPlayerId={1}
        onSubmit={onSubmit}
        onRespond={() => {}}
        onClose={() => {}}
      />,
    );

    expect(screen.getByText('Revenue Shield')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Revenue Shield/i }));
    fireEvent.click(screen.getByRole('button', { name: /Propose Trade/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        receiver_id: 2,
        included_deal_drafts: [
          expect.objectContaining({
            title: 'Revenue Shield',
            counterparty_id: 2,
          }),
        ],
      }),
    );
  });

  it('submits attached saved deal drafts with the trade payload', () => {
    const onSubmit = vi.fn();

    render(
      <TradePanel
        myPlayerId={1}
        onSubmit={onSubmit}
        onRespond={() => {}}
        onClose={() => {}}
      />,
    );

    fireEvent.click(screen.getAllByRole('button', { name: /Bot Prime/i })[0]);
    fireEvent.click(screen.getByRole('button', { name: /Revenue Shield/i }));
    fireEvent.click(screen.getByRole('button', { name: /Propose Trade/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        receiver_id: 2,
        included_deal_drafts: [
          expect.objectContaining({
            title: 'Revenue Shield',
            counterparty_id: 2,
          }),
        ],
      }),
    );
  });
});