import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import PlayerSlot from './PlayerSlot';
import ColorPicker from './ColorPicker';
import SettingsPanel from './SettingsPanel';
import BotSetupModal from './BotSetupModal';
import { useGameStore } from '../../hooks/useGameState';
import { lobbyAddBot, lobbyGet, lobbyRemoveBot, lobbySetReady, lobbyStart, lobbyUpdateBot, lobbyUpdateColor, lobbyUpdateSettings } from '../../utils/api';
import { applyLobbySnapshot } from '../../utils/lobbyState';

export default function LobbyRoom({ roomCode }) {
  const navigate = useNavigate();
  const { lobbyData, players, settings, takenColors, myPlayerId } = useGameStore();
  const [copying, setCopying] = useState(false);
  const [startError, setStartError] = useState('');
  const [readyError, setReadyError] = useState('');
  const [botError, setBotError] = useState('');
  const [colorError, setColorError] = useState('');
  const [botBusy, setBotBusy] = useState(false);
  const [botSetupOpen, setBotSetupOpen] = useState(false);
  const [colorBusy, setColorBusy] = useState(false);
  const [readyBusy, setReadyBusy] = useState(false);

  const me = players.find((p) => p.id === myPlayerId);
  const isHost = lobbyData?.match?.host_user_id === me?.user_id;
  const isReady = Boolean(me?.is_ready);
  const allReady = players.length >= 2 && players.every((p) => p.is_ready);
  const maxPlayers = settings?.max_players || 6;
  const botPlayers = players.filter((player) => player.is_bot);
  const botSetup = lobbyData?.bot_setup || null;

  // Fill empty slots
  const slots = Array.from({ length: maxPlayers }, (_, i) => players[i] || null);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(roomCode).then(() => {
      setCopying(true);
      setTimeout(() => setCopying(false), 1500);
    });
  };

  const refreshLobby = async () => {
    const { data } = await lobbyGet(roomCode);
    applyLobbySnapshot(data, { roomCode });
    return data;
  };

  const handleColorSelect = async (color) => {
    setColorError('');
    setColorBusy(true);
    try {
      const response = await lobbyUpdateColor(roomCode, color);
      if (response.data?.lobby) {
        applyLobbySnapshot(response.data.lobby, { roomCode });
      }
    } catch (err) {
      setColorError(err.response?.data?.error || 'Failed to change color.');
    } finally {
      setColorBusy(false);
    }
  };

  const handleReadyToggle = async () => {
    setReadyError('');
    setReadyBusy(true);
    try {
      const response = await lobbySetReady(roomCode, !isReady);
      if (response.data?.lobby) {
        applyLobbySnapshot(response.data.lobby, { roomCode });
      }
    } catch (err) {
      setReadyError(err.response?.data?.error || 'Failed to update ready state.');
    } finally {
      setReadyBusy(false);
    }
  };

  const handleSettingsChange = async (newSettings) => {
    if (!isHost) return;
    // Optimistically update the store so the UI responds immediately
    useGameStore.getState().setSettings(newSettings);
    try {
      const response = await lobbyUpdateSettings(roomCode, newSettings);
      if (response.data?.lobby) {
        applyLobbySnapshot(response.data.lobby, { roomCode });
      }
    } catch (err) {
      console.error('Settings update failed:', err);
    }
  };

  const handleStartGame = async () => {
    setStartError('');
    try {
      const res = await lobbyStart(roomCode);
      const matchId = res.data?.match_id || useGameStore.getState().matchId;
      navigate(`/game/${matchId}`);
    } catch (err) {
      setStartError(err.response?.data?.error || 'Failed to start game');
    }
  };

  const handleAddBots = async (payload) => {
    if (!isHost || players.length >= maxPlayers) return;
    setBotError('');
    setBotBusy(true);
    try {
      const response = await lobbyAddBot(roomCode, payload);
      if (response.data?.lobby) {
        applyLobbySnapshot(response.data.lobby, { roomCode });
      } else {
        await refreshLobby();
      }
    } catch (err) {
      setBotError(err.response?.data?.error || 'Failed to add bot');
    } finally {
      setBotBusy(false);
    }
  };

  const handleUpdateBot = async (playerId, payload) => {
    if (!isHost) return;
    setBotError('');
    setBotBusy(true);
    try {
      const response = await lobbyUpdateBot(roomCode, playerId, payload);
      if (response.data?.lobby) {
        applyLobbySnapshot(response.data.lobby, { roomCode });
      } else {
        await refreshLobby();
      }
    } catch (err) {
      setBotError(err.response?.data?.error || 'Failed to update bot');
    } finally {
      setBotBusy(false);
    }
  };

  const handleRemoveBot = async (playerId) => {
    if (!isHost) return;
    setBotError('');
    setBotBusy(true);
    try {
      const response = await lobbyRemoveBot(roomCode, playerId);
      if (response.data?.lobby) {
        applyLobbySnapshot(response.data.lobby, { roomCode });
      } else {
        await refreshLobby();
      }
    } catch (err) {
      setBotError(err.response?.data?.error || 'Failed to remove bot');
    } finally {
      setBotBusy(false);
    }
  };

  // Navigate to game when game starts
  useEffect(() => {
    const unsubscribe = useGameStore.subscribe(
      (state) => state.gamePhase,
      (phase) => {
        if (phase === 'playing') {
          const matchId = useGameStore.getState().matchId;
          navigate(`/game/${matchId || roomCode}`);
        }
      }
    );
    return unsubscribe;
  }, [navigate, roomCode]);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Game Lobby</h1>
            <p className="text-gray-400 text-sm">Waiting for players to join…</p>
          </div>
          {/* Room code */}
          <div className="text-center">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Room Code</p>
            <div className="flex items-center gap-2">
              <span className="text-3xl font-mono font-bold tracking-widest text-yellow-400">
                {roomCode}
              </span>
              <button
                onClick={handleCopyCode}
                className="text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 px-2 py-1 rounded transition"
              >
                {copying ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Player list + color picker */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-gray-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-gray-200">
                  Players ({players.length}/{maxPlayers})
                </h2>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">
                    {allReady ? 'All ready' : 'Waiting...'}
                  </span>
                  {isHost && (
                    <button
                      onClick={() => setBotSetupOpen(true)}
                      disabled={botBusy || players.length >= maxPlayers}
                      className="rounded-md border border-cyan-700/70 bg-cyan-950/50 px-3 py-1.5 text-xs font-semibold text-cyan-200 transition hover:border-cyan-500 hover:text-white disabled:cursor-not-allowed disabled:border-gray-700 disabled:bg-gray-900 disabled:text-gray-500"
                    >
                      Bot Setup
                    </button>
                  )}
                </div>
              </div>
              <div className="space-y-2">
                {slots.map((player, i) => (
                  <PlayerSlot
                    key={i}
                    player={player}
                    isMe={player?.id === myPlayerId}
                    isHost={player?.user_id === lobbyData?.match?.host_user_id}
                    slotIndex={i}
                  />
                ))}
              </div>
              {botError && (
                <p className="text-sm text-red-400">{botError}</p>
              )}
            </div>

            {/* Color picker for local player */}
            <div className="bg-gray-800 rounded-xl p-4">
              <ColorPicker
                selectedColor={me?.color_hex}
                takenColors={takenColors.filter((c) => c !== me?.color_hex)}
                onSelect={handleColorSelect}
                disabled={colorBusy}
              />
              {colorError && (
                <p className="mt-3 text-sm text-red-400">{colorError}</p>
              )}
            </div>

            {/* Ready + Start buttons */}
            <div className="flex gap-3">
              <button
                onClick={handleReadyToggle}
                disabled={readyBusy}
                className={[
                  'flex-1 py-3 rounded-lg font-semibold text-lg transition disabled:cursor-not-allowed disabled:opacity-60',
                  isReady
                    ? 'bg-green-700 hover:bg-green-600 text-white'
                    : 'bg-gray-700 hover:bg-gray-600 text-gray-200',
                ].join(' ')}
              >
                {isReady ? 'Ready' : 'Mark Ready'}
              </button>
              {isHost && (
                <button
                  onClick={handleStartGame}
                  disabled={!allReady}
                  className="flex-1 py-3 rounded-lg font-semibold text-lg bg-blue-600 hover:bg-blue-700
                             disabled:bg-gray-700 disabled:cursor-not-allowed disabled:text-gray-500 text-white transition"
                >
                  Start Game
                </button>
              )}
            </div>
            {readyError && (
              <p className="text-red-400 text-sm text-center">{readyError}</p>
            )}
            {startError && (
              <p className="text-red-400 text-sm text-center">{startError}</p>
            )}
          </div>

          {/* Right: Settings */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h2 className="font-semibold text-gray-200 mb-4">
              {isHost ? 'Game Settings' : 'Settings (Read-only)'}
            </h2>
            <div className="overflow-y-auto max-h-[calc(100vh-16rem)]">
              <SettingsPanel
                settings={settings}
                onChange={handleSettingsChange}
                readOnly={!isHost}
              />
            </div>
          </div>
        </div>
      </div>

      {isHost && (
        <BotSetupModal
          isOpen={botSetupOpen}
          onClose={() => setBotSetupOpen(false)}
          botSetup={botSetup}
          bots={botPlayers}
          openSeats={Math.max(0, maxPlayers - players.length)}
          onAddBots={handleAddBots}
          onUpdateBot={handleUpdateBot}
          onRemoveBot={handleRemoveBot}
          error={botError}
        />
      )}
    </div>
  );
}
