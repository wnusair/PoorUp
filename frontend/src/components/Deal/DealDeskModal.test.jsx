import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGameStore } from '../../hooks/useGameState';
import DealDeskModal from './DealDeskModal';


function buildDeal() {
  return {
    id: 47,
    match_id: 66,
    proposer_id: 2,
    counterparty_id: 1,
    status: 'proposed',
    title: 'Build loan',
    clauses: [
      {
        id: 93,
        type: 'development_investment',
        grantor_id: 1,
        beneficiary_id: 2,
        scope: {
          mode: 'selected_group_colors',
          group_colors: ['#EC4899'],
        },
        config: {
          escrow_amount: 150,
          profit_share_percent: 0.3,
          max_payout: 217.5,
          escrow_remaining: 0,
          payout_to_date: 0,
        },
        deadline: {
          metric: 'beneficiary_rotations',
          initial: 2,
          remaining: 2,
        },
        status: 'pending',
        tranches: [],
      },
    ],
  };
}


function setStoreState(balance = 25) {
  const deal = buildDeal();
  useGameStore.setState({
    deals: [deal],
    activeDeal: deal,
    players: [
      { id: 1, username: 'ShavingCream', balance, bankrupt: false },
      { id: 2, username: 'Cinder26', balance: 5.34, bankrupt: false },
    ],
    properties: {
      9: {
        id: 11,
        board_position: 9,
        name: 'Karachi',
        owner_id: 2,
        property_type: 'property',
        group_color: '#EC4899',
        base_price: 120,
        dev_level: 0,
        is_mortgaged: false,
      },
    },
    settings: {
      deals_enabled: true,
      private_equity_enabled: true,
    },
    economy: {
      inflation_rate: 0,
      gov_type: 'liberal_democracy',
      market_confidence: 78,
      capital_yield_rate: 0.021,
      private_equity_bonus_multiplier: 1.12,
    },
  });
}


describe('DealDeskModal', () => {
  beforeEach(() => {
    setStoreState();
  });

  afterEach(() => {
    useGameStore.setState({
      deals: [],
      activeDeal: null,
      players: [],
      properties: {},
      settings: {},
      economy: {},
    });
  });

  it('keeps the counter draft visible when the investor cannot fund the escrow', async () => {
    const onCounter = vi.fn();

    render(
      <DealDeskModal
        myPlayerId={1}
        onSubmit={vi.fn()}
        onRespond={vi.fn()}
        onCounter={onCounter}
        onCancel={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Counter' }));
    });
    const sendCounterofferButton = await screen.findByRole('button', { name: 'Send Counteroffer' });
    await act(async () => {
      fireEvent.click(sendCounterofferButton);
    });

    expect(await screen.findByText('Clause 1: ShavingCream cannot currently front $150.')).toBeInTheDocument();
    expect(onCounter).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText('Optional short title')).toHaveValue('Build loan');
    expect(screen.getByText('Counteroffer Draft')).toBeInTheDocument();
  });

  it('preserves the counter draft when the server rejects the counteroffer', async () => {
    setStoreState(500);
    const onCounter = vi.fn().mockRejectedValue(new Error('Only pending deals can be countered.'));

    render(
      <DealDeskModal
        myPlayerId={1}
        onSubmit={vi.fn()}
        onRespond={vi.fn()}
        onCounter={onCounter}
        onCancel={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Counter' }));
    });
    const sendCounterofferButton = await screen.findByRole('button', { name: 'Send Counteroffer' });
    await act(async () => {
      fireEvent.click(sendCounterofferButton);
    });

    await waitFor(() => expect(onCounter).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('Only pending deals can be countered.')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Optional short title')).toHaveValue('Build loan');
    expect(screen.getByText('Counteroffer Draft')).toBeInTheDocument();
  });

  it('shows the liberal-democracy market climate for PE deals', () => {
    setStoreState(500);

    render(
      <DealDeskModal
        myPlayerId={1}
        onSubmit={vi.fn()}
        onRespond={vi.fn()}
        onCounter={vi.fn()}
        onCancel={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("This Round's Cash Rules")).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cash rules help' })).toBeInTheDocument();
    expect(screen.getByText('Cash Bonus')).toBeInTheDocument();
    expect(screen.getByText('2.10%')).toBeInTheDocument();
    expect(screen.getByText(/Current build-loan bonus:/i)).toBeInTheDocument();
    expect(screen.getByText(/1v1 bonus active:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/\$268/).length).toBeGreaterThan(0);
  });
});