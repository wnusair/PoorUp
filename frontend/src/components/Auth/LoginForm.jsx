import { useState } from 'react';

export default function LoginForm({ onLogin, loading, error }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    onLogin(username.trim(), password);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">Username</label>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white
                     placeholder-gray-400 focus:outline-none focus:border-blue-500 transition"
          placeholder="Enter username"
          autoComplete="username"
          disabled={loading}
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white
                     placeholder-gray-400 focus:outline-none focus:border-blue-500 transition"
          placeholder="Enter password"
          autoComplete="current-password"
          disabled={loading}
          required
        />
      </div>
      {error && (
        <p className="text-red-400 text-sm bg-red-900/30 border border-red-800 rounded px-3 py-2">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={loading || !username.trim() || !password.trim()}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900 disabled:cursor-not-allowed
                   text-white font-semibold py-2 rounded-lg transition"
      >
        {loading ? 'Signing in…' : 'Sign In'}
      </button>
    </form>
  );
}
