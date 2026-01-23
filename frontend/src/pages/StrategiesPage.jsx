import React, { useEffect, useState } from 'react';
import { strategiesAPI } from '../api/client';
import toast from 'react-hot-toast';

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState([]);
  const [showNewStrategy, setShowNewStrategy] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    strategy_type: 'ma_crossover',
    parameters: {
      fast_period: 20,
      slow_period: 50,
      stop_loss_percent: 2,
      take_profit_percent: 5,
    },
  });

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async () => {
    try {
      const response = await strategiesAPI.listStrategies();
      setStrategies(response.data);
    } catch (error) {
      toast.error('Failed to load strategies');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateStrategy = async (e) => {
    e.preventDefault();
    try {
      await strategiesAPI.createStrategy(formData);
      toast.success('Strategy created successfully');
      setShowNewStrategy(false);
      setFormData({
        name: '',
        description: '',
        strategy_type: 'ma_crossover',
        parameters: {
          fast_period: 20,
          slow_period: 50,
          stop_loss_percent: 2,
          take_profit_percent: 5,
        },
      });
      fetchStrategies();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create strategy');
    }
  };

  const handleBacktest = async (strategyId) => {
    try {
      const response = await strategiesAPI.backtest(strategyId, {
        start_date: '2023-01-01',
        end_date: '2024-01-01',
        initial_capital: 100000,
      });
      toast.success(
        `Backtest completed. Return: ${(response.data.total_return * 100).toFixed(2)}%`
      );
    } catch (error) {
      toast.error('Backtest failed');
    }
  };

  if (isLoading) {
    return <div className="text-center py-10">Loading...</div>;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Trading Strategies</h1>
        <button
          onClick={() => setShowNewStrategy(!showNewStrategy)}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition"
        >
          {showNewStrategy ? 'Cancel' : 'New Strategy'}
        </button>
      </div>

      {showNewStrategy && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Create New Strategy</h2>
          <form onSubmit={handleCreateStrategy} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Name
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                rows="3"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Strategy Type
              </label>
              <select
                value={formData.strategy_type}
                onChange={(e) =>
                  setFormData({ ...formData, strategy_type: e.target.value })
                }
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="ma_crossover">Moving Average Crossover</option>
                <option value="rsi">RSI Strategy</option>
                <option value="momentum">Momentum Strategy</option>
              </select>
            </div>

            <button
              type="submit"
              className="w-full bg-green-600 text-white py-2 rounded-md hover:bg-green-700 transition"
            >
              Create Strategy
            </button>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {strategies.map((strategy) => (
          <div key={strategy.id} className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-xl font-bold text-gray-900">
                  {strategy.name}
                </h3>
                <p className="text-sm text-gray-600">{strategy.description}</p>
              </div>
              <span
                className={`px-3 py-1 rounded text-xs font-medium ${
                  strategy.is_live
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                {strategy.is_live ? 'Live' : 'Inactive'}
              </span>
            </div>

            <div className="bg-gray-50 rounded p-4 mb-4">
              <p className="text-sm font-medium text-gray-700 mb-2">
                Type: {strategy.strategy_type}
              </p>
              <p className="text-xs text-gray-600">
                Created: {new Date(strategy.created_at).toLocaleDateString()}
              </p>
            </div>

            <div className="flex space-x-2">
              <button
                onClick={() => handleBacktest(strategy.id)}
                className="flex-1 bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 transition text-sm"
              >
                Backtest
              </button>
              <button className="flex-1 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition text-sm">
                Edit
              </button>
              <button className="flex-1 bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 transition text-sm">
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
