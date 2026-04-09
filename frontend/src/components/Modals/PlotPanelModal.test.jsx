import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useGameStore } from '../../hooks/useGameState';
import PlotPanelModal from './PlotPanelModal';


describe('PlotPanelModal founder entry', () => {
  afterEach(() => {
    act(() => {
      useGameStore.setState({
        social: { plot: {} },
        players: [],
        properties: {},
        myPlayerId: null,
      });
    });
  });

  it('shows the founder action when the current player is eligible', async () => {
    const onPlotStart = vi.fn().mockResolvedValue({ summary: 'The plot has begun.' });

    act(() => {
      useGameStore.setState({
        social: { plot: {} },
        players: [
          {
            id: 1,
            username: 'Atlas',
            plot_can_found: true,
            plot_role: null,
          },
        ],
        properties: {},
        myPlayerId: 1,
      });
    });

    render(
      <PlotPanelModal
        onClose={vi.fn()}
        onPlotStart={onPlotStart}
        onPlotAction={vi.fn()}
        onPlotJoin={vi.fn()}
        onPlotLeave={vi.fn()}
        onPlotCounterAction={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Organization' }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Found The Plot' }));
    });

    expect(onPlotStart).toHaveBeenCalledWith({});
    await waitFor(() => {
      expect(screen.getByText('The plot has begun.')).toBeInTheDocument();
    });
  });
});