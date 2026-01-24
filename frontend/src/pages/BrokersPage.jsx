import React, { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import axios from 'axios';
import config from '../config/api';

const API_URL = config.API_BASE_URL;

export default function BrokersPage() {
  const [brokers, setBrokers] = useState([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    broker_name: 'zerodha',
    api_key: '',
    api_secret: '',
  });

  useEffect(() => {
    fetchBrokers();
  }, []);

  const fetchBrokers = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_URL}/brokers/credentials`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setBrokers(response.data);
    } catch (error) {
      if (error.response?.status !== 404) {
        toast.error('Failed to load broker credentials');
      }
    }
  };

  const handleAddBroker = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      await axios.post(
        `${API_URL}/brokers/credentials`,
        formData,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      
      toast.success('Broker credentials added successfully');
      setShowAddForm(false);
      setFormData({ broker_name: 'zerodha', api_key: '', api_secret: '' });
      fetchBrokers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add broker');
    } finally {
      setIsLoading(false);
    }
  };

  const handleZerodhaLogin = async (brokerId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_URL}/brokers/zerodha/login/${brokerId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      
      if (response.data.login_url) {
        window.open(response.data.login_url, '_blank');
        toast.success('Please complete Zerodha login in the new window');
      }
    } catch (error) {
      toast.error('Failed to initiate Zerodha login');
    }
  };

  const handleDeleteBroker = async (brokerName) => {
    if (!confirm(`Delete ${brokerName} credentials?`)) return;

    try {
      const token = localStorage.getItem('access_token');
      await axios.delete(
        `${API_URL}/brokers/credentials/${brokerName}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      
      toast.success('Broker credentials deleted');
      fetchBrokers();
    } catch (error) {
      toast.error('Failed to delete broker');
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Broker Connections</h1>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition"
        >
          {showAddForm ? 'Cancel' : '+ Add Broker'}
        </button>
      </div>

      {/* Add Broker Form */}
      {showAddForm && (
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-bold mb-4">Add Broker Credentials</h2>
          <form onSubmit={handleAddBroker} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Broker
              </label>
              <select
                value={formData.broker_name}
                onChange={(e) => setFormData({ ...formData, broker_name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="zerodha">Zerodha</option>
                <option value="upstox">Upstox</option>
                <option value="angel_one">Angel One</option>
                <option value="groww">Groww</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                API Key
              </label>
              <input
                type="text"
                value={formData.api_key}
                onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your API key"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                API Secret
              </label>
              <input
                type="password"
                value={formData.api_secret}
                onChange={(e) => setFormData({ ...formData, api_secret: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your API secret"
                required
              />
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-sm text-blue-800">
                <strong>📝 How to get API credentials:</strong>
                <br />
                <strong>Zerodha:</strong> Visit <a href="https://kite.zerodha.com" target="_blank" className="underline">kite.zerodha.com</a> → My Profile → Apps → Create new app
                <br />
                <strong>Upstox:</strong> Visit <a href="https://upstox.com/developer" target="_blank" className="underline">upstox.com/developer</a>
                <br />
                <strong>Angel One:</strong> Visit <a href="https://smartapi.angelbroking.com" target="_blank" className="underline">smartapi.angelbroking.com</a>
              </p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-400"
            >
              {isLoading ? 'Adding...' : 'Add Broker'}
            </button>
          </form>
        </div>
      )}

      {/* Brokers List */}
      <div className="grid gap-4">
        {brokers.length === 0 ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-8 text-center">
            <div className="text-4xl mb-4">🔌</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">No Brokers Connected</h3>
            <p className="text-gray-600 mb-4">
              Connect your broker account to start trading with real market data
            </p>
            <button
              onClick={() => setShowAddForm(true)}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition"
            >
              Add Your First Broker
            </button>
          </div>
        ) : (
          brokers.map((broker) => (
            <div key={broker.id} className="bg-white rounded-lg shadow p-6">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    <h3 className="text-xl font-bold text-gray-900 capitalize">
                      {broker.broker_name}
                    </h3>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      broker.access_token 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-yellow-100 text-yellow-800'
                    }`}>
                      {broker.access_token ? '✓ Connected' : '⚠ Authentication Required'}
                    </span>
                  </div>

                  <div className="space-y-2 text-sm text-gray-600">
                    <p><strong>API Key:</strong> {broker.api_key.substring(0, 8)}...</p>
                    <p><strong>Added:</strong> {new Date(broker.created_at).toLocaleDateString()}</p>
                    {broker.last_used && (
                      <p><strong>Last Used:</strong> {new Date(broker.last_used).toLocaleString()}</p>
                    )}
                  </div>

                  {broker.broker_name.toLowerCase() === 'zerodha' && !broker.access_token && (
                    <div className="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-3">
                      <p className="text-sm text-blue-800 mb-2">
                        Complete Zerodha login to activate real-time trading
                      </p>
                      <button
                        onClick={() => handleZerodhaLogin(broker.id)}
                        className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 transition"
                      >
                        🔐 Login to Zerodha
                      </button>
                    </div>
                  )}
                </div>

                <button
                  onClick={() => handleDeleteBroker(broker.broker_name)}
                  className="text-red-600 hover:text-red-800 ml-4"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Instructions */}
      <div className="mt-8 bg-gray-50 rounded-lg p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">📚 Setup Instructions</h3>
        <div className="space-y-3 text-sm text-gray-700">
          <p><strong>Step 1:</strong> Click "Add Broker" and enter your API credentials</p>
          <p><strong>Step 2:</strong> For Zerodha, click "Login to Zerodha" to complete OAuth</p>
          <p><strong>Step 3:</strong> Once connected, you'll see real-time data on the dashboard</p>
          <p className="mt-4 text-xs text-gray-500">
            ⚠️ Your API credentials are encrypted and stored securely. Never share your API keys with anyone.
          </p>
        </div>
      </div>
    </div>
  );
}
