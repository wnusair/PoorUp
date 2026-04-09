import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-950 text-center p-6">
      <h1 className="text-6xl font-extrabold text-gray-700 mb-4">404</h1>
      <p className="text-gray-400 mb-8">This page doesn't exist.</p>
      <Link to="/" className="btn-primary">Back to Home</Link>
    </div>
  );
}
