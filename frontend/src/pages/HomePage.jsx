import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LoginForm from '../components/Auth/LoginForm';
import RegisterForm from '../components/Auth/RegisterForm';
import { api } from '../utils/api';
import { useGameStore } from '../hooks/useGameState';
import { useAuth } from '../hooks/useAuth';

export default function HomePage() {
  const [tab, setTab] = useState('login'); // 'login' | 'register'
  const [roomCode, setRoomCode] = useState('');
  const [joinError, setJoinError] = useState('');
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();
  const { myPlayerId } = useGameStore();
  const { user, loading: authLoading, error: authError, login, register } = useAuth();

  async function handleCreate() {
    setCreating(true);
    try {
      const { data } = await api.post('/lobby/create');
      const code = data.match?.room_code;
      if (code) navigate(`/lobby/${code}`);
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to create lobby');
    } finally {
      setCreating(false);
    }
  }

  async function handleJoin(e) {
    e.preventDefault();
    setJoinError('');
    const code = roomCode.trim().toUpperCase();
    if (!code) { setJoinError('Enter a room code.'); return; }
    try {
      await api.post('/lobby/join', { room_code: code });
      navigate(`/lobby/${code}`);
    } catch (err) {
      setJoinError(err.response?.data?.error || 'Failed to join room');
    }
  }

  function handleLogout() {
    localStorage.removeItem('poorup_token');
    localStorage.removeItem('poorup_user');
    window.location.reload();
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-gray-950">
      {/* Title */}
      <div className="mb-10 text-center">
        <h1 className="text-5xl font-extrabold text-white tracking-tight mb-2">
          Poor<span className="text-blue-400">Up</span>
        </h1>
        <p className="text-gray-400 text-sm max-w-sm">
          Corrupt the government, live off welfare, goon to victory...
        </p>
      </div>

      {user ? (
        /* ── Logged-in view ── */
        <div className="w-full max-w-sm space-y-6">
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
            <p className="text-gray-400 text-sm mb-1">Logged in as</p>
            <p className="text-white font-semibold text-lg">{user.username}</p>
          </div>

          {/* Create lobby */}
          <button
            onClick={handleCreate}
            disabled={creating}
            className="btn-primary w-full text-base py-3"
          >
            {creating ? 'Creating…' : '+ Create New Lobby'}
          </button>

          {/* Join lobby */}
          <form onSubmit={handleJoin} className="space-y-3">
            <input
              type="text"
              value={roomCode}
              onChange={e => setRoomCode(e.target.value.toUpperCase())}
              maxLength={8}
              placeholder="Enter room code…"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5
                         text-white placeholder-gray-500 focus:outline-none focus:ring-2
                         focus:ring-blue-500"
            />
            {joinError && <p className="text-red-400 text-xs">{joinError}</p>}
            <button type="submit" className="btn-ghost w-full">
              Join Room
            </button>
          </form>

          <button onClick={handleLogout} className="btn-ghost w-full text-xs text-gray-500">
            Log out
          </button>
        </div>
      ) : (
        /* ── Auth view ── */
        <div className="w-full max-w-sm">
          {/* Tabs */}
          <div className="flex border-b border-gray-700 mb-6">
            {['login', 'register'].map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-2 text-sm font-medium capitalize transition-colors
                  ${tab === t
                    ? 'text-blue-400 border-b-2 border-blue-400'
                    : 'text-gray-500 hover:text-gray-300'
                  }`}
              >
                {t}
              </button>
            ))}
          </div>

          {tab === 'login' ? (
            <LoginForm
              onLogin={async (username, password) => { await login(username, password); window.location.reload(); }}
              loading={authLoading}
              error={authError}
            />
          ) : (
            <RegisterForm
              onRegister={async (username, password) => { await register(username, password); setTab('login'); }}
              loading={authLoading}
              error={authError}
            />
          )}
        </div>
      )}
    </div>
  );
}
