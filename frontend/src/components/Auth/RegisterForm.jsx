import { useState } from 'react';

export default function RegisterForm({ onRegister, loading, error }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [localError, setLocalError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    setLocalError('');
    if (!username.trim()) return setLocalError('Username is required');
    if (password.length < 6) return setLocalError('Password must be at least 6 characters');
    if (password !== confirm) return setLocalError('Passwords do not match');
    onRegister(username.trim(), password);
  };

  const displayError = localError || error;

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
          placeholder="Choose a username"
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
          placeholder="Choose a password"
          autoComplete="new-password"
          disabled={loading}
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">Confirm Password</label>
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white
                     placeholder-gray-400 focus:outline-none focus:border-blue-500 transition"
          placeholder="Confirm password"
          autoComplete="new-password"
          disabled={loading}
          required
        />
      </div>
      {displayError && (
        <p className="text-red-400 text-sm bg-red-900/30 border border-red-800 rounded px-3 py-2">
          {displayError}
        </p>
      )}
      <button
        type="submit"
        disabled={loading || !username.trim() || !password || !confirm}
        className="w-full bg-green-600 hover:bg-green-700 disabled:bg-green-900 disabled:cursor-not-allowed
                   text-white font-semibold py-2 rounded-lg transition"
      >
        {loading ? 'Registering…' : 'Create Account'}
      </button>
    </form>
  );
}
