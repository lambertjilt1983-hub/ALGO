import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import config from './config/api';
import AdminPanel from './components/AdminPanel';

function Dashboard() {
  const [user, setUser] = useState(null);
  const [brokers, setBrokers] = useState([]);
  const [brokerBalances, setBrokerBalances] = useState({});
  const [showBrokerForm, setShowBrokerForm] = useState(false);
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [showStrategyForm, setShowStrategyForm] = useState(false);
  const [deletingBroker, setDeletingBroker] = useState(null);
  const navigate = useNavigate();

  // New Broker Form States
  const [brokerName, setBrokerName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [accessToken, setAccessToken] = useState('');

  // New Order Form States
  const [selectedBroker, setSelectedBroker] = useState('');
  const [symbol, setSymbol] = useState('');
  const [quantity, setQuantity] = useState('');
  const [orderType, setOrderType] = useState('MARKET');
  const [side, setSide] = useState('BUY');

  // New Strategy Form States
  const [strategyName, setStrategyName] = useState('');
  const [strategyType, setStrategyType] = useState('MOVING_AVERAGE');
  const [parameters, setParameters] = useState('{}');

  // Market Intelligence States
  const [activeTab, setActiveTab] = useState('overview');
  const [marketSentiment, setMarketSentiment] = useState(null);
  const [marketTrends, setMarketTrends] = useState(null);
  const [marketNews, setMarketNews] = useState([]);
  const [sectors, setSectors] = useState([]);

  useEffect(() => {
    fetchUserData();
    fetchBrokers();
    fetchMarketIntelligence();
    
    // Check for Zerodha OAuth callback from backend
    const urlParams = new URLSearchParams(window.location.search);
    console.log('🔍 Checking URL params:', window.location.search);
    console.log('🔍 URL params object:', Object.fromEntries(urlParams.entries()));
    
    const zerodhaAuth = urlParams.get('zerodha_auth');
    const upstoxCode = urlParams.get('code');
    const upstoxState = urlParams.get('state');
    
    // Handle direct Zerodha redirect (when redirect_url is set to frontend)
    const status = urlParams.get('status');
    const requestToken = urlParams.get('request_token');
    
    console.log('🔍 Status:', status, 'Request Token:', requestToken);
    
    if (status === 'success' && requestToken) {
      const state = urlParams.get('state');
      const storedBrokerId = localStorage.getItem('zerodha_last_broker_id');
      const parsedBrokerId = state?.includes(':') ? state.split(':')[1] : state;
      const brokerId = parsedBrokerId || storedBrokerId;
      console.log('✅ Zerodha redirect detected, exchanging token...');
      handleZerodhaCallback(requestToken, brokerId);
      return;
    }

    if (upstoxCode && upstoxState?.startsWith('upstox:')) {
      const parts = upstoxState.split(':');
      const brokerId = parts[2];
      handleUpstoxCallback(upstoxCode, brokerId);
      return;
    }
    
    // Handle backend redirect
    if (zerodhaAuth === 'success') {
      alert('✓ Zerodha authentication successful! Your account is now connected.');
      // Clear URL params
      window.history.replaceState({}, document.title, window.location.pathname);
      // Refresh broker data
      setTimeout(() => {
        fetchBrokers();
      }, 1000);
    } else if (zerodhaAuth === 'error') {
      const msg = urlParams.get('msg') || 'Unknown error';
      alert(`Zerodha authentication failed: ${msg.replace(/_/g, ' ')}`);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const handleZerodhaCallback = async (requestToken, brokerId) => {
    try {
      const token = localStorage.getItem('access_token');

      if (!brokerId) {
        alert('Missing broker id for Zerodha token refresh. Please retry login from Brokers page.');
        return;
      }
      
      console.log('🔄 Exchanging Zerodha request token:', requestToken);
      
      // Call backend to exchange request token for access token
      const response = await fetch(`${config.API_BASE_URL}/api/tokens/refresh/${brokerId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ request_token: requestToken })
      });
      
      console.log('📥 Callback response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('✅ Callback response data:', data);
        
        if (data.status === 'success') {
          console.log('🎉 Token exchange successful! Broker ID:', data.broker_id);
          alert('✅ Zerodha connected! Access token saved. Real-time trading is now active.');
          
          // Clean URL
          window.history.replaceState({}, document.title, window.location.pathname);
          
          // Refresh broker data to show updated balance
          setTimeout(() => {
            fetchBrokers();
            // Also fetch balance immediately to verify token works
            if (data.broker_id) {
              fetchBrokerBalance(data.broker_id);
            }
          }, 500);
        } else {
          console.error('❌ Token exchange failed:', data.message);
          alert(`Zerodha authentication failed: ${data.message || 'Unknown error'}`);
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      } else {
        const errorText = await response.text();
        console.error('❌ Zerodha auth error:', errorText);
        alert(`Zerodha authentication failed: ${errorText}`);
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    } catch (error) {
      console.error('💥 Failed to complete Zerodha authentication:', error);
      alert('Network error during Zerodha authentication. Please check if backend is running and try again.');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  };

  const handleUpstoxCallback = async (code, brokerId) => {
    try {
      const token = localStorage.getItem('access_token');

      if (!brokerId) {
        alert('Missing broker id for Upstox token exchange. Please retry login from Brokers page.');
        return;
      }

      const response = await fetch(`${config.API_BASE_URL}/brokers/upstox/exchange/${brokerId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ code })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          alert('✅ Upstox connected! Access token saved.');
          window.history.replaceState({}, document.title, window.location.pathname);
          setTimeout(() => {
            fetchBrokers();
            if (data.broker_id) {
              fetchBrokerBalance(data.broker_id);
            }
          }, 500);
          return;
        }
      }

      const errorText = await response.text();
      alert(`Upstox authentication failed: ${errorText}`);
      window.history.replaceState({}, document.title, window.location.pathname);
    } catch (error) {
      console.error('Upstox auth error:', error);
      alert('Network error during Upstox authentication. Please check if backend is running and try again.');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  };

  const fetchUserData = async () => {
    try {
      const response = await config.authFetch(config.endpoints.auth.me);
      
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/';
        return;
      }
      
      const data = await response.json();
      setUser(data);
    } catch (error) {
      console.error('Failed to fetch user data:', error);
      // Don't redirect on network errors, only on 401 (handled above)
    }
  };

  const fetchBrokers = async () => {
    try {
      const response = await config.authFetch(config.endpoints.brokers.credentials);
      
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/';
        return;
      }
      
      const data = await response.json();
      setBrokers(data);
      
      // Fetch balance for each broker
      if (Array.isArray(data)) {
        data.forEach(broker => {
          fetchBrokerBalance(broker.id);
        });
      }
    } catch (error) {
      console.error('Failed to fetch brokers:', error);
      // Don't redirect on network errors, only on 401 (handled above)
    }
  };

  const fetchBrokerBalance = async (brokerId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${config.API_BASE_URL}/brokers/balance/${brokerId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const balanceData = await response.json();
        console.log(`Broker ${brokerId} balance response:`, balanceData);
        
        // If token is expired, trigger re-authentication flow
        if (balanceData.status === 'token_expired' || balanceData.requires_reauth) {
          console.warn(`Token expired for broker ${brokerId}, showing reconnect prompt`);
        }
        
        setBrokerBalances(prev => ({
          ...prev,
          [brokerId]: balanceData
        }));
      } else {
        console.error(`Failed to fetch balance for broker ${brokerId}: ${response.status}`);
      }
    } catch (error) {
      console.error(`Failed to fetch balance for broker ${brokerId}:`, error);
    }
  };

  const handleDeleteBroker = async (broker) => {
    if (!broker?.broker_name) {
      alert('Missing broker name');
      return;
    }

    const confirmed = window.confirm(`Remove broker ${broker.broker_name}? This cannot be undone.`);
    if (!confirmed) {
      return;
    }

    try {
      setDeletingBroker(broker.broker_name);
      const response = await config.authFetch(
        config.endpoints.brokers.credentialsByName(encodeURIComponent(broker.broker_name)),
        { method: 'DELETE' }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to delete broker');
      }

      setBrokers((prev) => prev.filter((item) => item.id !== broker.id));
      setBrokerBalances((prev) => {
        const next = { ...prev };
        delete next[broker.id];
        return next;
      });
    } catch (error) {
      alert(error.message || 'Failed to delete broker');
    } finally {
      setDeletingBroker(null);
    }
  };

  const fetchMarketIntelligence = async () => {
    try {
      const [sentimentRes, trendsRes, newsRes, sectorsRes] = await Promise.all([
        config.authFetch(config.endpoints.market.sentiment),
        config.authFetch(config.endpoints.market.trends),
        config.authFetch(config.getUrl(config.endpoints.market.news, { limit: 10 })),
        config.authFetch(config.endpoints.market.sectors)
      ]);

      if (sentimentRes.ok) {
        const data = await sentimentRes.json();
        setMarketSentiment(data.sentiment);
      }
      if (trendsRes.ok) {
        const data = await trendsRes.json();
        setMarketTrends(data.trends);
      }
      if (newsRes.ok) {
        const data = await newsRes.json();
        setMarketNews(data.news);
      }
      if (sectorsRes.ok) {
        const data = await sectorsRes.json();
        setSectors(data.sectors);
      }
    } catch (error) {
      console.error('Failed to fetch market intelligence:', error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/login');
  };

  const handleBrokerSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await config.authFetch(config.endpoints.brokers.credentials, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          broker_name: brokerName,
          api_key: apiKey,
          api_secret: apiSecret,
          access_token: accessToken
        })
      });

      if (response.ok) {
        alert('Broker connected successfully!');
        setShowBrokerForm(false);
        setBrokerName('');
        setApiKey('');
        setApiSecret('');
        setAccessToken('');
        fetchBrokers();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      alert('Failed to connect broker');
    }
  };

  const handleOrderSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await config.authFetch(config.endpoints.orders.create, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          broker_id: parseInt(selectedBroker),
          symbol: symbol,
          quantity: parseInt(quantity),
          order_type: orderType,
          side: side
        })
      });

      if (response.ok) {
        alert('Order placed successfully!');
        setShowOrderForm(false);
        setSelectedBroker('');
        setSymbol('');
        setQuantity('');
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      alert('Failed to place order');
    }
  };

  const handleStrategySubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await config.authFetch(config.endpoints.strategies.create, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: strategyName,
          strategy_type: strategyType,
          parameters: JSON.parse(parameters)
        })
      });

      if (response.ok) {
        alert('Strategy created successfully!');
        setShowStrategyForm(false);
        setStrategyName('');
        setParameters('{}');
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      alert('Failed to create strategy');
    }
  };

  const getTotalPortfolioValue = () => {
    return Object.values(brokerBalances).reduce((total, balance) => {
      return total + (balance.total_balance || 0);
    }, 0);
  };

  const handleZerodhaLogin = async (brokerId) => {
    // Prevent multiple clicks
    if (window.zerodhaLoginInProgress) {
      alert('Zerodha login already in progress. Please complete the current login.');
      return;
    }
    
    try {
      window.zerodhaLoginInProgress = true;
      localStorage.setItem('zerodha_last_broker_id', String(brokerId));
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${config.API_BASE_URL}/brokers/zerodha/login/${brokerId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        // Open Zerodha login in new window
        const loginWindow = window.open(data.login_url, 'ZerodhaLogin', 'width=600,height=800');
        
        // Show message to user
        alert('Zerodha login window opened. After logging in, close this alert and refresh the page.');
        
        // Reset flag when user closes the window
        const checkWindow = setInterval(() => {
          if (loginWindow.closed) {
            clearInterval(checkWindow);
            window.zerodhaLoginInProgress = false;
            // Refresh broker data
            setTimeout(() => {
              fetchBrokers();
            }, 2000);
          }
        }, 1000);
      } else {
        window.zerodhaLoginInProgress = false;
        alert('Failed to initiate Zerodha login');
      }
    } catch (error) {
      window.zerodhaLoginInProgress = false;
      alert('Error: ' + error.message);
    }
  };

  const handleUpstoxLogin = async (brokerId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${config.API_BASE_URL}/brokers/upstox/login/${brokerId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const errorText = await response.text();
        alert(`Failed to initiate Upstox login: ${errorText}`);
        return;
      }

      const data = await response.json();
      window.open(data.login_url, 'UpstoxLogin', 'width=600,height=800');
      alert('Upstox login window opened. After logging in, close this alert and refresh the page.');
    } catch (error) {
      console.error('Upstox login error:', error);
      alert('Failed to initiate Upstox login');
    }
  };

  if (!user) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
      }}>
        <div style={{
          fontSize: '24px',
          color: 'white',
          fontWeight: 'bold'
        }}>
          Loading...
        </div>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    }}>
      {/* Navigation Bar */}
      <nav style={{
        padding: '20px 40px',
        background: 'rgba(255, 255, 255, 0.1)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{
          color: 'white',
          margin: 0,
          fontSize: '28px',
          fontWeight: 'bold'
        }}>
          AlgoTrade Pro
        </h1>
        <button
          onClick={handleLogout}
          style={{
            padding: '10px 24px',
            background: 'rgba(255, 255, 255, 0.2)',
            color: 'white',
            border: '1px solid rgba(255, 255, 255, 0.3)',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            transition: 'all 0.3s ease'
          }}
        >
          Logout
        </button>
      </nav>

      {/* Main Content */}
      <div style={{
        padding: '40px',
        maxWidth: '1400px',
        margin: '0 auto'
      }}>
        {/* Welcome Section */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.95)',
          borderRadius: '16px',
          padding: '32px',
          marginBottom: '32px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
        }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: '24px',
            alignItems: 'center'
          }}>
            <div>
              <h2 style={{
                margin: '0 0 8px 0',
                color: '#2d3748',
                fontSize: '24px'
              }}>
                Welcome back, {user.username}!
              </h2>
              <p style={{
                margin: '4px 0',
                color: '#718096',
                fontSize: '14px'
              }}>
                User ID: #{user.id}
              </p>
              <p style={{
                margin: '4px 0',
                color: '#718096',
                fontSize: '14px'
              }}>
                {user.email}
              </p>
              <p style={{
                margin: '4px 0',
                color: '#718096',
                fontSize: '14px'
              }}>
                Member since {new Date(user.created_at).toLocaleDateString()}
              </p>
            </div>

            {Object.keys(brokerBalances).length > 0 && (
              <div style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                borderRadius: '12px',
                padding: '24px',
                color: 'white',
                textAlign: 'center'
              }}>
                <div style={{
                  fontSize: '14px',
                  opacity: '0.9',
                  marginBottom: '8px',
                  fontWeight: '500'
                }}>
                  Total Portfolio Value
                </div>
                <div style={{
                  fontSize: '32px',
                  fontWeight: 'bold',
                  marginBottom: '4px'
                }}>
                  ₹{getTotalPortfolioValue().toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                {Object.values(brokerBalances).some(b => typeof b.data_source === 'string' && b.data_source.startsWith('real_')) ? (
                  <div style={{
                    fontSize: '12px',
                    opacity: '0.9',
                    background: 'rgba(52, 211, 153, 0.3)',
                    padding: '4px 12px',
                    borderRadius: '12px',
                    display: 'inline-block',
                    marginTop: '8px'
                  }}>
                    ✓ Live Market Data
                  </div>
                ) : brokers.some(b => b.broker_name?.toLowerCase().includes('zerodha')) &&
                  Object.values(brokerBalances).some(b => b.status === 'token_expired' || b.requires_reauth) ? (
                  <div style={{
                    fontSize: '12px',
                    opacity: '0.8',
                    background: 'rgba(251, 146, 60, 0.3)',
                    padding: '4px 12px',
                    borderRadius: '12px',
                    display: 'inline-block',
                    marginTop: '8px',
                    color: '#ea580c'
                  }}>
                    ⚠️ Zerodha authentication required
                  </div>
                ) : brokers.length > 0 ? (
                  <div style={{
                    fontSize: '12px',
                    opacity: '0.85',
                    background: 'rgba(255, 255, 255, 0.18)',
                    padding: '4px 12px',
                    borderRadius: '12px',
                    display: 'inline-block',
                    marginTop: '8px'
                  }}>
                    ✓ Brokers connected - balance depends on broker API
                  </div>
                ) : (
                  <div style={{
                    fontSize: '12px',
                    opacity: '0.8',
                    background: 'rgba(255, 255, 255, 0.2)',
                    padding: '4px 12px',
                    borderRadius: '12px',
                    display: 'inline-block',
                    marginTop: '8px'
                  }}>
                    ⚠️ Demo Data - Connect Broker for Real Data
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {user.is_admin && (
          <div style={{ marginBottom: '32px' }}>
            <AdminPanel user={user} />
          </div>
        )}

        {/* Action Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
          marginBottom: '32px'
        }}>
          {/* Connect Broker Card */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.95)',
            borderRadius: '16px',
            padding: '24px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
            cursor: 'pointer',
            transition: 'transform 0.3s ease, box-shadow 0.3s ease',
            ':hover': {
              transform: 'translateY(-4px)'
            }
          }}
          onClick={() => setShowBrokerForm(!showBrokerForm)}
          >
            <div style={{
              fontSize: '40px',
              marginBottom: '12px'
            }}>
              🔗
            </div>
            <h3 style={{
              margin: '0 0 8px 0',
              color: '#2d3748',
              fontSize: '20px'
            }}>
              Connect Broker
            </h3>
            <p style={{
              margin: 0,
              color: '#718096',
              fontSize: '14px'
            }}>
              Link your Zerodha account
            </p>
          </div>

          {/* Place Order Card */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.95)',
            borderRadius: '16px',
            padding: '24px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
            cursor: 'pointer',
            transition: 'transform 0.3s ease'
          }}
          onClick={() => setShowOrderForm(!showOrderForm)}
          >
            <div style={{
              fontSize: '40px',
              marginBottom: '12px'
            }}>
              📊
            </div>
            <h3 style={{
              margin: '0 0 8px 0',
              color: '#2d3748',
              fontSize: '20px'
            }}>
              Place Order
            </h3>
            <p style={{
              margin: 0,
              color: '#718096',
              fontSize: '14px'
            }}>
              Execute a new trade
            </p>
          </div>

          {/* Create Strategy Card */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.95)',
            borderRadius: '16px',
            padding: '24px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
            cursor: 'pointer',
            transition: 'transform 0.3s ease'
          }}
          onClick={() => setShowStrategyForm(!showStrategyForm)}
          >
            <div style={{
              fontSize: '40px',
              marginBottom: '12px'
            }}>
              🤖
            </div>
            <h3 style={{
              margin: '0 0 8px 0',
              color: '#2d3748',
              fontSize: '20px'
            }}>
              Create Strategy
            </h3>
            <p style={{
              margin: 0,
              color: '#718096',
              fontSize: '14px'
            }}>
              Build algo trading strategy
            </p>
          </div>
        </div>

        {/* Connected Brokers */}
        {brokers.length > 0 && (
          <div style={{
            background: 'rgba(255, 255, 255, 0.95)',
            borderRadius: '16px',
            padding: '32px',
            marginBottom: '32px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
          }}>
            <h3 style={{
              margin: '0 0 24px 0',
              color: '#2d3748',
              fontSize: '22px'
            }}>
              Connected Brokers
            </h3>
            <div style={{
              display: 'grid',
              gap: '16px'
            }}>
              {brokers.map(broker => (
                <div key={broker.id} style={{
                  background: 'linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%)',
                  borderRadius: '12px',
                  padding: '20px',
                  border: '1px solid #e2e8f0'
                }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    marginBottom: '12px'
                  }}>
                    <div>
                      <h4 style={{
                        margin: '0 0 8px 0',
                        color: '#2d3748',
                        fontSize: '18px',
                        fontWeight: 'bold'
                      }}>
                        {broker.broker_name}
                      </h4>
                      <p style={{
                        margin: '4px 0',
                        color: '#718096',
                        fontSize: '13px'
                      }}>
                        Broker ID: #{broker.id}
                      </p>
                      <p style={{
                        margin: '4px 0',
                        color: '#718096',
                        fontSize: '13px'
                      }}>
                        Connected: {new Date(broker.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span style={{
                      padding: '6px 16px',
                      background: broker.is_active ? '#48bb78' : '#f56565',
                      color: 'white',
                      borderRadius: '20px',
                      fontSize: '12px',
                      fontWeight: '600'
                    }}>
                      {broker.is_active ? '● Active' : '● Inactive'}
                    </span>
                  </div>
                  
                  {/* Zerodha OAuth Button */}
                  {broker.broker_name.toLowerCase().includes('zerodha') && (broker.requires_reauth || !broker.has_access_token) && (
                    <button
                      onClick={() => handleZerodhaLogin(broker.id)}
                      style={{
                        width: '100%',
                        padding: '12px',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '8px',
                        fontSize: '14px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        marginBottom: '12px'
                      }}
                    >
                      🔐 Reconnect Zerodha
                    </button>
                  )}

                  {broker.broker_name.toLowerCase().includes('upstox') && (broker.requires_reauth || !broker.has_access_token) && (
                    <button
                      onClick={() => handleUpstoxLogin(broker.id)}
                      style={{
                        width: '100%',
                        padding: '12px',
                        background: 'linear-gradient(135deg, #38b2ac 0%, #319795 100%)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '8px',
                        fontSize: '14px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        marginBottom: '12px'
                      }}
                    >
                      🔐 Connect Upstox
                    </button>
                  )}

                  <button
                    onClick={() => handleDeleteBroker(broker)}
                    disabled={deletingBroker === broker.broker_name}
                    style={{
                      width: '100%',
                      padding: '10px',
                      background: '#fff5f5',
                      color: '#c53030',
                      border: '1px solid #fed7d7',
                      borderRadius: '8px',
                      fontSize: '13px',
                      fontWeight: '600',
                      cursor: deletingBroker === broker.broker_name ? 'not-allowed' : 'pointer',
                      opacity: deletingBroker === broker.broker_name ? 0.6 : 1
                    }}
                  >
                    {deletingBroker === broker.broker_name ? 'Removing...' : 'Remove Broker'}
                  </button>
                  
                  {brokerBalances[broker.id] && (
                    <div style={{
                      background: 'white',
                      borderRadius: '8px',
                      padding: '16px',
                      marginTop: '12px',
                      border: '1px solid #e2e8f0'
                    }}>
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                        gap: '16px'
                      }}>
                        <div>
                          <div style={{
                            fontSize: '12px',
                            color: '#718096',
                            marginBottom: '4px',
                            fontWeight: '500'
                          }}>
                            Available Balance
                          </div>
                          <div style={{
                            fontSize: '20px',
                            color: '#2d3748',
                            fontWeight: 'bold'
                          }}>
                            ₹{brokerBalances[broker.id].available_balance.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </div>
                        </div>
                        <div>
                          <div style={{
                            fontSize: '12px',
                            color: '#718096',
                            marginBottom: '4px',
                            fontWeight: '500'
                          }}>
                            Total Balance
                          </div>
                          <div style={{
                            fontSize: '20px',
                            color: '#2d3748',
                            fontWeight: 'bold'
                          }}>
                            ₹{brokerBalances[broker.id].total_balance.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </div>
                        </div>
                        <div>
                          <div style={{
                            fontSize: '12px',
                            color: '#718096',
                            marginBottom: '4px',
                            fontWeight: '500'
                          }}>
                            Used Margin
                          </div>
                          <div style={{
                            fontSize: '20px',
                            color: '#e53e3e',
                            fontWeight: 'bold'
                          }}>
                            ₹{brokerBalances[broker.id].used_margin.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </div>
                        </div>
                      </div>
                      <div style={{
                        marginTop: '12px',
                        padding: '8px 12px',
                        background: brokerBalances[broker.id].data_source?.startsWith('real_') ? '#d1fae5' : '#fef5e7',
                        borderRadius: '6px',
                        border: `1px solid ${brokerBalances[broker.id].data_source?.startsWith('real_') ? '#6ee7b7' : '#f9e79f'}`,
                        fontSize: '11px',
                        color: brokerBalances[broker.id].data_source?.startsWith('real_') ? '#065f46' : '#856404'
                      }}>
                        {brokerBalances[broker.id].data_source?.startsWith('real_')
                          ? `✓ Live Data from ${broker.broker_name}`
                          : brokerBalances[broker.id].message
                            ? `⚠️ ${brokerBalances[broker.id].message}`
                            : brokerBalances[broker.id].error
                              ? `⚠️ ${brokerBalances[broker.id].error}`
                              : `⚠️ Connect ${broker.broker_name} with access token for real balance`}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            {/* Auto Trading Engine Link */}
            <div style={{ marginTop: '32px', display: 'flex', alignItems: 'center' }}>
              <span style={{ marginRight: '8px' }}>🤖</span>
              <a
                href="/autotrading"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: '#2563eb', textDecoration: 'underline', fontWeight: 600 }}
              >
                Auto Trading Engine
              </a>
            </div>
          </div>
        )}

        {/* Broker Form Modal */}
        {showBrokerForm && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000
          }}
          onClick={() => setShowBrokerForm(false)}
          >
            <div style={{
              background: 'white',
              borderRadius: '16px',
              padding: '32px',
              maxWidth: '500px',
              width: '90%',
              maxHeight: '90vh',
              overflowY: 'auto'
            }}
            onClick={(e) => e.stopPropagation()}
            >
              <h2 style={{
                margin: '0 0 24px 0',
                color: '#2d3748'
              }}>
                Connect Broker Account
              </h2>
              <form onSubmit={handleBrokerSubmit}>
                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Broker Name
                  </label>
                  <select
                    value={brokerName}
                    onChange={(e) => setBrokerName(e.target.value)}
                    required
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px',
                      backgroundColor: 'white',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="">Select a broker...</option>
                    <option value="zerodha">Zerodha (Fully Supported)</option>
                    <option value="upstox">Upstox</option>
                    <option value="angel_one">Angel One</option>
                    <option value="groww">Groww</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    API Key
                  </label>
                  <input
                    type="text"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Your API Key"
                    required
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    API Secret
                  </label>
                  <input
                    type="password"
                    value={apiSecret}
                    onChange={(e) => setApiSecret(e.target.value)}
                    placeholder="Your API Secret"
                    required
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Access Token (Optional)
                  </label>
                  <input
                    type="text"
                    value={accessToken}
                    onChange={(e) => setAccessToken(e.target.value)}
                    placeholder="Access Token"
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div style={{
                  display: 'flex',
                  gap: '12px'
                }}>
                  <button
                    type="submit"
                    style={{
                      flex: 1,
                      padding: '12px',
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '16px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    Connect
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowBrokerForm(false)}
                    style={{
                      flex: 1,
                      padding: '12px',
                      background: '#e2e8f0',
                      color: '#2d3748',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '16px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Order Form Modal */}
        {showOrderForm && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000
          }}
          onClick={() => setShowOrderForm(false)}
          >
            <div style={{
              background: 'white',
              borderRadius: '16px',
              padding: '32px',
              maxWidth: '500px',
              width: '90%',
              maxHeight: '90vh',
              overflowY: 'auto'
            }}
            onClick={(e) => e.stopPropagation()}
            >
              <h2 style={{
                margin: '0 0 24px 0',
                color: '#2d3748'
              }}>
                Place New Order
              </h2>
              <form onSubmit={handleOrderSubmit}>
                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Select Broker
                  </label>
                  <select
                    value={selectedBroker}
                    onChange={(e) => setSelectedBroker(e.target.value)}
                    required
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  >
                    <option value="">Select a broker</option>
                    {brokers.map(broker => (
                      <option key={broker.id} value={broker.id}>
                        {broker.broker_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Symbol
                  </label>
                  <input
                    type="text"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    placeholder="e.g., RELIANCE"
                    required
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Quantity
                  </label>
                  <input
                    type="number"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    placeholder="Number of shares"
                    required
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Order Type
                  </label>
                  <select
                    value={orderType}
                    onChange={(e) => setOrderType(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  >
                    <option value="MARKET">Market Order</option>
                    <option value="LIMIT">Limit Order</option>
                  </select>
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Side
                  </label>
                  <select
                    value={side}
                    onChange={(e) => setSide(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  >
                    <option value="BUY">Buy</option>
                    <option value="SELL">Sell</option>
                  </select>
                </div>

                <div style={{
                  display: 'flex',
                  gap: '12px'
                }}>
                  <button
                    type="submit"
                    style={{
                      flex: 1,
                      padding: '12px',
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '16px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    Place Order
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowOrderForm(false)}
                    style={{
                      flex: 1,
                      padding: '12px',
                      background: '#e2e8f0',
                      color: '#2d3748',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '16px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Strategy Form Modal */}
        {showStrategyForm && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000
          }}
          onClick={() => setShowStrategyForm(false)}
          >
            <div style={{
              background: 'white',
              borderRadius: '16px',
              padding: '32px',
              maxWidth: '500px',
              width: '90%',
              maxHeight: '90vh',
              overflowY: 'auto'
            }}
            onClick={(e) => e.stopPropagation()}
            >
              <h2 style={{
                margin: '0 0 24px 0',
                color: '#2d3748'
              }}>
                Create Trading Strategy
              </h2>
              <form onSubmit={handleStrategySubmit}>
                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Strategy Name
                  </label>
                  <input
                    type="text"
                    value={strategyName}
                    onChange={(e) => setStrategyName(e.target.value)}
                    placeholder="My Strategy"
                    required
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Strategy Type
                  </label>
                  <select
                    value={strategyType}
                    onChange={(e) => setStrategyType(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px'
                    }}
                  >
                    <option value="MOVING_AVERAGE">Moving Average</option>
                    <option value="RSI">RSI</option>
                    <option value="MACD">MACD</option>
                    <option value="BOLLINGER_BANDS">Bollinger Bands</option>
                  </select>
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <label style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: '#2d3748',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    Parameters (JSON)
                  </label>
                  <textarea
                    value={parameters}
                    onChange={(e) => setParameters(e.target.value)}
                    placeholder='{"period": 20, "threshold": 70}'
                    rows={4}
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '14px',
                      fontFamily: 'monospace'
                    }}
                  />
                </div>

                <div style={{
                  display: 'flex',
                  gap: '12px'
                }}>
                  <button
                    type="submit"
                    style={{
                      flex: 1,
                      padding: '12px',
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '16px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    Create Strategy
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowStrategyForm(false)}
                    style={{
                      flex: 1,
                      padding: '12px',
                      background: '#e2e8f0',
                      color: '#2d3748',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '16px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Market Intelligence Section */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.95)',
          borderRadius: '16px',
          padding: '32px',
          marginBottom: '32px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
        }}>
          <h3 style={{
            margin: '0 0 24px 0',
            color: '#2d3748',
            fontSize: '20px',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            📊 Market Intelligence & News
            <button
              onClick={fetchMarketIntelligence}
              style={{
                marginLeft: 'auto',
                padding: '8px 16px',
                background: '#4299e1',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontSize: '12px',
                cursor: 'pointer'
              }}
            >
              🔄 Refresh
            </button>
          </h3>

          {/* Market Sentiment */}
          {marketSentiment && (
            <div style={{
              marginBottom: '24px',
              padding: '16px',
              background: '#f7fafc',
              borderRadius: '8px',
              border: '1px solid #e2e8f0'
            }}>
              <h4 style={{ margin: '0 0 12px 0', color: '#2d3748', fontSize: '16px' }}>
                📰 Market Sentiment
              </h4>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: '16px'
              }}>
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#718096' }}>Overall</p>
                  <p style={{
                    margin: 0,
                    fontSize: '18px',
                    fontWeight: 'bold',
                    color: marketSentiment.overall_sentiment === 'Bullish' || marketSentiment.overall_sentiment === 'Strongly Bullish' ? '#48bb78' :
                          marketSentiment.overall_sentiment === 'Bearish' ? '#f56565' : '#ecc94b'
                  }}>
                    {marketSentiment.overall_sentiment}
                  </p>
                </div>
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#718096' }}>Score</p>
                  <p style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#2d3748' }}>
                    {marketSentiment.sentiment_score}
                  </p>
                </div>
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#718096' }}>Positive</p>
                  <p style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#48bb78' }}>
                    {marketSentiment.positive_news_count} ({marketSentiment.positive_percentage}%)
                  </p>
                </div>
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#718096' }}>Negative</p>
                  <p style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#f56565' }}>
                    {marketSentiment.negative_news_count}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Market Trends */}
          {marketTrends && marketTrends.indices && (
            <div style={{
              marginBottom: '24px',
              padding: '16px',
              background: '#f7fafc',
              borderRadius: '8px',
              border: '1px solid #e2e8f0'
            }}>
              <h4 style={{ margin: '0 0 12px 0', color: '#2d3748', fontSize: '16px' }}>
                📈 Index Trends - {marketTrends.market_status}
              </h4>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px'
              }}>
                {Object.entries(marketTrends.indices).slice(0, 4).map(([name, data]) => (
                  <div key={name} style={{
                    padding: '12px',
                    background: 'white',
                    borderRadius: '6px',
                    border: '1px solid #e2e8f0'
                  }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      marginBottom: '8px'
                    }}>
                      <span style={{ fontWeight: 'bold', color: '#2d3748' }}>{name}</span>
                      <span style={{
                        color: data.change >= 0 ? '#48bb78' : '#f56565',
                        fontWeight: 'bold'
                      }}>
                        {data.change >= 0 ? '+' : ''}{data.change_percent}%
                      </span>
                    </div>
                    <p style={{ margin: '0 0 4px 0', fontSize: '14px', color: '#4a5568' }}>
                      {data.current.toFixed(2)}
                    </p>
                    <p style={{ margin: 0, fontSize: '11px', color: '#718096' }}>
                      {data.trend} • {data.strength} • RSI: {data.rsi}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top Sectors */}
          {sectors && sectors.length > 0 && (
            <div style={{
              marginBottom: '24px',
              padding: '16px',
              background: '#f7fafc',
              borderRadius: '8px',
              border: '1px solid #e2e8f0'
            }}>
              <h4 style={{ margin: '0 0 12px 0', color: '#2d3748', fontSize: '16px' }}>
                🎯 Sector Performance
              </h4>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '8px'
              }}>
                {sectors.slice(0, 8).map((sector, idx) => (
                  <div key={idx} style={{
                    padding: '8px 12px',
                    background: 'white',
                    borderRadius: '6px',
                    border: '1px solid #e2e8f0',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}>
                    <span style={{ fontSize: '13px', color: '#2d3748', fontWeight: '500' }}>
                      {sector.name}
                    </span>
                    <span style={{
                      fontSize: '13px',
                      fontWeight: 'bold',
                      color: parseFloat(sector.performance.replace('%', '')) >= 0 ? '#48bb78' : '#f56565'
                    }}>
                      {sector.performance}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Latest News */}
          {marketNews && marketNews.length > 0 && (
            <div style={{
              padding: '16px',
              background: '#f7fafc',
              borderRadius: '8px',
              border: '1px solid #e2e8f0'
            }}>
              <h4 style={{ margin: '0 0 12px 0', color: '#2d3748', fontSize: '16px' }}>
                📰 Latest Market News
              </h4>
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {marketNews.map((news, idx) => (
                  <div key={idx} style={{
                    padding: '12px',
                    marginBottom: '8px',
                    background: 'white',
                    borderRadius: '6px',
                    border: '1px solid #e2e8f0'
                  }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'start',
                      gap: '12px'
                    }}>
                      <div style={{ flex: 1 }}>
                        <p style={{
                          margin: '0 0 6px 0',
                          fontSize: '14px',
                          fontWeight: '500',
                          color: '#2d3748',
                          lineHeight: '1.4'
                        }}>
                          {news.title}
                        </p>
                        <div style={{
                          display: 'flex',
                          gap: '12px',
                          fontSize: '11px',
                          color: '#718096'
                        }}>
                          <span>{news.source}</span>
                          <span>•</span>
                          <span>{news.category}</span>
                          <span>•</span>
                          <span>{new Date(news.timestamp).toLocaleTimeString()}</span>
                        </div>
                      </div>
                      <span style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: 'bold',
                        whiteSpace: 'nowrap',
                        background: news.sentiment.sentiment === 'positive' ? '#c6f6d5' :
                                   news.sentiment.sentiment === 'negative' ? '#fed7d7' : '#e2e8f0',
                        color: news.sentiment.sentiment === 'positive' ? '#22543d' :
                               news.sentiment.sentiment === 'negative' ? '#742a2a' : '#2d3748'
                      }}>
                        {news.sentiment.sentiment.toUpperCase()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;

