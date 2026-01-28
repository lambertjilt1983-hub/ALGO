import React, { useState, useEffect } from 'react';
import config from '../config/api';

const AutoTradingDashboard = () => {
  const [enabled, setEnabled] = useState(false);
  const [isDemoMode, setIsDemoMode] = useState(true);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [activeTrades, setActiveTrades] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [reportSummary, setReportSummary] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [livePrice, setLivePrice] = useState(null);
  const [activeTab, setActiveTab] = useState('trading');
  const [historySearch, setHistorySearch] = useState('');

  const fetchData = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      const [statusRes, activeRes, reportRes] = await Promise.all([
        config.authFetch(config.endpoints.autoTrade.status),
        config.authFetch(config.endpoints.autoTrade.activeTrades),
        config.authFetch(config.getUrl(config.endpoints.autoTrade.report, { limit: 500 }))
      ]);

      let statusPayload = null;
      if (statusRes.ok) {
        const data = await statusRes.json();
        statusPayload = data.status || data;
        setEnabled(true); // backend always enabled
        setIsDemoMode(statusPayload.is_demo_mode !== false);
      }

      let active = [];
      if (activeRes.ok) {
        const data = await activeRes.json();
        const trades = data.trades || data;
        active = trades;
        if (data.is_demo_mode && analysis && analysis.demo_trades) {
          active = analysis.demo_trades;
        }
        setActiveTrades(active);
      }

      let historyData = [];
      if (reportRes.ok) {
        const data = await reportRes.json();
        historyData = data.trades || [];
        setTradeHistory(historyData);
        setReportSummary(data.summary || null);
      }

      const totalTrades = historyData.length;
      const winSample = statusPayload?.win_sample || 0;
      const winRate = statusPayload?.win_rate || 0;
      const targetPts = analysis?.recommendation?.target_points || statusPayload?.target_points_per_trade || 25;
      const remainingCap = statusPayload?.remaining_capital ?? statusPayload?.portfolio_cap ?? 0;
      const capitalInUse = statusPayload?.capital_in_use ?? 0;
      const portfolioCap = statusPayload?.portfolio_cap ?? null;
      const mappedStats = {
        enabled: true,
        is_demo_mode: statusPayload?.is_demo_mode !== false,
        active_trades_count: statusPayload?.active_trades_count ?? active.length,
        max_trades: statusPayload?.max_trades || 6,
        win_rate: winRate,
        win_sample: winSample,
        daily_pnl: statusPayload?.daily_pnl || 0,
        total_trades: totalTrades,
        target_points_per_trade: targetPts,
        capital_in_use: capitalInUse,
        remaining_capital: remainingCap,
        portfolio_cap: portfolioCap,
      };
      setStats(mappedStats);

      setLoading(false);
    } catch (error) {
      console.error('Error fetching auto-trade data:', error);
      setLoading(false);
    }
  };

  const analyzeMarket = async () => {
    try {
      const response = await config.authFetch(
        config.getUrl(config.endpoints.autoTrade.analyze, { symbol: 'NIFTY', balance: 100000 }),
        { method: 'POST' }
      );

      if (response.ok) {
        const data = await response.json();
        setAnalysis(data);
        if (data.live_price) {
          setLivePrice(data.live_price);
        }
      }
    } catch (error) {
      console.error('Error analyzing market:', error);
    }
  };

  const toggleMode = async () => {
    const newMode = !isDemoMode;
    
    if (!newMode) {
      const confirmed = window.confirm(
        '⚠️ WARNING: Switching to LIVE mode will execute REAL trades with real money!\n\n' +
        'Are you sure you want to continue?'
      );
      
      if (!confirmed) return;
    }
    
    try {
      const response = await config.authFetch(
        config.getUrl(config.endpoints.autoTrade.setMode, { demo_mode: newMode }),
        { method: 'POST' }
      );

      if (response.ok) {
        const data = await response.json();
        setIsDemoMode(newMode);
        alert(data.message);
      }
    } catch (error) {
      console.error('Error toggling mode:', error);
      alert('Failed to switch mode');
    }
  };

  const toggleAutoTrading = async () => {
    try {
      const response = await config.authFetch(
        config.getUrl(config.endpoints.autoTrade.toggle, { enabled: !enabled }),
        { method: 'POST' }
      );

      if (response.ok) {
        const data = await response.json();
        setEnabled(data.enabled);
        alert(data.message);
      }
    } catch (error) {
      console.error('Error toggling auto-trading:', error);
      alert('Failed to toggle auto-trading');
    }
  };

  const executeAutoTrade = async () => {
    const rec = analysis?.recommendation;
    if (!rec) {
      alert('Run Analyze first so we have a recommendation with prices.');
      return;
    }

    const entryPrice = Number(rec.entry_price ?? livePrice ?? rec.underlying_price ?? 0);
    if (!entryPrice || Number.isNaN(entryPrice)) {
      alert('Missing entry price from analysis; cannot execute.');
      return;
    }

    const tradeParams = {
      symbol: rec.symbol || 'NIFTY',
      price: entryPrice,
      target: rec.target ?? undefined,
      stop_loss: rec.stop_loss ?? undefined,
      support: rec.support ?? undefined,
      resistance: rec.resistance ?? undefined,
      quantity: rec.quantity ?? 1,
      side: rec.action || rec.side || 'BUY',
      balance: stats?.portfolio_cap ?? 50000,
      broker_id: 1,
    };

    const sanitizedParams = Object.fromEntries(
      Object.entries(tradeParams).filter(([, value]) => value !== undefined && value !== null && value !== '')
    );

    if (!isDemoMode) {
      const confirmed = window.confirm(
        '⚠️ LIVE TRADING ALERT!\n\n' +
        'This will execute a REAL trade with real money.\n\n' +
        'Continue?'
      );
      
      if (!confirmed) return;
    }
    
    setExecuting(true);
    
    try {
      const response = await config.authFetch(
        config.getUrl(config.endpoints.autoTrade.execute, sanitizedParams),
        { method: 'POST' }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          const prefix = isDemoMode ? '🎯 DEMO' : '⚡ LIVE';
          alert(`${prefix}: ${data.message}`);
          fetchData();
        } else {
          alert(data.message);
        }
      }
    } catch (error) {
      console.error('Error executing trade:', error);
      alert('Failed to execute trade');
    } finally {
      setExecuting(false);
    }
  };

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

  const sampleTodayTrades = [
    {
      id: 'SAMPLE-1',
      symbol: 'NIFTY 27FEB 22500 CE',
      action: 'BUY',
      entry_price: 112.5,
      exit_price: 114.8,
      pnl: 2.3,
      pnl_percentage: 2.04,
      status: 'CLOSED',
      entry_time: todayIso,
      exit_time: todayIso,
      quantity: 50,
    },
    {
      id: 'SAMPLE-2',
      symbol: 'BANKNIFTY 27FEB 48500 PE',
      action: 'SELL',
      entry_price: 152.0,
      exit_price: 149.5,
      pnl: 2.5,
      pnl_percentage: 1.64,
      status: 'CLOSED',
      entry_time: todayIso,
      exit_time: todayIso,
      quantity: 15,
    },
  ];

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
  const todayTableRows = tradesToday.length > 0 ? tradesToday : sampleTodayTrades;

  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.95)',
      borderRadius: '16px',
      padding: '32px',
      marginBottom: '32px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
    }}>
      {/* Header with Toggle */}
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
              {isDemoMode ? '🎯 DEMO' : '⚡ LIVE'}
            </span>
          </h3>
          <p style={{
            margin: 0,
            color: '#718096',
            fontSize: '14px'
          }}>
            {livePrice && <span>📊 NIFTY: ₹{livePrice.toFixed(2)} • </span>}
            {isDemoMode ? '🎯 Demo Mode - Using Real Market Data • No Real Trades' : '⚡ LIVE Mode - Real Trades Execution'}
            {' • '}Max {stats?.max_trades || 10} Concurrent Trades
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            onClick={toggleMode}
            style={{
              padding: '10px 20px',
              background: isDemoMode ? '#f56565' : '#48bb78',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            {isDemoMode ? '⚡ Switch to LIVE' : '🎯 Switch to DEMO'}
          </button>
          <button
            onClick={analyzeMarket}
            style={{
              padding: '10px 20px',
              background: '#4299e1',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            📊 Analyze
          </button>
          <button
            onClick={toggleAutoTrading}
            style={{
              padding: '12px 24px',
              background: enabled ? '#f56565' : '#48bb78',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: '600',
              cursor: 'pointer',
              minWidth: '140px'
            }}
          >
            {enabled ? '⏸ Disable' : '▶ Enable'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
        <button
          onClick={() => setActiveTab('trading')}
          style={{
            padding: '10px 16px',
            borderRadius: '10px',
            border: 'none',
            fontWeight: '700',
            background: activeTab === 'trading' ? '#2b6cb0' : '#e2e8f0',
            color: activeTab === 'trading' ? 'white' : '#2d3748',
            cursor: 'pointer'
          }}
        >
          🚀 Trading
        </button>
        <button
          onClick={() => setActiveTab('report')}
          style={{
            padding: '10px 16px',
            borderRadius: '10px',
            border: 'none',
            fontWeight: '700',
            background: activeTab === 'report' ? '#2b6cb0' : '#e2e8f0',
            color: activeTab === 'report' ? 'white' : '#2d3748',
            cursor: 'pointer'
          }}
        >
          📊 Reports
        </button>
      </div>

      {activeTab === 'trading' && (
        <>

      {/* Statistics Dashboard */}
      {stats && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '16px',
          marginBottom: '32px'
        }}>
          <div style={{
            padding: '20px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Total Trades</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold' }}>{stats.total_trades}</div>
          </div>
          <div style={{
            padding: '20px',
            background: 'linear-gradient(135deg, #48bb78 0%, #38a169 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Win Rate</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold' }}>{(stats.win_rate || 0).toFixed(2)}%</div>
          </div>
          <div style={{
            padding: '20px',
            background: 'linear-gradient(135deg, #4299e1 0%, #3182ce 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Daily P&L</div>
            <div style={{
              fontSize: '28px',
              fontWeight: 'bold',
              color: stats.daily_pnl >= 0 ? '#c6f6d5' : '#fed7d7'
            }}>
              ₹{(stats.daily_pnl || 0).toLocaleString()}
            </div>
          </div>
          <div style={{
            padding: '20px',
            background: 'linear-gradient(135deg, #ed8936 0%, #dd6b20 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Active Trades</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
              {stats.active_trades_count || 0} / {stats.max_trades || 2}
              {(stats.active_trades_count || 0) >= (stats.max_trades || 2) && (
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
            <div style={{ fontSize: '32px', fontWeight: 'bold' }}>{stats.target_points_per_trade || 25}pts</div>
          </div>

          {stats.portfolio_cap !== null && (
            <div style={{
              padding: '20px',
              background: 'linear-gradient(135deg, #319795 0%, #2c7a7b 100%)',
              borderRadius: '12px',
              color: 'white',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Capital In Use</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold' }}>₹{(stats.capital_in_use || 0).toLocaleString()}</div>
              <div style={{ fontSize: '12px', opacity: 0.85, marginTop: '6px' }}>
                Remaining: ₹{(stats.remaining_capital || 0).toLocaleString()} / Cap: ₹{(stats.portfolio_cap || 0).toLocaleString()}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Market Analysis */}
      {analysis && analysis.recommendation && (
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
                🎯 AI Recommendation ({analysis.signals_count} strategies analyzed)
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
                    {analysis.recommendation.strategy || 'Best Match'}
                  </span>
                </span>
                <span>
                  <strong>Action:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: analysis.recommendation.action === 'BUY' ? '#48bb78' : '#f56565',
                    color: 'white',
                    fontWeight: 'bold'
                  }}>
                    {analysis.recommendation.action}
                  </span>
                </span>
                <span><strong>Symbol:</strong> {analysis.recommendation.symbol}</span>
                <span><strong>Confidence:</strong> {analysis.recommendation.confidence}%</span>
                <span><strong>Quantity:</strong> {analysis.recommendation.quantity}</span>
                <span><strong>Expiry:</strong> {analysis.recommendation.expiry_date || analysis.recommendation.expiry}</span>
              </div>
            </div>
            {enabled && (
              <button
                onClick={executeAutoTrade}
                disabled={executing}
                style={{
                  padding: '12px 24px',
                  background: executing ? '#cbd5e0' : '#48bb78',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '15px',
                  fontWeight: '600',
                  cursor: executing ? 'not-allowed' : 'pointer'
                }}
              >
                {executing ? '⏳ Executing...' : '⚡ Execute Trade'}
              </button>
            )}
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
                ₹{analysis.recommendation.entry_price.toFixed(2)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>
                Target (+{analysis.recommendation.target_points || 25}pts)
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#48bb78' }}>
                ₹{analysis.recommendation.target.toFixed(2)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Stop Loss (-20pts)</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#f56565' }}>
                ₹{analysis.recommendation.stop_loss.toFixed(2)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Potential Profit</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#38a169' }}>
                ₹{analysis.recommendation.potential_profit.toLocaleString()}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Max Risk</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#e53e3e' }}>
                ₹{analysis.recommendation.risk.toLocaleString()}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Quantity</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#5a67d8' }}>
                {analysis.recommendation.quantity}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Expiry Date</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#2d3748' }}>
                {analysis.recommendation.expiry_date || 'N/A'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* All Signals Table */}
      {/* Debug: Raw signals output */}
      {analysis && analysis.signals && (
        <div style={{ margin: '16px 0', padding: '12px', background: '#f7fafc', border: '1px dashed #cbd5e0', borderRadius: '8px', fontSize: '12px', color: '#2d3748' }}>
          <strong>Debug: Raw signals array</strong>
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0 }}>
            {JSON.stringify(analysis.signals, null, 2)}
          </pre>
        </div>
      )}
      {analysis && analysis.signals && analysis.signals.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h4 style={{
            margin: '0 0 16px 0',
            color: '#2d3748',
            fontSize: '18px',
            fontWeight: 'bold'
          }}>
            📋 All Strategy Signals ({analysis.signals.length})
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
                {analysis.signals.map((signal, idx) => (
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
            📈 Active Trades ({activeTrades.length})
          </h4>
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '14px'
            }}>
              <thead>
                <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '12px', textAlign: 'left' }}>ID</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Action</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Target</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Stop Loss</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Strategy</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Time</th>
                </tr>
              </thead>
              <tbody>
                {activeTrades.map((trade, idx) => {
                  const entry = Number(trade.entry_price || trade.price || trade.underlying_price || 0);
                  const target = Number(trade.target || trade.exit_price || entry);
                  const stop = Number(trade.stop_loss || entry);
                  const action = trade.action || trade.side || 'BUY';
                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                      <td style={{ padding: '12px' }}>#{trade.id}</td>
                      <td style={{ padding: '12px', fontWeight: '600' }}>{trade.symbol || trade.index || '—'}</td>
                      <td style={{ padding: '12px' }}>
                        <span style={{
                          padding: '4px 8px',
                          borderRadius: '4px',
                          background: action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                          color: action === 'BUY' ? '#22543d' : '#742a2a',
                          fontSize: '12px',
                          fontWeight: 'bold'
                        }}>
                          {action}
                        </span>
                      </td>
                      <td style={{ padding: '12px', textAlign: 'right' }}>₹{entry.toFixed(2)}</td>
                      <td style={{ padding: '12px', textAlign: 'right', color: '#48bb78', fontWeight: '600' }}>
                        ₹{target.toFixed(2)}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'right', color: '#f56565', fontWeight: '600' }}>
                        ₹{stop.toFixed(2)}
                      </td>
                      <td style={{ padding: '12px', fontSize: '12px', color: '#718096' }}>{trade.strategy || trade.strategy_name || 'LIVE_TREND_FOLLOW'}</td>
                      <td style={{ padding: '12px', fontSize: '12px', color: '#718096' }}>
                        {trade.entry_time ? new Date(trade.entry_time).toLocaleTimeString() : '—'}
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
      </>
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
};

export default AutoTradingDashboard;
