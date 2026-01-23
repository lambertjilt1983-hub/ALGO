import React, { useEffect, useState } from 'react';
import { Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ordersAPI, strategiesAPI, marketAPI } from '../api/client';
import toast from 'react-hot-toast';

export default function Dashboard() {
  const [orders, setOrders] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [indices, setIndices] = useState(null);
  const [stats, setStats] = useState({
    totalOrders: 0,
    totalStrategies: 0,
    activeStrategies: 0,
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [ordersRes, strategiesRes] = await Promise.all([
          ordersAPI.listOrders(),
          strategiesAPI.listStrategies(),
        ]);

        setOrders(ordersRes.data);
        setStrategies(strategiesRes.data);

        setStats({
          totalOrders: ordersRes.data.length,
          totalStrategies: strategiesRes.data.length,
          activeStrategies: strategiesRes.data.filter((s) => s.is_live).length,
        });
      } catch (error) {
        toast.error('Failed to load dashboard');
      } finally {
        setIsLoading(false);
      }
    };

    const fetchIndices = async () => {
      try {
        const response = await marketAPI.getLiveIndices();
        if (response.data.success) {
          setIndices(response.data.indices);
        }
      } catch (error) {
        console.error('Error fetching indices:', error);
      }
    };

    fetchData();
    fetchIndices();
    
    // Refresh indices every 5 seconds
    const interval = setInterval(fetchIndices, 5000);
    return () => clearInterval(interval);
  }, []);

  const chartData = [
    { name: 'Jan', wins: 12, losses: 8 },
    { name: 'Feb', wins: 19, losses: 4 },
    { name: 'Mar', wins: 15, losses: 7 },
    { name: 'Apr', wins: 22, losses: 5 },
  ];

  if (isLoading) {
    return <div className="text-center py-10">Loading...</div>;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-4xl font-bold text-gray-900 mb-4">Dashboard</h1>

      {/* Live Market Indices */}
      {indices && (
        <div className="bg-gradient-to-r from-blue-600 to-blue-800 text-white rounded-lg shadow-lg p-4 mb-8">
          <div className="flex flex-wrap justify-center gap-6">
            <div className="flex flex-col items-center">
              <span className="text-xs font-medium opacity-90">NIFTY 50</span>
              <div className="flex items-center space-x-2">
                <span className="text-2xl font-bold">{indices.NIFTY?.value?.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                <span className={`text-sm font-semibold px-2 py-1 rounded ${indices.NIFTY?.change >= 0 ? 'bg-green-500' : 'bg-red-500'}`}>
                  {indices.NIFTY?.change >= 0 ? '▲' : '▼'} {Math.abs(indices.NIFTY?.change_percent || 0).toFixed(2)}%
                </span>
              </div>
            </div>
            <div className="w-px h-12 bg-white/30"></div>
            <div className="flex flex-col items-center">
              <span className="text-xs font-medium opacity-90">BANK NIFTY</span>
              <div className="flex items-center space-x-2">
                <span className="text-2xl font-bold">{indices.BANKNIFTY?.value?.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                <span className={`text-sm font-semibold px-2 py-1 rounded ${indices.BANKNIFTY?.change >= 0 ? 'bg-green-500' : 'bg-red-500'}`}>
                  {indices.BANKNIFTY?.change >= 0 ? '▲' : '▼'} {Math.abs(indices.BANKNIFTY?.change_percent || 0).toFixed(2)}%
                </span>
              </div>
            </div>
            <div className="w-px h-12 bg-white/30"></div>
            <div className="flex flex-col items-center">
              <span className="text-xs font-medium opacity-90">SENSEX</span>
              <div className="flex items-center space-x-2">
                <span className="text-2xl font-bold">{indices.SENSEX?.value?.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                <span className={`text-sm font-semibold px-2 py-1 rounded ${indices.SENSEX?.change >= 0 ? 'bg-green-500' : 'bg-red-500'}`}>
                  {indices.SENSEX?.change >= 0 ? '▲' : '▼'} {Math.abs(indices.SENSEX?.change_percent || 0).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Total Orders</p>
          <p className="text-3xl font-bold text-blue-600">{stats.totalOrders}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Total Strategies</p>
          <p className="text-3xl font-bold text-green-600">{stats.totalStrategies}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Active Strategies</p>
          <p className="text-3xl font-bold text-purple-600">{stats.activeStrategies}</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Trade Performance</h2>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorWins" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#8884d8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="name" />
              <YAxis />
              <CartesianGrid strokeDasharray="3 3" />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="wins"
                stroke="#8884d8"
                fillOpacity={1}
                fill="url(#colorWins)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Recent Orders</h2>
          <div className="space-y-2">
            {orders.slice(0, 5).map((order) => (
              <div
                key={order.id}
                className="flex justify-between items-center p-3 bg-gray-50 rounded"
              >
                <div>
                  <p className="font-medium text-gray-900">{order.symbol}</p>
                  <p className="text-sm text-gray-600">{order.order_type}</p>
                </div>
                <div className="text-right">
                  <p
                    className={`font-medium ${
                      order.side === 'buy' ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {order.side.toUpperCase()} {order.quantity}
                  </p>
                  <p className="text-sm text-gray-600">{order.status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Strategies */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Active Strategies</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {strategies.map((strategy) => (
                <tr key={strategy.id}>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    {strategy.name}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {strategy.strategy_type}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        strategy.is_live
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {strategy.is_live ? 'Live' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {new Date(strategy.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
