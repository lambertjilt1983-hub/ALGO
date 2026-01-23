import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store';
import { marketAPI } from '../api/client';

export default function Navbar() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [indices, setIndices] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) {
      fetchIndices();
      // Refresh indices every 5 seconds
      const interval = setInterval(fetchIndices, 5000);
      return () => clearInterval(interval);
    }
  }, [user]);

  const fetchIndices = async () => {
    try {
      const response = await marketAPI.getLiveIndices();
      if (response.data.success) {
        setIndices(response.data.indices);
      }
      setLoading(false);
    } catch (error) {
      console.error('Error fetching indices:', error);
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <nav className="bg-gradient-to-r from-blue-600 to-blue-800 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link to="/" className="text-2xl font-bold">
              🚀 AlgoTrade Pro
            </Link>
            {user && (
              <div className="hidden md:flex space-x-4">
                <Link to="/dashboard" className="hover:text-blue-200 transition">
                  Dashboard
                </Link>
                <Link to="/brokers" className="hover:text-blue-200 transition">
                  Brokers
                </Link>
                <Link to="/orders" className="hover:text-blue-200 transition">
                  Orders
                </Link>
                <Link to="/strategies" className="hover:text-blue-200 transition">
                  Strategies
                </Link>
                <Link to="/market" className="hover:text-blue-200 transition">
                  Market Intelligence
                </Link>
              </div>
            )}
          </div>
          <div className="flex items-center space-x-4">
            {user ? (
              <>
                {/* Live Market Indices */}
                {!loading && indices && (
                  <div className="hidden md:flex items-center space-x-3 bg-white/10 rounded-lg px-3 py-1.5 backdrop-blur-sm">
                    <div className="flex items-center space-x-1">
                      <span className="text-xs font-medium">NIFTY</span>
                      <span className="text-sm font-bold">{indices.NIFTY.value.toLocaleString('en-IN')}</span>
                      <span className={`text-xs ${indices.NIFTY.change >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                        {indices.NIFTY.change >= 0 ? '▲' : '▼'} {Math.abs(indices.NIFTY.change_percent)}%
                      </span>
                    </div>
                    <div className="w-px h-6 bg-white/30"></div>
                    <div className="flex items-center space-x-1">
                      <span className="text-xs font-medium">BANK</span>
                      <span className="text-sm font-bold">{indices.BANKNIFTY.value.toLocaleString('en-IN')}</span>
                      <span className={`text-xs ${indices.BANKNIFTY.change >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                        {indices.BANKNIFTY.change >= 0 ? '▲' : '▼'} {Math.abs(indices.BANKNIFTY.change_percent)}%
                      </span>
                    </div>
                    <div className="w-px h-6 bg-white/30"></div>
                    <div className="flex items-center space-x-1">
                      <span className="text-xs font-medium">SENSEX</span>
                      <span className="text-sm font-bold">{indices.SENSEX.value.toLocaleString('en-IN')}</span>
                      <span className={`text-xs ${indices.SENSEX.change >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                        {indices.SENSEX.change >= 0 ? '▲' : '▼'} {Math.abs(indices.SENSEX.change_percent)}%
                      </span>
                    </div>
                  </div>
                )}
                <span className="text-sm">{user.username}</span>
                <button
                  onClick={handleLogout}
                  className="bg-red-500 hover:bg-red-600 px-4 py-2 rounded transition"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="hover:text-blue-200 transition">
                  Login
                </Link>
                <Link
                  to="/register"
                  className="bg-green-500 hover:bg-green-600 px-4 py-2 rounded transition"
                >
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
