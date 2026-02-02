import React, { useState, useEffect } from 'react';

// Use environment-based API URL if available
import config from '../config/api';
const OPTION_SIGNALS_API = `${config.API_BASE_URL}/option-signals/intraday-advanced`;
const PROFESSIONAL_SIGNAL_API = `${config.API_BASE_URL}/strategies/live/professional-signal`;
const PAPER_TRADES_ACTIVE_API = `${config.API_BASE_URL}/paper-trades/active`;
const PAPER_TRADES_HISTORY_API = `${config.API_BASE_URL}/paper-trades/history`;
const PAPER_TRADES_PERFORMANCE_API = `${config.API_BASE_URL}/paper-trades/performance`;
const PAPER_TRADES_UPDATE_API = `${config.API_BASE_URL}/paper-trades/update-prices`;
const PAPER_TRADES_CREATE_API = `${config.API_BASE_URL}/paper-trades`;

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
  const [lastPaperSignalSymbol, setLastPaperSignalSymbol] = useState(null);
  const [confirmationMode, setConfirmationMode] = useState('balanced');
  const [selectedSignalSymbol, setSelectedSignalSymbol] = useState(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('selectedSignalSymbol');
  });
  const [signalsLoaded, setSignalsLoaded] = useState(false);

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
    try {
      // Update paper trade prices with LIVE data
      await config.authFetch(PAPER_TRADES_UPDATE_API, { method: 'POST' });

      const [activeRes, historyRes, perfRes] = await Promise.all([
        config.authFetch(PAPER_TRADES_ACTIVE_API),
        config.authFetch(`${PAPER_TRADES_HISTORY_API}?days=7&limit=100`),
        config.authFetch(`${PAPER_TRADES_PERFORMANCE_API}?days=30`),
      ]);

      const activeData = activeRes.ok ? await activeRes.json() : { trades: [] };
      const historyData = historyRes.ok ? await historyRes.json() : { trades: [] };
      const perfData = perfRes.ok ? await perfRes.json() : null;

      const active = activeData.trades || [];
      const history = historyData.trades || [];

      setActiveTrades(active);
      setTradeHistory(history);
      setReportSummary(perfData);
      setHasActiveTrade(active.length > 0);

      // Compute daily P&L from closed trades
      const todayLabel = new Date().toDateString();
      const dailyPnl = history
        .filter((t) => {
          const ts = t.exit_time || t.entry_time;
          if (!ts) return false;
          return new Date(ts).toDateString() === todayLabel;
        })
        .reduce((acc, t) => acc + Number(t.pnl ?? t.profit_loss ?? 0), 0);

      const capitalInUse = active.reduce((acc, t) => acc + Number(t.entry_price ?? 0) * Number(t.quantity ?? 0), 0);

      const targetPoints = Number(activeSignal?.target_points ?? 0) || (activeSignal && activeSignal.entry_price && activeSignal.target
        ? Math.max(0, Number(activeSignal.target) - Number(activeSignal.entry_price))
        : 25);

      setStats({
        daily_pnl: dailyPnl,
        active_trades_count: active.length,
        max_trades: 2,
        target_points_per_trade: Math.round(targetPoints),
        capital_in_use: capitalInUse,
        remaining_capital: null,
        portfolio_cap: null,
      });
    } catch (e) {
      setActiveTrades([]);
      setTradeHistory([]);
      setReportSummary(null);
    } finally {
      setLoading(false);
    }
  };

  // Remove legacy analyzeMarket logic (config references)
  const analyzeMarket = async () => {
    if (!activeSignal) return;

    // In demo mode, log paper trade and show live P&L
    if (!autoTradingActive) {
      await createPaperTradeFromSignal(activeSignal);
      await fetchData();
    }
  };

  // Remove toggleMode, always live
  const toggleMode = () => {};

  // Fetch option signals from backend
  useEffect(() => {
    const fetchOptionSignals = async () => {
      try {
        const res = await fetch(`${OPTION_SIGNALS_API}?mode=${encodeURIComponent(confirmationMode)}`);
        const data = await res.json();
        setOptionSignals(data.signals || []);
      } catch (e) {
        setOptionSignals([]);
      } finally {
        setSignalsLoaded(true);
      }
    };
    fetchOptionSignals();
  }, [confirmationMode]);

  // Group signals by index to show CE and PE side-by-side
  const groupedSignals = optionSignals.reduce((acc, signal) => {
    // Filter out fake/invalid signals
    if (signal.error) return acc;
    if (!signal.symbol || !signal.index || !signal.strike) return acc;
    if (!signal.entry_price || signal.entry_price <= 0) return acc;
    if (!signal.target || signal.target <= 0) return acc;
    if (!signal.stop_loss || signal.stop_loss <= 0) return acc;
    if (!signal.confirmation_score && !signal.confidence) return acc;
    
    const key = signal.index;
    if (!acc[key]) {
      acc[key] = { ce: null, pe: null, strike: signal.strike, expiry: signal.expiry_date || signal.expiry_zone };
    }
    if (signal.option_type === 'CE') {
      acc[key].ce = signal;
    } else if (signal.option_type === 'PE') {
      acc[key].pe = signal;
    }
    return acc;
  }, {});

  // Get selected signal from grouped signals
  const selectedSignal = selectedSignalSymbol
    ? optionSignals.find((s) => s.symbol === selectedSignalSymbol)
    : null;

  // Pick the best signal (highest confidence) from valid optionSignals only
  const bestSignal = optionSignals.reduce((best, curr) => {
    // Skip invalid signals
    if (curr.error || !curr.symbol || !curr.entry_price || curr.entry_price <= 0) return best;
    if (!curr.confirmation_score && !curr.confidence) return best;
    
    return (!best || ((curr.confirmation_score ?? curr.confidence) > (best.confirmation_score ?? best.confidence))) ? curr : best;
  }, null);

  const activeSignal = selectedSignal || bestSignal;

  // Render option signals table - Side by side CE and PE
  const renderOptionSignalsTable = () => (
    <div style={{ margin: '32px 0' }}>
      <h3>📊 Intraday Option Signals (CE vs PE)</h3>
      {Object.keys(groupedSignals).length === 0 && signalsLoaded && (
        <div style={{ padding: '20px', background: '#fff3cd', border: '1px solid #ffc107', borderRadius: '4px', marginBottom: '16px' }}>
          <strong>⚠️ No signals available</strong> - API may not have returned any data or all signals have errors.
        </div>
      )}
      {!signalsLoaded && (
        <div style={{ padding: '20px', background: '#d1ecf1', border: '1px solid #17a2b8', borderRadius: '4px', marginBottom: '16px' }}>
          <strong>Loading signals...</strong>
        </div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', background: 'white', borderRadius: '8px', overflow: 'hidden' }}>
        <thead>
          <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center' }}>Index</th>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center', color: '#2d8a3f', fontWeight: '700' }}>📈 CALL (CE) - BUY</th>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center', color: '#c92a2a', fontWeight: '700' }}>📉 PUT (PE) - BUY</th>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center' }}>Strike</th>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center' }}>Expiry</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(groupedSignals).map(([index, data]) => (
            <tr key={index} style={{ borderBottom: '1px solid #e2e8f0' }}>
              <td style={{ padding: '12px', border: '1px solid #e2e8f0', fontWeight: '700', textAlign: 'center', color: '#2b6cb0' }}>{index}</td>
              
              {/* CALL (CE) Signal */}
              <td style={{ padding: '10px', border: '1px solid #e2e8f0', textAlign: 'center', background: selectedSignalSymbol === data.ce?.symbol ? '#eff6ff' : 'white' }}>
                {data.ce ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name="signal_selection"
                        checked={selectedSignalSymbol === data.ce.symbol}
                        onChange={() => {
                          setSelectedSignalSymbol(data.ce.symbol);
                          localStorage.setItem('selectedSignalSymbol', data.ce.symbol);
                        }}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                      <span style={{ color: '#2d8a3f', fontWeight: 'bold', fontSize: '12px' }}>SELECT</span>
                    </label>
                    <div style={{ fontSize: '12px', lineHeight: '1.4' }}>
                      <div><strong>Entry:</strong> ₹{(data.ce.entry_price ?? 0).toFixed(2)}</div>
                      <div><strong>Target:</strong> <span style={{ color: '#48bb78', fontWeight: 'bold' }}>₹{(data.ce.target ?? 0).toFixed(2)}</span></div>
                      <div><strong>SL:</strong> <span style={{ color: '#f56565' }}>₹{(data.ce.stop_loss ?? 0).toFixed(2)}</span></div>
                      <div style={{ marginTop: '4px', padding: '4px', borderRadius: '3px', background: Number(data.ce.confirmation_score ?? data.ce.confidence ?? 0) >= 85 ? '#c6f6d5' : Number(data.ce.confirmation_score ?? data.ce.confidence ?? 0) >= 75 ? '#feebc8' : '#fed7d7', color: Number(data.ce.confirmation_score ?? data.ce.confidence ?? 0) >= 85 ? '#22543d' : Number(data.ce.confirmation_score ?? data.ce.confidence ?? 0) >= 75 ? '#92400e' : '#742a2a', fontWeight: 'bold' }}>
                        Conf: {(data.ce.confirmation_score ?? data.ce.confidence ?? 0).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ) : (
                  <span style={{ color: '#cbd5e0' }}>No Signal</span>
                )}
              </td>
              
              {/* PUT (PE) Signal */}
              <td style={{ padding: '10px', border: '1px solid #e2e8f0', textAlign: 'center', background: selectedSignalSymbol === data.pe?.symbol ? '#eff6ff' : 'white' }}>
                {data.pe ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name="signal_selection"
                        checked={selectedSignalSymbol === data.pe.symbol}
                        onChange={() => {
                          setSelectedSignalSymbol(data.pe.symbol);
                          localStorage.setItem('selectedSignalSymbol', data.pe.symbol);
                        }}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                      <span style={{ color: '#c92a2a', fontWeight: 'bold', fontSize: '12px' }}>SELECT</span>
                    </label>
                    <div style={{ fontSize: '12px', lineHeight: '1.4' }}>
                      <div><strong>Entry:</strong> ₹{(data.pe.entry_price ?? 0).toFixed(2)}</div>
                      <div><strong>Target:</strong> <span style={{ color: '#48bb78', fontWeight: 'bold' }}>₹{(data.pe.target ?? 0).toFixed(2)}</span></div>
                      <div><strong>SL:</strong> <span style={{ color: '#f56565' }}>₹{(data.pe.stop_loss ?? 0).toFixed(2)}</span></div>
                      <div style={{ marginTop: '4px', padding: '4px', borderRadius: '3px', background: Number(data.pe.confirmation_score ?? data.pe.confidence ?? 0) >= 85 ? '#c6f6d5' : Number(data.pe.confirmation_score ?? data.pe.confidence ?? 0) >= 75 ? '#feebc8' : '#fed7d7', color: Number(data.pe.confirmation_score ?? data.pe.confidence ?? 0) >= 85 ? '#22543d' : Number(data.pe.confirmation_score ?? data.pe.confidence ?? 0) >= 75 ? '#92400e' : '#742a2a', fontWeight: 'bold' }}>
                        Conf: {(data.pe.confirmation_score ?? data.pe.confidence ?? 0).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ) : (
                  <span style={{ color: '#cbd5e0' }}>No Signal</span>
                )}
              </td>
              
              <td style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center', fontWeight: '600' }}>{data.strike}</td>
              <td style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center', fontSize: '12px', color: '#666' }}>{data.expiry}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  useEffect(() => {
    if (signalsLoaded && selectedSignalSymbol && !selectedSignal) {
      setSelectedSignalSymbol(null);
      localStorage.removeItem('selectedSignalSymbol');
    }
    // eslint-disable-next-line
  }, [signalsLoaded, optionSignals, selectedSignalSymbol]);

  useEffect(() => {
    if (selectedSignalSymbol) {
      localStorage.setItem('selectedSignalSymbol', selectedSignalSymbol);
    } else {
      localStorage.removeItem('selectedSignalSymbol');
    }
  }, [selectedSignalSymbol]);

  // Auto-execute the selected/best signal if available and auto-trading is active
  useEffect(() => {
    if (activeSignal && !executing && autoTradingActive && !hasActiveTrade) {
      executeAutoTrade(activeSignal);
    }
    // eslint-disable-next-line
  }, [activeSignal, autoTradingActive, hasActiveTrade]);

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

  const createPaperTradeFromSignal = async (signal) => {
    if (!signal || !signal.symbol) return;
    if (autoTradingActive) return;
    if (activeTrades.length > 0) return;
    if (lastPaperSignalSymbol === signal.symbol) return;

    const payload = {
      symbol: signal.symbol,
      index_name: signal.index,
      side: signal.action,
      signal_type: 'intraday_option',
      quantity: (signal.quantity || 1) * lotMultiplier,
      entry_price: signal.entry_price,
      stop_loss: signal.stop_loss,
      target: signal.target,
      strategy: signal.strategy || 'ATM Option',
      signal_data: signal,
    };

    try {
      const res = await config.authFetch(PAPER_TRADES_CREATE_API, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        if (data?.success !== false) {
          setLastPaperSignalSymbol(signal.symbol);
        }
      }
    } catch (e) {
      // ignore paper trade creation errors in demo mode
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

  useEffect(() => {
    fetchData();
    analyzeMarket();

    // Auto-refresh every 1 second for live updates
    const interval = setInterval(() => {
      fetchData();
      if (enabled) {
        analyzeMarket();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [enabled]);

  useEffect(() => {
    if (activeSignal?.entry_price) {
      setLivePrice(activeSignal.entry_price);
    }
  }, [activeSignal]);

  useEffect(() => {
    if (!autoTradingActive && activeSignal && signalsLoaded) {
      createPaperTradeFromSignal(activeSignal);
    }
  }, [autoTradingActive, activeSignal, signalsLoaded, activeTrades.length, lotMultiplier]);

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
            background: 'linear-gradient(135deg, #939BA3 0%, #7a8289 100%)',
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
      {activeSignal && (
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
                {selectedSignal ? `🎯 Selected Signal ${activeSignal.option_type === 'CE' ? '📈 (CALL)' : '📉 (PUT)'}` : '🎯 AI Recommendation (best signal)'}
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
                        {activeSignal.strategy || 'Best Match'}
                  </span>
                </span>
                <span>
                  <strong>Action:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: activeSignal.action === 'BUY' ? '#48bb78' : '#f56565',
                    color: 'white',
                    fontWeight: 'bold'
                  }}>
                    {activeSignal.action}
                  </span>
                </span>
                <span><strong>Symbol:</strong> {activeSignal.symbol}</span>
                <span>
                  <strong>Confidence:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: Number(activeSignal.confirmation_score ?? activeSignal.confidence) >= 85 ? '#c6f6d5' : Number(activeSignal.confirmation_score ?? activeSignal.confidence) >= 75 ? '#feebc8' : '#fed7d7',
                    color: Number(activeSignal.confirmation_score ?? activeSignal.confidence) >= 85 ? '#22543d' : Number(activeSignal.confirmation_score ?? activeSignal.confidence) >= 75 ? '#92400e' : '#742a2a',
                    fontWeight: '600'
                  }}>
                    {(activeSignal.confirmation_score ?? activeSignal.confidence ?? 0).toFixed(1)}%
                  </span>
                </span>
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
                    {activeSignal.quantity * lotMultiplier}
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
                <span><strong>Expiry:</strong> {activeSignal.expiry_date || activeSignal.expiry}</span>
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
                ₹{activeSignal.entry_price?.toFixed(2) ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>
                Target (+{activeSignal.target_points ?? 25}pts)
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#48bb78' }}>
                ₹{activeSignal.target?.toFixed(2) ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Stop Loss (-20pts)</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#f56565' }}>
                ₹{activeSignal.stop_loss?.toFixed(2) ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Potential Profit</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#38a169' }}>
                ₹{((activeSignal.target - activeSignal.entry_price) * activeSignal.quantity * lotMultiplier)?.toLocaleString() ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Max Risk</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#e53e3e' }}>
                ₹{((activeSignal.entry_price - activeSignal.stop_loss) * activeSignal.quantity * lotMultiplier)?.toLocaleString() ?? '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Quantity</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#5a67d8' }}>
                {activeSignal.quantity * lotMultiplier}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Expiry Date</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#2d3748' }}>
                {activeSignal.expiry_date || 'N/A'}
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
      {activeTrades.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h4 style={{
            margin: '0 0 16px 0',
            color: '#2d3748',
            fontSize: '18px',
            fontWeight: 'bold'
          }}>
            ⚡ Active Trades (LIVE P&L)
          </h4>
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px',
              background: 'white',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <thead>
                <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Action</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Current</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>P&L</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>%</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Qty</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Opened</th>
                </tr>
              </thead>
              <tbody>
                {activeTrades.map((trade) => {
                  const entry = Number(trade.entry_price || 0);
                  const current = Number(trade.current_price ?? entry);
                  const pnl = Number(trade.pnl ?? 0);
                  const pnlPct = Number(trade.pnl_percentage ?? 0);
                  const action = trade.side || 'BUY';
                  return (
                    <tr key={trade.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                      <td style={{ padding: '10px', fontWeight: '600' }}>{trade.symbol}</td>
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
                      <td style={{ padding: '10px', textAlign: 'right' }}>₹{current.toFixed(2)}</td>
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
                      <td style={{ padding: '10px', textAlign: 'right' }}>{trade.quantity}</td>
                      <td style={{ padding: '10px', fontSize: '11px', color: '#718096' }}>
                        {trade.entry_time ? new Date(trade.entry_time).toLocaleString() : '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
      
    </div>
  );
}

export default AutoTradingDashboard;
