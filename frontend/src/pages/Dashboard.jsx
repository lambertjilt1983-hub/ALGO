import React, { useEffect, useState } from 'react';
import axios from 'axios';
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
  const [signals, setSignals] = useState([]);
  const [activeTrade, setActiveTrade] = useState(null);

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

    const fetchSignals = async () => {
      try {
        const response = await axios.post('/autotrade/analyze?symbol=NIFTY,BANKNIFTY,FINNIFTY&balance=100000');
        if (response.data && response.data.signals) {
          setSignals(response.data.signals);
        }
      } catch (error) {
        console.error('Error fetching signals:', error);
      }
    };

    const fetchActiveTrade = async () => {
      try {
        const response = await axios.get('/autotrade/trades/active');
        if (response.data && response.data.length > 0) {
          setActiveTrade(response.data[0]);
        } else {
          setActiveTrade(null);
        }
      } catch (error) {
        setActiveTrade(null);
      }
    };

    fetchData();
    fetchIndices();
    fetchSignals();
    fetchActiveTrade();

    // Refresh signals and active trade every 10 seconds
    const interval = setInterval(() => {
      fetchSignals();
      fetchActiveTrade();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Auto-trade for signals with confidence > 80 if no active trade
    if (!activeTrade && signals.length > 0) {
      const highConf = signals.filter(s => s.confidence > 80);
      if (highConf.length > 0) {
        const sig = highConf[0];
        axios.post('/autotrade/execute', {
          symbol: sig.symbol,
          price: sig.entry_price,
          quantity: sig.quantity,
          side: sig.action,
          stop_loss: sig.stop_loss,
          target: sig.target,
          expiry: sig.expiry_date || sig.expiry,
        }).then(() => {
          toast.success(`Auto-trade executed for ${sig.symbol}`);
        }).catch(() => {
          toast.error('Auto-trade failed');
        });
      }
    }
  }, [signals, activeTrade]);

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
            {/* ...existing code... */}
          </div>
        </div>
      )}

      {/* All Strategy Signals (including CE/PE) */}
      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4">All Strategy Signals (including CE/PE)</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-2 py-2">Strategy</th>
                <th className="px-2 py-2">Symbol</th>
                <th className="px-2 py-2">Action</th>
                <th className="px-2 py-2">Confidence</th>
                <th className="px-2 py-2">Quantity</th>
                <th className="px-2 py-2">Entry</th>
                <th className="px-2 py-2">Target</th>
                <th className="px-2 py-2">Stop Loss</th>
                <th className="px-2 py-2">Expiry</th>
                <th className="px-2 py-2">Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {signals.map((sig, idx) => (
                <tr key={idx}>
                  <td className="px-2 py-2">{sig.strategy}</td>
                  <td className="px-2 py-2">{sig.symbol}</td>
                  <td className="px-2 py-2">{sig.action}</td>
                  <td className="px-2 py-2">{sig.confidence}%</td>
                  <td className="px-2 py-2">{sig.quantity}</td>
                  <td className="px-2 py-2">₹{sig.entry_price}</td>
                  <td className="px-2 py-2">₹{sig.target}</td>
                  <td className="px-2 py-2">₹{sig.stop_loss}</td>
                  <td className="px-2 py-2">{sig.expiry_date || sig.expiry}</td>
                  <td className="px-2 py-2">{sig.option_type || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ...existing code... */}

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
