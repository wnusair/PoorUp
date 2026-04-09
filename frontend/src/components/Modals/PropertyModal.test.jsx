import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useGameStore } from '../../hooks/useGameState';
import PropertyModal from './PropertyModal';


function setStoreState() {
  const property = {
    id: 11,
    board_position: 11,
    name: 'Karachi',
    owner_id: 1,
    property_type: 'property',
    group_color: '#EC4899',
    base_price: 120,
    current_value: 120,
    dev_level: 1,
    is_mortgaged: false,
    deal_investment_options: [
      {
        deal_id: 5,
        clause_id: 9,
        escrow_remaining: 220,
        profit_share_percent: 0.3,
        max_payout: 300,
      },
    ],
    deal_profit_obligations: [
      {
        deal_id: 5,
        tranche_id: 12,
        profit_share_percent: 0.3,
        payout_to_date: 60,
        max_payout: 300,
      },
    ],
  };

  useGameStore.setState({
    pendingAction: null,
    myPlayerId: 1,
    currentPlayerId: 1,
    players: [
      { id: 1, username: 'Atlas', balance: 900 },
      { id: 2, username: 'Rival', balance: 700 },
    ],
    properties: {
      11: property,
    },
    economy: {
      gov_type: 'liberal_democracy',
      government_type: 'liberal_democracy',
      market_confidence: 79,
      capital_yield_rate: 0.021,
      private_equity_bonus_multiplier: 1.15,
    },
  });

  return property;
}


describe('PropertyModal', () => {
  afterEach(() => {
    useGameStore.setState({
      pendingAction: null,
      myPlayerId: null,
      currentPlayerId: null,
      players: [],
      properties: {},
      economy: {},
    });
  });

  it('shows effective PE ceilings under liberal democracy', () => {
    const property = setStoreState();

    render(
      <PropertyModal
        property={property}
        mode="details"
        onBuy={vi.fn()}
        onDecline={vi.fn()}
        onDevelop={vi.fn()}
        onMortgage={vi.fn()}
        onSellHouse={vi.fn()}
        onUnmortgage={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("This Round's Cash Rules")).toBeInTheDocument();
    expect(screen.getByText(/1v1 bonus active:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/\$380/).length).toBeGreaterThan(0);
  });
});