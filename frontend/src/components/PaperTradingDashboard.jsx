import React, { useState, useEffect } from 'react';
import config from '../config/api';

const PaperTradingDashboard = () => {
  const [activeTrades, setActiveTrades] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedDays, setSelectedDays] = useState(7);
  const [prevActiveCount, setPrevActiveCount] = useState(0);

  // Delete a paper trade
  const deletePaperTrade = async (tradeId) => {
    if (!window.confirm('Delete this paper trade?')) return;
    try {
      const response = await fetch(`${config.API_BASE_URL}/paper-trades/${tradeId}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        await loadData();
      }
    } catch (error) {
      console.error('Failed to delete paper trade:', error);
    }
  };

  // Fetch active paper trades
  const fetchActiveTrades = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/paper-trades/active`);
      const data = await response.json();
      if (data.success) {
        setActiveTrades(data.trades);
        
        // Detect when a trade closes (active count goes from 1 to 0)
        if (prevActiveCount === 1 && data.trades.length === 0) {
          console.log('Trade closed! Emitting event for next trade...');
          // Emit custom event for parent component to detect trade closure
          window.dispatchEvent(new CustomEvent('tradeClosedEvent', { detail: { closedAt: new Date() } }));
        }
        setPrevActiveCount(data.trades.length);
      }
    } catch (error) {
      console.error('Failed to fetch active paper trades:', error);
    }
  };

  // Fetch trade history
  const fetchTradeHistory = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/paper-trades/history?days=${selectedDays}`);
      const data = await response.json();
      if (data.success) {
        setTradeHistory(data.trades);
      }
    } catch (error) {
      console.error('Failed to fetch trade history:', error);
    }
  };

  // Fetch performance stats
  const fetchPerformance = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/paper-trades/performance?days=${selectedDays}`);
      const data = await response.json();
      if (data.success) {
        setPerformance(data);
      }
    } catch (error) {
      console.error('Failed to fetch performance:', error);
    }
  };

  // Load all data
  const loadData = async () => {
    setLoading(true);
    await Promise.all([
      fetchActiveTrades(),
      fetchTradeHistory(),
      fetchPerformance()
    ]);
    setLoading(false);
  };

  // Update prices for all open trades
  const updatePrices = async () => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/paper-trades/update-prices`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        // Refresh data after price update
        await loadData();
      }
    } catch (error) {
      console.error('Failed to update prices:', error);
    }
  };

  useEffect(() => {
    loadData();
    
    // Update prices every 3 seconds for real-time SL/Target detection
    const priceUpdateInterval = setInterval(updatePrices, 3000);
    
    return () => {
      clearInterval(priceUpdateInterval);
    };
  }, [selectedDays]);

  // Calculate P&L color
  const getPnLColor = (pnl) => {
    if (!pnl) return '#718096';
    return pnl > 0 ? '#48bb78' : pnl < 0 ? '#f56565' : '#718096';
  };

  if (loading && !performance) {
    return (
      <div style={{ padding: '32px', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', color: '#718096' }}>
          Loading paper trading data...
        </div>
      </div>
    );
  }

  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.95)',
      borderRadius: '16px',
      padding: '32px',
      marginBottom: '32px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', color: '#2d3748' }}>
          📊 Paper Trading Performance
        </h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          <select
            value={selectedDays}
            onChange={(e) => setSelectedDays(Number(e.target.value))}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            <option value={1}>Today</option>
            <option value={7}>Last 7 Days</option>
            <option value={30}>Last 30 Days</option>
            <option value={90}>Last 90 Days</option>
          </select>
          <button
            onClick={loadData}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              background: '#667eea',
              color: 'white',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            🔄 Refresh
          </button>
          <button
            onClick={updatePrices}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              background: '#48bb78',
              color: 'white',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            📈 Update Prices
          </button>
        </div>
      </div>

      {/* Performance Stats */}
      {performance && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          marginBottom: '32px'
        }}>
          <div style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: '12px',
            padding: '20px',
            color: 'white'
          }}>
            <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '8px' }}>Total P&L</div>
            <div style={{ fontSize: '28px', fontWeight: 'bold' }}>
              {performance.total_pnl > 0 ? '+' : ''}₹{performance.total_pnl.toLocaleString()}
            </div>
            <div style={{ fontSize: '12px', marginTop: '8px', opacity: 0.9 }}>
              {performance.total_trades} trades
            </div>
          </div>

          <div style={{
            background: performance.win_rate >= 50 ? 'linear-gradient(135deg, #48bb78 0%, #38a169 100%)' : 'linear-gradient(135deg, #f56565 0%, #e53e3e 100%)',
            borderRadius: '12px',
            padding: '20px',
            color: 'white'
          }}>
            <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '8px' }}>Win Rate</div>
            <div style={{ fontSize: '28px', fontWeight: 'bold' }}>{performance.win_rate}%</div>
            <div style={{ fontSize: '12px', marginTop: '8px', opacity: 0.9 }}>
              {performance.winning_trades}W / {performance.losing_trades}L
            </div>
          </div>

          <div style={{
            background: 'linear-gradient(135deg, #4299e1 0%, #3182ce 100%)',
            borderRadius: '12px',
            padding: '20px',
            color: 'white'
          }}>
            <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '8px' }}>Avg P&L/Trade</div>
            <div style={{ fontSize: '28px', fontWeight: 'bold' }}>
              {performance.avg_pnl_per_trade > 0 ? '+' : ''}₹{performance.avg_pnl_per_trade.toLocaleString()}
            </div>
            <div style={{ fontSize: '12px', marginTop: '8px', opacity: 0.9 }}>
              Target: {performance.target_hits} | SL: {performance.sl_hits}
            </div>
          </div>

          <div style={{
            background: performance.open_pnl >= 0 ? 'linear-gradient(135deg, #38b2ac 0%, #319795 100%)' : 'linear-gradient(135deg, #ed8936 0%, #dd6b20 100%)',
            borderRadius: '12px',
            padding: '20px',
            color: 'white'
          }}>
            <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '8px' }}>Open Positions</div>
            <div style={{ fontSize: '28px', fontWeight: 'bold' }}>{performance.open_positions}</div>
            <div style={{ fontSize: '12px', marginTop: '8px', opacity: 0.9 }}>
              Unrealized: {performance.open_pnl > 0 ? '+' : ''}₹{performance.open_pnl.toLocaleString()}
            </div>
          </div>
        </div>
      )}

      {/* Best & Worst Trades */}
      {performance && (performance.best_trade || performance.worst_trade) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '32px' }}>
          {performance.best_trade && (
            <div style={{
              border: '2px solid #48bb78',
              borderRadius: '12px',
              padding: '16px',
              background: '#f0fff4'
            }}>
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#48bb78', marginBottom: '8px' }}>
                🏆 Best Trade
              </div>
              <div style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '4px' }}>
                {performance.best_trade.symbol}
              </div>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#48bb78' }}>
                +₹{performance.best_trade.pnl.toLocaleString()} ({performance.best_trade.pnl_percentage.toFixed(2)}%)
              </div>
            </div>
          )}
          
          {performance.worst_trade && (
            <div style={{
              border: '2px solid #f56565',
              borderRadius: '12px',
              padding: '16px',
              background: '#fff5f5'
            }}>
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#f56565', marginBottom: '8px' }}>
                📉 Worst Trade
              </div>
              <div style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '4px' }}>
                {performance.worst_trade.symbol}
              </div>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#f56565' }}>
                ₹{performance.worst_trade.pnl.toLocaleString()} ({performance.worst_trade.pnl_percentage.toFixed(2)}%)
              </div>
            </div>
          )}
        </div>
      )}

      {/* Active Paper Trades */}
      {activeTrades.length > 0 && (
        <div style={{ marginBottom: '32px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: 'bold', color: '#2d3748', margin: 0 }}>
              🔄 Active Paper Trades ({activeTrades.length})
            </h3>
            {activeTrades.length > 0 && (
              <div style={{
                padding: '8px 16px',
                borderRadius: '8px',
                background: '#fed7d7',
                color: '#742a2a',
                fontSize: '13px',
                fontWeight: '600'
              }}>
                🔒 ONE TRADE ACTIVE - Next signal will wait to close
              </div>
            )}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '14px',
              background: 'white',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <thead>
                <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Side</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Current</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Target</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Stop Loss</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>P&L</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>P&L %</th>
                  <th style={{ padding: '12px', textAlign: 'center' }}>SL Status</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Entry Time</th>
                  <th style={{ padding: '12px', textAlign: 'center' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {activeTrades.map((trade) => (
                  <tr key={trade.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '12px', fontWeight: '600' }}>{trade.symbol}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: '600',
                        background: trade.side === 'BUY' ? '#c6f6d5' : '#fed7d7',
                        color: trade.side === 'BUY' ? '#22543d' : '#742a2a'
                      }}>
                        {trade.side}
                      </span>
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>₹{trade.entry_price}</td>
                    <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600' }}>
                      ₹{trade.current_price || trade.entry_price}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>₹{trade.target || '--'}</td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>₹{trade.stop_loss || '--'}</td>
                    <td style={{
                      padding: '12px',
                      textAlign: 'right',
                      fontWeight: 'bold',
                      color: getPnLColor(trade.pnl)
                    }}>
                      {trade.pnl !== null && trade.pnl !== undefined ? (trade.pnl > 0 ? '+' : '') + '₹' + trade.pnl.toFixed(2) : (trade.current_price && trade.entry_price ? '₹' + ((trade.side === 'BUY' ? trade.current_price - trade.entry_price : trade.entry_price - trade.current_price) * trade.quantity).toFixed(2) : '--')}
                    </td>
                    <td style={{
                      padding: '12px',
                      textAlign: 'right',
                      fontWeight: 'bold',
                      color: getPnLColor(trade.pnl)
                    }}>
                      {trade.pnl_percentage !== null && trade.pnl_percentage !== undefined ? (trade.pnl_percentage > 0 ? '+' : '') + trade.pnl_percentage.toFixed(2) + '%' : (trade.current_price && trade.entry_price && trade.entry_price > 0 ? (((trade.side === 'BUY' ? trade.current_price - trade.entry_price : trade.entry_price - trade.current_price) / trade.entry_price) * 100).toFixed(2) + '%' : '--')}
                    </td>
                    {/* Trailing SL Status */}
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      {(() => {
                        const profit = trade.side === 'BUY' ? (trade.current_price || trade.entry_price) - trade.entry_price : trade.entry_price - (trade.current_price || trade.entry_price);
                        
                        // Check if target reached
                        const targetReached = trade.target && (
                          (trade.side === 'BUY' && (trade.current_price || trade.entry_price) >= trade.target) ||
                          (trade.side === 'SELL' && (trade.current_price || trade.entry_price) <= trade.target)
                        );
                        
                        // Target reached - 5pt trailing SL active (don't close, keep trailing)
                        if (targetReached) {
                          return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'center' }}>
                              <span style={{ padding: '4px 8px', borderRadius: '4px', background: '#a78bfa', color: '#ffffff', fontWeight: '600', fontSize: '11px' }}>🚀 TRAILING +5PT</span>
                              <span style={{ fontSize: '10px', color: '#666', fontWeight: '600' }}>Target hit! Let it run...</span>
                            </div>
                          );
                        } else if (profit > 15) {
                          return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'center' }}>
                              <span style={{ padding: '4px 8px', borderRadius: '4px', background: '#c6f6d5', color: '#22543d', fontWeight: '600', fontSize: '11px' }}>🔄 TRAILING</span>
                              <span style={{ fontSize: '10px', color: '#666' }}>+{profit.toFixed(0)}pts</span>
                            </div>
                          );
                        } else if (profit > 5) {
                          return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'center' }}>
                              <span style={{ padding: '4px 8px', borderRadius: '4px', background: '#feebc8', color: '#92400e', fontWeight: '600', fontSize: '11px' }}>📌 BREAKEVEN</span>
                              <span style={{ fontSize: '10px', color: '#666' }}>+{profit.toFixed(1)}pts</span>
                            </div>
                          );
                        } else {
                          return <span style={{ padding: '4px 8px', borderRadius: '4px', background: '#bee3f8', color: '#2c5282', fontWeight: '600', fontSize: '11px' }}>🎯 NORMAL</span>;
                        }
                      })()}
                    </td>
                    <td style={{ padding: '12px', fontSize: '12px', color: '#718096' }}>
                      {trade.entry_time ? new Date(trade.entry_time).toLocaleString() : '--'}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      <button
                        onClick={() => deletePaperTrade(trade.id)}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '4px',
                          border: 'none',
                          background: '#f56565',
                          color: 'white',
                          fontSize: '12px',
                          fontWeight: '600',
                          cursor: 'pointer'
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trade History */}
      <div>
        <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px', color: '#2d3748' }}>
          📜 Recent Closed Trades ({tradeHistory.length})
        </h3>
        {tradeHistory.length === 0 ? (
          <div style={{
            padding: '40px',
            textAlign: 'center',
            background: '#f7fafc',
            borderRadius: '12px',
            color: '#718096'
          }}>
            No closed paper trades yet. Signals will be automatically tracked.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '14px',
              background: 'white',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <thead>
                <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Side</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Status</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Entry Price</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Exit Price</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Target</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Stop Loss</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>P&L</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>P&L %</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Entry Time</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Exit Time</th>
                  <th style={{ padding: '12px', textAlign: 'center' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {tradeHistory.map((trade) => (
                  <tr key={trade.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '12px', fontWeight: '600' }}>{trade.symbol}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: '600',
                        background: trade.side === 'BUY' ? '#c6f6d5' : '#fed7d7',
                        color: trade.side === 'BUY' ? '#22543d' : '#742a2a'
                      }}>
                        {trade.side}
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: '600',
                        background: trade.status === 'TARGET_HIT' ? '#c6f6d5' : trade.status === 'SL_HIT' ? '#fed7d7' : '#e2e8f0',
                        color: trade.status === 'TARGET_HIT' ? '#22543d' : trade.status === 'SL_HIT' ? '#742a2a' : '#4a5568'
                      }}>
                        {trade.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>₹{trade.entry_price}</td>
                    <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600' }}>
                      ₹{trade.exit_price || trade.current_price}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', fontSize: '12px', color: '#718096' }}>
                      ₹{trade.target || '--'}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', fontSize: '12px', color: '#718096' }}>
                      ₹{trade.stop_loss || '--'}
                    </td>
                    <td style={{
                      padding: '12px',
                      textAlign: 'right',
                      fontWeight: 'bold',
                      color: getPnLColor(trade.pnl)
                    }}>
                      {trade.pnl ? (trade.pnl > 0 ? '+' : '') + '₹' + trade.pnl.toFixed(2) : '--'}
                    </td>
                    <td style={{
                      padding: '12px',
                      textAlign: 'right',
                      fontWeight: 'bold',
                      color: getPnLColor(trade.pnl)
                    }}>
                      {trade.pnl_percentage ? (trade.pnl_percentage > 0 ? '+' : '') + trade.pnl_percentage.toFixed(2) + '%' : '--'}
                    </td>
                    <td style={{ padding: '12px', fontSize: '12px', color: '#718096' }}>
                      {trade.entry_time ? new Date(trade.entry_time).toLocaleString() : '--'}
                    </td>
                    <td style={{ padding: '12px', fontSize: '12px', color: '#718096' }}>
                      {trade.exit_time ? new Date(trade.exit_time).toLocaleString() : '--'}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      <button
                        onClick={() => deletePaperTrade(trade.id)}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '4px',
                          border: 'none',
                          background: '#f56565',
                          color: 'white',
                          fontSize: '12px',
                          fontWeight: '600',
                          cursor: 'pointer'
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default PaperTradingDashboard;
