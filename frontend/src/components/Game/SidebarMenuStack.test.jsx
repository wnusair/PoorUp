import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useGameStore } from '../../hooks/useGameState';
import SidebarMenuStack from './SidebarMenuStack';

const adminSeedPlotDebug = vi.fn();

vi.mock('../../utils/api', () => ({
  adminSeedPlotDebug: (...args) => adminSeedPlotDebug(...args),
}));

describe('SidebarMenuStack host debug tools', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_ENABLE_HOST_DEBUG_TOOLS', 'true');
    adminSeedPlotDebug.mockReset();
    adminSeedPlotDebug.mockResolvedValue({ data: { message: 'Debug communist plot seeded.' } });
    const storage = {
      getItem: vi.fn((key) => (key === 'poorup_user' ? JSON.stringify({ id: '7' }) : null)),
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

    act(() => {
      useGameStore.setState({
        settings: {},
        matchId: 44,
        lobbyData: { match: { host_user_id: 7 } },
      });
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    act(() => {
      useGameStore.setState({
        settings: {},
        matchId: null,
        lobbyData: null,
      });
    });
  });

  it('shows the host debug button and seeds the communist plot scenario', async () => {
    render(<SidebarMenuStack />);

    fireEvent.click(screen.getByRole('button', { name: 'Seed Plot' }));

    expect(adminSeedPlotDebug).toHaveBeenCalledWith(44);
    await waitFor(() => {
      expect(screen.getByText('Debug communist plot seeded.')).toBeInTheDocument();
    });
  });

  it('hides host debug tools when the env flag disables them', () => {
    vi.stubEnv('VITE_ENABLE_HOST_DEBUG_TOOLS', 'false');

    render(<SidebarMenuStack />);

    expect(screen.queryByRole('button', { name: 'Seed Plot' })).not.toBeInTheDocument();
  });
});
