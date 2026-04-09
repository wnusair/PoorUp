import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useGameStore } from '../hooks/useGameState';
import { getSocket, useSocket } from '../hooks/useSocket';
import LobbyRoom from '../components/Lobby/LobbyRoom';
import { api } from '../utils/api';
import { applyLobbySnapshot } from '../utils/lobbyState';

export default function LobbyPage() {
  const { roomCode } = useParams();
  const normalizedRoomCode = roomCode?.trim().toUpperCase() || '';
  const navigate = useNavigate();
  const { lobbyData } = useGameStore();

  // Load initial lobby state from REST
  useEffect(() => {
    async function fetchLobby() {
      try {
        const { data } = await api.get(`/lobby/${normalizedRoomCode}`);
        applyLobbySnapshot(data, { roomCode: normalizedRoomCode });

        const socket = getSocket();
        if (socket) {
          socket.emit('join_room', {
            room_code: normalizedRoomCode,
            ...(data.match?.id ? { match_id: data.match.id } : {}),
          });
        }

        if (data.match?.status === 'active' && data.match?.id) {
          useGameStore.getState().setGamePhase('playing');
          navigate(`/game/${data.match.id}`, { replace: true });
        }
      } catch (err) {
        console.error('Failed to load lobby:', err);
      }
    }
    fetchLobby();
  }, [navigate, normalizedRoomCode]);

  // Socket connection for live lobby updates
  const myPlayerId = useGameStore(s => s.myPlayerId);
  useSocket({
    roomCode: normalizedRoomCode,
    playerId: myPlayerId,
    enabled: true,
  });

  // Listen for game_start to navigate to game
  useEffect(() => {
    const unsub = useGameStore.subscribe(
      state => state.gamePhase,
      phase => {
        if (phase === 'playing') {
          const matchId = useGameStore.getState().matchId;
          navigate(`/game/${matchId}`);
        }
      }
    );
    return unsub;
  }, [navigate]);

  if (!lobbyData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 p-4 md:p-8">
      <LobbyRoom roomCode={normalizedRoomCode} />
    </div>
  );
}
