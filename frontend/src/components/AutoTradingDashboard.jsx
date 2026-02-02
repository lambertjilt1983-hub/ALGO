import React, { useState, useEffect } from 'react';
import PaperTradingDashboard from './PaperTradingDashboard';

// Use environment-based API URL if available
import config from '../config/api';
const OPTION_SIGNALS_API = `${config.API_BASE_URL}/option-signals/intraday`;
const PROFESSIONAL_SIGNAL_API = `${config.API_BASE_URL}/strategies/live/professional-signal`;

const AutoTradingDashboard = () => {
  const [enabled, setEnabled] = useState(false);
  // Force LIVE mode only
  const isDemoMode = false;
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [activeTrades, setActiveTrades] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [reportSummary, setReportSummary] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [optionSignals, setOptionSignals] = useState([]);
  const [executing, setExecuting] = useState(false);
  const [livePrice, setLivePrice] = useState(null);
  const [activeTab, setActiveTab] = useState('trading');
  const [historySearch, setHistorySearch] = useState('');
  const [lotMultiplier, setLotMultiplier] = useState(1); // For quantity adjustment
  const [autoTradingActive, setAutoTradingActive] = useState(false);
  const [hasActiveTrade, setHasActiveTrade] = useState(false);
  const [showPaperTrading, setShowPaperTrading] = useState(false);
  const [lastLoggedSignal, setLastLoggedSignal] = useState(null);

  // --- Professional Signal Integration ---
  const [professionalSignal, setProfessionalSignal] = useState(null);
  useEffect(() => {
    const fetchProfessionalSignal = async () => {
      try {
        const res = await config.authFetch(PROFESSIONAL_SIGNAL_API);
        const data = await res.json();
        setProfessionalSignal(data);
      } catch (err) {
        setProfessionalSignal({ error: err.message });
      }
    };
    fetchProfessionalSignal();
    const interval = setInterval(fetchProfessionalSignal, 60000); // refresh every 60s
    return () => clearInterval(interval);
  }, []);

  // Remove legacy fetchData logic (config references)
  const fetchData = async () => {
    setLoading(false);
  };

  // Remove legacy analyzeMarket logic (config references)
  const analyzeMarket = async () => {};

  // Remove toggleMode, always live
  const toggleMode = () => {};

  // Fetch option signals from backend
  useEffect(() => {
    const fetchOptionSignals = async () => {
      try {
        const res = await fetch(OPTION_SIGNALS_API);
        const data = await res.json();
        setOptionSignals(data.signals || []);
      } catch (e) {
        setOptionSignals([]);
      }
    };
    fetchOptionSignals();
  }, []);
  // Render option signals table
  const renderOptionSignalsTable = () => (
    <div style={{ margin: '32px 0' }}>
      <h3>Intraday Option Signals</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px', background: 'white', borderRadius: '8px', overflow: 'hidden' }}>
        <thead>
          <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
            <th>Index</th>
            <th>Strike</th>
            <th>CE Signal</th>
            <th>PE Signal</th>
            <th>Sentiment</th>
            <th>Expiry Zone</th>
            <th>Risk Note</th>
          </tr>
        </thead>
        <tbody>
          {optionSignals.map((s, idx) => (
            <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
              <td>{s.index}</td>
              <td>{s.strike ?? '--'}</td>
              <td>{s.ce_signal ?? '--'}</td>
              <td>{s.pe_signal ?? '--'}</td>
              <td>{s.sentiment ?? '--'}</td>
              <td>{s.expiry_zone ?? '--'}</td>
              <td>{s.risk_note ?? (s.error ? `Error: ${s.error}` : '--')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  // Pick the best signal (highest confidence) from optionSignals
  const bestSignal = optionSignals.reduce((best, curr) =>
    (!best || (curr.confidence > best.confidence)) ? curr : best, null
  );

  // Auto-execute the best signal if available and auto-trading is active
  useEffect(() => {
    if (bestSignal && !executing && autoTradingActive && !hasActiveTrade) {
      executeAutoTrade(bestSignal);
    }
    // eslint-disable-next-line
  }, [bestSignal, autoTradingActive, hasActiveTrade]);

  // Remove legacy toggleAutoTrading logic (config references)
  const toggleAutoTrading = async () => {};

  // Implement auto trade execution using bestSignal
  const executeAutoTrade = async (signal) => {
    if (!signal || executing) return;
    
    // Check if auto-trading is active
    if (!autoTradingActive) return;
    
    // Only allow one trade at a time
    if (hasActiveTrade) {
      console.log('Trade already active, skipping...');
      return;
    }
    
    const token = localStorage.getItem('access_token');
    if (!token) {
      alert('No access token found. Please login.');
      return;
    }
    const adjustedQuantity = signal.quantity * lotMultiplier;
    const confirmMsg = `⚡ LIVE TRADE\n\nIndex: ${signal.index}\nSymbol: ${signal.symbol}\nAction: ${signal.action}\nStrike: ${signal.strike}\nQty: ${adjustedQuantity} (${lotMultiplier} lots)\nEntry: ₹${signal.entry_price}\nTarget: ₹${signal.target}\nStop Loss: ₹${signal.stop_loss}\n\nProceed with auto trade?`;
    if (!window.confirm(confirmMsg)) return;
    setExecuting(true);
    try {
      const params = {
        symbol: signal.symbol,
        price: signal.entry_price,
        target: signal.target,
        stop_loss: signal.stop_loss,
        quantity: adjustedQuantity,
        side: signal.action,
        expiry: signal.expiry_date,
        broker_id: 1,
        balance: 50000
      };
      const response = await config.authFetch(config.endpoints.autoTrade.execute, {
        method: 'POST',
        body: JSON.stringify(params)
      });
      if (response.ok) {
        const data = await response.json();
        setHasActiveTrade(true);
        alert(data.message || 'Trade executed!');
      } else {
        let errorMsg = 'Failed to execute trade.';
        try {
          const errData = await response.json();
          if (errData.message) errorMsg += '\nReason: ' + errData.message;
          if (errData.detail) errorMsg += '\nDetail: ' + errData.detail;
        } catch {}
        alert(errorMsg);
      }
    } catch (e) {
      alert('Error executing trade: ' + e.message);
    } finally {
      setExecuting(false);
    }
  };

  // Arm live trading
  const armLiveTrading = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      alert('No access token found. Please login.');
      return;
    }
    try {
      const response = await config.authFetch(config.endpoints.autoTrade.arm || '/autotrade/arm', {
        method: 'POST',
        body: JSON.stringify(true)
      });
      if (response.ok) {
        const data = await response.json();
        alert('Live trading armed!');
        setEnabled(true);
      } else {
        alert('Failed to arm live trading.');
      }
    } catch (e) {
      alert('Error arming live trading: ' + e.message);
    }
  };

  // Log paper trade when signal appears (if not auto-trading)
  const logPaperTrade = async (signal) => {
    try {
      // Check if there's an active open trade - if yes, don't log new signal
      const activesResponse = await fetch(`${config.API_BASE_URL}/paper-trades/active`);
      const activesData = await activesResponse.json();
      
      if (activesData.success && activesData.trades && activesData.trades.length > 0) {
        console.log('Active trade exists. Waiting for it to close before logging new signal.');
        return; // Don't log new signal if one is already active
      }

      const response = await fetch(`${config.API_BASE_URL}/paper-trades`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: signal.symbol,
          index_name: signal.index || signal.index_name,
          side: signal.action,
          signal_type: signal.signal_type || signal.type,
          quantity: signal.quantity * lotMultiplier,
          entry_price: signal.entry_price,
          stop_loss: signal.stop_loss,
          target: signal.target,
          strategy: signal.strategy || 'professional',
          signal_data: signal
        })
      });
      
      if (response.ok) {
        console.log('Paper trade logged successfully for', signal.symbol);
      }
    } catch (error) {
      console.error('Failed to log paper trade:', error);
    }
  };

  // Auto-log paper trade when new signal appears and auto-trading is OFF
  useEffect(() => {
    if (bestSignal && !autoTradingActive) {
      // Create unique signal key with timestamp to avoid duplicates
      const signalKey = `${bestSignal.symbol}-${bestSignal.entry_price}-${bestSignal.action}-${Math.floor(Date.now() / 5000)}`;
      if (lastLoggedSignal !== signalKey) {
        logPaperTrade(bestSignal);
        setLastLoggedSignal(signalKey);
      }
    }
    // eslint-disable-next-line
  }, [bestSignal, autoTradingActive]);

  // When a trade closes, immediately try to log the next trade
  useEffect(() => {
    const handleTradeClosed = () => {
      console.log('Trade closed event received - attempting to log next trade');
      setHasActiveTrade(false);
      setLastLoggedSignal(null); // Reset to allow same signal to log again
      
      // If auto-trading is OFF and there's a signal, log it immediately
      if (bestSignal && !autoTradingActive) {
        setTimeout(() => {
          console.log('Logging next trade after closure:', bestSignal.symbol);
          logPaperTrade(bestSignal);
        }, 1000); // 1 second delay to ensure backend state is updated
      }
    };
    
    window.addEventListener('tradeClosedEvent', handleTradeClosed);
    return () => window.removeEventListener('tradeClosedEvent', handleTradeClosed);
  }, [bestSignal, autoTradingActive]);

  useEffect(() => {
    fetchData();
    analyzeMarket();

    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      fetchData();
      if (enabled) {
        analyzeMarket();
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [enabled]);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '400px'
      }}>
        <div style={{
          fontSize: '18px',
          color: '#718096'
        }}>
          Loading auto-trading dashboard...
        </div>
      </div>
    );
  }

  const todayLabel = new Date().toDateString();
  const todayIso = new Date().toISOString().slice(0, 10);
  const tradesToday = tradeHistory.filter((trade) => {
    const ts = trade.exit_time || trade.entry_time || trade.timestamp;
    if (!ts) return false;
    return new Date(ts).toDateString() === todayLabel;
  });
  const sumPnl = (trades) => trades.reduce((acc, t) => acc + Number(t.profit_loss ?? t.pnl ?? 0), 0);
  const sumWins = (trades) => trades.filter((t) => Number(t.profit_loss ?? t.pnl ?? 0) > 0).length;
  const overallPnl = reportSummary?.total_pnl ?? sumPnl(tradeHistory);
  const todayPnlFromSummary = reportSummary?.by_date?.find((d) => d.date === todayIso)?.pnl;
  const filteredHistory = tradeHistory.filter((t) => {
    const q = historySearch.trim().toLowerCase();
    if (!q) return true;
    return [t.symbol, t.index, t.action, t.status, t.strategy]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(q));
  });
  const todayTableRows = tradesToday;

  // --- Professional Signal Integration ---
  // ...existing code...

  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.95)',
      borderRadius: '16px',
      padding: '32px',
      marginBottom: '32px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
    }}>
      {/* Header with Toggle */}
      {renderOptionSignalsTable()}
      
      {/* Professional Signal Display */}
      {professionalSignal && !professionalSignal.error && (
        <div style={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: '16px',
          padding: '24px',
          marginBottom: '24px',
          color: 'white',
          boxShadow: '0 10px 40px rgba(102, 126, 234, 0.3)'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '20px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
            🎯 Professional Intraday Signal
            <span style={{
              fontSize: '12px',
              padding: '4px 10px',
              borderRadius: '12px',
              background: 'rgba(255,255,255,0.2)',
              fontWeight: '600'
            }}>
              LIVE
            </span>
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Symbol</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold' }}>{professionalSignal.symbol}</div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Action</div>
              <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                <span style={{
                  padding: '6px 16px',
                  borderRadius: '8px',
                  background: professionalSignal.signal === 'buy' ? '#48bb78' : professionalSignal.signal === 'sell' ? '#f56565' : '#cbd5e0',
                  color: 'white'
                }}>
                  {(professionalSignal.signal || 'HOLD').toUpperCase()}
                </span>
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Entry Price</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
                ₹{professionalSignal.entry_price ? professionalSignal.entry_price.toFixed(2) : 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Stop Loss</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#fed7d7' }}>
                ₹{professionalSignal.stop_loss ? professionalSignal.stop_loss.toFixed(2) : 'N/A'}
              </div>
            </div>
          </div>
        </div>
      )}
      
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '32px',
        paddingBottom: '20px',
        borderBottom: '2px solid #e2e8f0'
      }}>
        <div>
          <h3 style={{
            margin: '0 0 8px 0',
            color: '#2d3748',
            fontSize: '24px',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            🤖 Auto Trading Engine
            <span style={{
              fontSize: '14px',
              padding: '4px 12px',
              borderRadius: '20px',
              background: enabled ? '#48bb78' : '#cbd5e0',
              color: 'white',
              fontWeight: '600'
            }}>
              {enabled ? 'ACTIVE' : 'DISABLED'}
            </span>
            <span style={{
              fontSize: '14px',
              padding: '4px 12px',
              borderRadius: '20px',
              background: isDemoMode ? '#4299e1' : '#f56565',
              color: 'white',
              fontWeight: '600'
            }}>
              {'⚡ LIVE'}
            </span>
          </h3>
          <p style={{
            margin: 0,
            color: '#718096',
            fontSize: '14px'
          }}>
            {livePrice && <span>📊 NIFTY: ₹{livePrice.toFixed(2)} • </span>}
            {'⚡ LIVE Mode - Real Trades Execution'}
            {' • '}Max {stats?.max_trades || 10} Concurrent Trades
            {hasActiveTrade && <span style={{ color: '#f56565', fontWeight: '600' }}> • 🔒 ONE TRADE ACTIVE - Waiting to close...</span>}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            onClick={toggleMode}
            style={{
              padding: '10px 20px'
            }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Daily P&L</div>
            <div style={{
              fontSize: '28px',
              fontWeight: 'bold',
              color: (stats?.daily_pnl ?? 0) >= 0 ? '#c6f6d5' : '#fed7d7'
            }}>
                ₹{(stats?.daily_pnl ?? 0).toLocaleString()}
            </div>
          </button>
          <div style={{
            padding: '20px',
            background: 'linear-gradient(135deg, #ed8936 0%, #dd6b20 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Active Trades</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
              {(stats?.active_trades_count ?? 0)} / {(stats?.max_trades ?? 2)}
              {(stats?.active_trades_count ?? 0) >= (stats?.max_trades ?? 2) && (
                <span style={{ fontSize: '16px', background: '#fc8181', padding: '2px 8px', borderRadius: '4px' }}>FULL</span>
              )}
            </div>
          </div>
          <div style={{
            padding: '20px',
            background: 'linear-gradient(135deg, #9f7aea 0%, #805ad5 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Target / Trade</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold' }}>{stats?.target_points_per_trade ?? 25}pts</div>
          </div>

          {stats?.portfolio_cap !== null && stats?.portfolio_cap !== undefined && (
            <div style={{
              padding: '20px',
              background: 'linear-gradient(135deg, #319795 0%, #2c7a7b 100%)',
              borderRadius: '12px',
              color: 'white',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Capital In Use</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold' }}>₹{(stats?.capital_in_use ?? 0).toLocaleString()}</div>
              <div style={{ fontSize: '12px', opacity: 0.85, marginTop: '6px' }}>
                Remaining: ₹{(stats?.remaining_capital ?? 0).toLocaleString()} / Cap: ₹{(stats?.portfolio_cap ?? 0).toLocaleString()}
              </div>
            </div>
          )}
        </div>
    </div>

      {/* Market Analysis */}
      {bestSignal && (
        <div style={{
          padding: '24px',
          background: 'linear-gradient(135deg, #fef5e7 0%, #fdebd0 100%)',
          borderRadius: '12px',
          border: '2px solid #f59e0b',
          marginBottom: '24px'
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'start',
            marginBottom: '16px'
          }}>
            <div>
              <h4 style={{
                margin: '0 0 8px 0',
                color: '#78350f',
                fontSize: '18px',
                fontWeight: 'bold'
              }}>
                🎯 AI Recommendation (1 best signal)
              </h4>
              <div style={{
                display: 'flex',
                gap: '16px',
                fontSize: '14px',
                color: '#92400e',
                flexWrap: 'wrap'
              }}>
                <span>
                  <strong>Strategy:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: '#667eea',
                    color: 'white',
                    fontWeight: '600'
                  }}>
                    {bestSignal.strategy || 'Best Match'}
                  </span>
                </span>
                <span>
                  <strong>Action:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: bestSignal.action === 'BUY' ? '#48bb78' : '#f56565',
                    color: 'white',
                    fontWeight: 'bold'
                  }}>
                    {bestSignal.action}
                  </span>
                </span>
                <span><strong>Symbol:</strong> {bestSignal.symbol}</span>
                <span><strong>Confidence:</strong> {bestSignal.confidence}%</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong>Quantity:</strong>
                  <button
                    onClick={() => setLotMultiplier(Math.max(1, lotMultiplier - 1))}
                    style={{
                      padding: '2px 8px',
                      background: '#e2e8f0',
                      border: '1px solid #cbd5e0',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: 'bold'
                    }}
                  >
                    −
                  </button>
                  <span style={{
                    padding: '4px 12px',
                    background: '#edf2f7',
                    borderRadius: '6px',
                    fontWeight: 'bold',
                    minWidth: '80px',
                    textAlign: 'center'
                  }}>
                    {bestSignal.quantity * lotMultiplier}
                  </span>
                  <button
                    onClick={() => setLotMultiplier(lotMultiplier + 1)}
                    style={{
                      padding: '2px 8px',
                      background: '#e2e8f0',
                      border: '1px solid #cbd5e0',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: 'bold'
                    }}
                  >
                    +
                  </button>
                  <span style={{ fontSize: '12px', color: '#718096' }}>({lotMultiplier} lots)</span>
                </span>
                <span><strong>Expiry:</strong> {bestSignal.expiry_date || bestSignal.expiry}</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <button
                onClick={() => {
                  setAutoTradingActive(!autoTradingActive);
                  if (autoTradingActive) {
                    setHasActiveTrade(false);
                  }
                }}
                style={{
                  padding: '12px 24px',
                  background: autoTradingActive ? '#f56565' : '#48bb78',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '15px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
                }}
              >
                {autoTradingActive ? '🛑 Stop Auto-Trading' : '▶️ Start Auto-Trading'}
              </button>
              {autoTradingActive && (
                <div style={{
                  padding: '8px 16px',
                  background: hasActiveTrade ? '#fed7d7' : '#c6f6d5',
                  color: hasActiveTrade ? '#742a2a' : '#22543d',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '600'
                }}>
                  {hasActiveTrade ? '🔒 Trade Active (1/1)' : '✓ Ready to Trade'}
                </div>
              )}
            </div>
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '12px',
            padding: '16px',
            background: 'rgba(255, 255, 255, 0.5)',
            borderRadius: '8px'
          }}>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>
                🔴 Live Entry Price
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1a202c' }}>
                ₹{bestSignal.entry_price?.toFixed(2) ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>
                Target (+{bestSignal.target_points ?? 25}pts)
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#48bb78' }}>
                ₹{bestSignal.target?.toFixed(2) ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Stop Loss (-20pts)</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#f56565' }}>
                ₹{bestSignal.stop_loss?.toFixed(2) ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Potential Profit</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#38a169' }}>
                ₹{((bestSignal.target - bestSignal.entry_price) * bestSignal.quantity * lotMultiplier)?.toLocaleString() ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Max Risk</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#e53e3e' }}>
                ₹{((bestSignal.entry_price - bestSignal.stop_loss) * bestSignal.quantity * lotMultiplier)?.toLocaleString() ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Quantity</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#5a67d8' }}>
                {bestSignal.quantity * lotMultiplier}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Expiry Date</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#2d3748' }}>
                {bestSignal.expiry_date || 'N/A'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* All Signals Table */}
      {analysis?.signals?.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h4 style={{
            margin: '0 0 16px 0',
            color: '#2d3748',
            fontSize: '18px',
            fontWeight: 'bold'
          }}>
            📋 All Strategy Signals ({analysis.signals?.length ?? 0})
          </h4>
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
                  <th style={{ padding: '12px', textAlign: 'left' }}>Strategy</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Action</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Confidence</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Quantity</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Target</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Stop Loss</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Expiry</th>
                </tr>
              </thead>
              <tbody>
                {analysis.signals?.map((signal, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '12px', fontSize: '13px' }}>{signal.strategy}</td>
                    <td style={{ padding: '12px', fontWeight: '600', fontSize: '13px' }}>{signal.symbol}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        background: signal.action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                        color: signal.action === 'BUY' ? '#22543d' : '#742a2a',
                        fontSize: '12px',
                        fontWeight: 'bold'
                      }}>
                        {signal.action}
                      </span>
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600' }}>
                      {signal.confidence}%
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600', color: '#5a67d8' }}>
                      {signal.quantity}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>
                      ₹{signal.entry_price.toFixed(2)}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', color: '#48bb78', fontWeight: '600' }}>
                      ₹{signal.target.toFixed(2)}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', color: '#f56565', fontWeight: '600' }}>
                      ₹{signal.stop_loss.toFixed(2)}
                    </td>
                    <td style={{ padding: '12px', fontSize: '12px', color: '#718096' }}>
                      {signal.expiry_date || signal.expiry}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Active Trades */}

      {/* Trade History */}
      {tradeHistory.length > 0 && (
        <div>
          <h4 style={{
            margin: '0 0 16px 0',
            color: '#2d3748',
            fontSize: '18px',
            fontWeight: 'bold'
          }}>
            📊 Trade History (Last {tradeHistory.length})
          </h4>
          <div style={{ overflowX: 'auto', maxHeight: '400px', overflowY: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px'
            }}>
              <thead style={{ position: 'sticky', top: 0, background: '#f7fafc', zIndex: 1 }}>
                <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '10px', textAlign: 'left' }}>ID</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Action</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Exit</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>P&L</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>%</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Status</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Exit Time</th>
                </tr>
              </thead>
              <tbody>
                {tradeHistory.map((trade, idx) => {
                  const entry = Number(trade.entry_price || trade.price || 0);
                  const exit = trade.exit_price != null ? Number(trade.exit_price) : null;
                  const pnl = Number(trade.profit_loss ?? trade.pnl ?? 0);
                  const pnlPct = Number(trade.profit_percentage ?? trade.pnl_percent ?? 0);
                  const action = trade.action || trade.side || 'BUY';
                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                      <td style={{ padding: '10px' }}>#{trade.id}</td>
                      <td style={{ padding: '10px', fontWeight: '600' }}>{trade.symbol || trade.index || '—'}</td>
                      <td style={{ padding: '10px' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          background: action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                          color: action === 'BUY' ? '#22543d' : '#742a2a',
                          fontSize: '11px',
                          fontWeight: 'bold'
                        }}>
                          {action}
                        </span>
                      </td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>₹{entry.toFixed(2)}</td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>₹{exit !== null ? exit.toFixed(2) : '-'}</td>
                      <td style={{
                        padding: '10px',
                        textAlign: 'right',
                        fontWeight: '700',
                        color: pnl >= 0 ? '#48bb78' : '#f56565'
                      }}>
                        {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString()}
                      </td>
                      <td style={{
                        padding: '10px',
                        textAlign: 'right',
                        fontWeight: '600',
                        color: pnlPct >= 0 ? '#48bb78' : '#f56565'
                      }}>
                        {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                      </td>
                      <td style={{ padding: '10px' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          background: trade.status === 'CLOSED' ? '#bee3f8' : '#feebc8',
                          color: trade.status === 'CLOSED' ? '#2c5282' : '#7c2d12',
                          fontSize: '11px',
                          fontWeight: 'bold'
                        }}>
                          {trade.status || 'CLOSED'}
                        </span>
                      </td>
                      <td style={{ padding: '10px', fontSize: '11px', color: '#718096' }}>
                        {trade.exit_time ? new Date(trade.exit_time).toLocaleString() : '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty States - Show Analysis instead of empty message */}
      {activeTrades.length === 0 && tradeHistory.length === 0 && !analysis && (
        <div style={{
          padding: '60px 20px',
          textAlign: 'center',
          background: '#f7fafc',
          borderRadius: '12px',
          border: '2px dashed #cbd5e0'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
          <h4 style={{ margin: '0 0 8px 0', color: '#2d3748', fontSize: '18px' }}>
            No Trades Yet
          </h4>
          <p style={{ margin: 0, color: '#718096', fontSize: '14px', marginBottom: '16px' }}>
            Click "📊 Analyze" to see live market signals and expected profit/loss
          </p>
          <button
            onClick={analyzeMarket}
            style={{
              padding: '12px 32px',
              background: '#4299e1',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            📊 Analyze Market Now
          </button>
        </div>
      )}
      
      {/* Show Demo Trades if available */}
      {activeTrades.length === 0 && analysis && analysis.demo_trades && analysis.demo_trades.length > 0 && (
        <div style={{
          background: 'white',
          borderRadius: '12px',
          padding: '24px',
          marginBottom: '24px',
          border: '2px solid #4299e1'
        }}>
          <h4 style={{
            margin: '0 0 16px 0',
            color: '#2d3748',
            fontSize: '18px',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            🎯 Demo Trades - Expected Performance
            <span style={{
              fontSize: '12px',
              padding: '3px 10px',
              borderRadius: '12px',
              background: '#4299e1',
              color: 'white',
              fontWeight: '600'
            }}>
              SIMULATED
            </span>
          </h4>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Action</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Current</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Target</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Qty</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Current P&L</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Expected Profit</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Max Loss</th>
                </tr>
              </thead>
              <tbody>
                {analysis.demo_trades.map((trade, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '12px', fontWeight: '600' }}>{trade.symbol}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        background: trade.action === 'BUY' ? '#48bb78' : '#f56565',
                        color: 'white',
                        fontSize: '12px',
                        fontWeight: '600'
                      }}>
                        {trade.action}
                      </span>
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>₹{trade.entry_price}</td>
                    <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600' }}>₹{trade.current_price}</td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>₹{trade.target}</td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>{trade.quantity}</td>
                    <td style={{
                      padding: '12px',
                      textAlign: 'right',
                      fontWeight: 'bold',
                      color: trade.unrealized_pnl >= 0 ? '#48bb78' : '#f56565'
                    }}>
                      ₹{trade.unrealized_pnl.toLocaleString()} ({trade.pnl_percentage >= 0 ? '+' : ''}{trade.pnl_percentage}%)
                    </td>
                    <td style={{
                      padding: '12px',
                      textAlign: 'right',
                      fontWeight: 'bold',
                      color: '#48bb78'
                    }}>
                      +₹{trade.target_profit.toLocaleString()}
                    </td>
                    <td style={{
                      padding: '12px',
                      textAlign: 'right',
                      fontWeight: 'bold',
                      color: '#f56565'
                    }}>
                      -₹{trade.max_loss.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ background: '#f7fafc', borderTop: '2px solid #e2e8f0', fontWeight: 'bold' }}>
                  <td colSpan="6" style={{ padding: '12px' }}>TOTAL</td>
                  <td style={{
                    padding: '12px',
                    textAlign: 'right',
                    color: analysis.demo_trades.reduce((sum, t) => sum + t.unrealized_pnl, 0) >= 0 ? '#48bb78' : '#f56565',
                    fontSize: '16px'
                  }}>
                    ₹{analysis.demo_trades.reduce((sum, t) => sum + t.unrealized_pnl, 0).toLocaleString()}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'right', color: '#48bb78', fontSize: '16px' }}>
                    +₹{analysis.demo_trades.reduce((sum, t) => sum + t.target_profit, 0).toLocaleString()}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'right', color: '#f56565', fontSize: '16px' }}>
                    -₹{analysis.demo_trades.reduce((sum, t) => sum + t.max_loss, 0).toLocaleString()}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p style={{ margin: '16px 0 0 0', fontSize: '13px', color: '#718096', fontStyle: 'italic' }}>
            💡 These are simulated trades using real market data. Enable auto-trading to execute real trades (in selected mode).
          </p>
        </div>
      )}

      {activeTab === 'report' && (
        <div style={{
          background: 'white',
          borderRadius: '12px',
          padding: '20px',
          border: '1px solid #e2e8f0'
        }}>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
            <div style={{ padding: '16px', background: '#1a202c', color: 'white', borderRadius: '10px', minWidth: '180px' }}>
              <div style={{ fontSize: '12px', opacity: 0.8 }}>Today P&L</div>
              <div style={{ fontSize: '26px', fontWeight: '700', color: (todayPnlFromSummary ?? sumPnl(tradesToday)) >= 0 ? '#c6f6d5' : '#fed7d7' }}>
                ₹{(todayPnlFromSummary ?? sumPnl(tradesToday)).toLocaleString()}
              </div>
            </div>
            <div style={{ padding: '16px', background: '#2b6cb0', color: 'white', borderRadius: '10px', minWidth: '180px' }}>
              <div style={{ fontSize: '12px', opacity: 0.9 }}>Today Trades</div>
              <div style={{ fontSize: '26px', fontWeight: '700' }}>{tradesToday.length}</div>
            </div>
            <div style={{ padding: '16px', background: '#2f855a', color: 'white', borderRadius: '10px', minWidth: '180px' }}>
              <div style={{ fontSize: '12px', opacity: 0.9 }}>Today Win / Loss</div>
              <div style={{ fontSize: '16px', fontWeight: '700' }}>{sumWins(tradesToday)} / {tradesToday.length - sumWins(tradesToday)}</div>
            </div>
            <div style={{ padding: '16px', background: '#4a5568', color: 'white', borderRadius: '10px', minWidth: '180px' }}>
              <div style={{ fontSize: '12px', opacity: 0.9 }}>Overall P&L</div>
              <div style={{ fontSize: '26px', fontWeight: '700', color: overallPnl >= 0 ? '#c6f6d5' : '#fed7d7' }}>
                ₹{overallPnl.toLocaleString()}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4 style={{ margin: 0, color: '#2d3748' }}>Trade Report (search & history)</h4>
            <input
              type="text"
              placeholder="Search symbol / action / status"
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
              style={{
                padding: '10px 12px',
                borderRadius: '8px',
                border: '1px solid #cbd5e0',
                minWidth: '240px'
              }}
            />
          </div>

          <div style={{ marginBottom: '12px' }}>
            <h5 style={{ margin: '0 0 8px 0', color: '#2d3748' }}>Today Trades</h5>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <tr>
                    <th style={{ padding: '8px', textAlign: 'left' }}>ID</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Symbol</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Action</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>Entry</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>Exit</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>P&L</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {todayTableRows.map((t, idx) => {
                    const entry = Number(t.entry_price || t.price || 0);
                    const exit = t.exit_price != null ? Number(t.exit_price) : null;
                    const pnl = Number(t.pnl ?? t.profit_loss ?? 0);
                    const action = t.action || t.side || 'BUY';
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                        <td style={{ padding: '8px' }}>{t.id}</td>
                        <td style={{ padding: '8px', fontWeight: '600' }}>{t.symbol || t.index || '—'}</td>
                        <td style={{ padding: '8px' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '3px',
                            background: action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                            color: action === 'BUY' ? '#22543d' : '#742a2a',
                            fontSize: '11px',
                            fontWeight: 'bold'
                          }}>
                            {action}
                          </span>
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>₹{entry.toFixed(2)}</td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>₹{exit !== null ? exit.toFixed(2) : '-'}</td>
                        <td style={{ padding: '8px', textAlign: 'right', fontWeight: '700', color: pnl >= 0 ? '#48bb78' : '#f56565' }}>
                          {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString()}
                        </td>
                        <td style={{ padding: '8px', fontSize: '11px', color: '#718096' }}>{t.status || 'CLOSED'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {tradesToday.length === 0 && (
              <div style={{ marginTop: '8px', fontSize: '12px', color: '#718096' }}>
                Showing sample rows. Real trades will appear here once captured today.
              </div>
            )}
          </div>

          {filteredHistory.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: '#718096', border: '1px dashed #e2e8f0', borderRadius: '10px' }}>
              No trades found for the current filters.
            </div>
          ) : (
            <div style={{ overflowX: 'auto', maxHeight: '480px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead style={{ position: 'sticky', top: 0, background: '#f7fafc', zIndex: 1 }}>
                  <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                    <th style={{ padding: '10px', textAlign: 'left' }}>ID</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>Symbol</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>Action</th>
                    <th style={{ padding: '10px', textAlign: 'right' }}>Entry</th>
                    <th style={{ padding: '10px', textAlign: 'right' }}>Exit</th>
                    <th style={{ padding: '10px', textAlign: 'right' }}>P&L</th>
                    <th style={{ padding: '10px', textAlign: 'right' }}>%</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>Status</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.map((trade, idx) => {
                    const entry = Number(trade.entry_price || trade.price || 0);
                    const exit = trade.exit_price != null ? Number(trade.exit_price) : null;
                    const pnl = Number(trade.profit_loss ?? trade.pnl ?? 0);
                    const pnlPct = Number(trade.profit_percentage ?? trade.pnl_percent ?? 0);
                    const action = trade.action || trade.side || 'BUY';
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                        <td style={{ padding: '10px' }}>#{trade.id}</td>
                        <td style={{ padding: '10px', fontWeight: '600' }}>{trade.symbol || trade.index || '—'}</td>
                        <td style={{ padding: '10px' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '3px',
                            background: action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                            color: action === 'BUY' ? '#22543d' : '#742a2a',
                            fontSize: '11px',
                            fontWeight: 'bold'
                          }}>
                            {action}
                          </span>
                        </td>
                        <td style={{ padding: '10px', textAlign: 'right' }}>₹{entry.toFixed(2)}</td>
                        <td style={{ padding: '10px', textAlign: 'right' }}>₹{exit !== null ? exit.toFixed(2) : '-'}</td>
                        <td style={{
                          padding: '10px',
                          textAlign: 'right',
                          fontWeight: '700',
                          color: pnl >= 0 ? '#48bb78' : '#f56565'
                        }}>
                          {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString()}
                        </td>
                        <td style={{
                          padding: '10px',
                          textAlign: 'right',
                          fontWeight: '600',
                          color: pnlPct >= 0 ? '#48bb78' : '#f56565'
                        }}>
                          {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                        </td>
                        <td style={{ padding: '10px' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '3px',
                            background: trade.status === 'CLOSED' ? '#bee3f8' : '#feebc8',
                            color: trade.status === 'CLOSED' ? '#2c5282' : '#7c2d12',
                            fontSize: '11px',
                            fontWeight: 'bold'
                          }}>
                            {trade.status || 'CLOSED'}
                          </span>
                        </td>
                        <td style={{ padding: '10px', fontSize: '11px', color: '#718096' }}>
                          {trade.exit_time ? new Date(trade.exit_time).toLocaleDateString() : (trade.entry_time ? new Date(trade.entry_time).toLocaleDateString() : '-')}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      
      {/* Paper Trading Performance Section */}
      <div style={{ marginTop: '32px', marginBottom: '16px' }}>
        <button
          onClick={() => setShowPaperTrading(!showPaperTrading)}
          style={{
            width: '100%',
            padding: '16px',
            background: showPaperTrading ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'linear-gradient(135deg, #4299e1 0%, #3182ce 100%)',
            color: 'white',
            border: 'none',
            borderRadius: '12px',
            fontSize: '16px',
            fontWeight: 'bold',
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <span>📊 {showPaperTrading ? 'Hide' : 'Show'} Paper Trading Performance</span>
          <span style={{ fontSize: '20px' }}>{showPaperTrading ? '▼' : '▶'}</span>
        </button>
      </div>
      
      {showPaperTrading && <PaperTradingDashboard />}
    </div>
  );
}

export default AutoTradingDashboard;
