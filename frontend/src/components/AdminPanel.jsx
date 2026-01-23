import React, { useEffect, useState, useCallback } from 'react';
import config from '../config/api';

const badge = (label, tone = '#2563eb', bg = 'rgba(37, 99, 235, 0.12)') => (
  <span style={{
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 10px',
    borderRadius: '999px',
    fontSize: '12px',
    fontWeight: 700,
    color: tone,
    background: bg,
    letterSpacing: '0.02em',
  }}>
    ● {label}
  </span>
);

const formatValue = (value) => {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? badge('YES', '#16a34a', 'rgba(22, 163, 74, 0.12)') : badge('NO', '#dc2626', 'rgba(220, 38, 38, 0.12)');
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && value.length > 42) return value.slice(0, 39) + '…';
  if (typeof value === 'string' && value.includes('T')) return new Date(value).toLocaleString();
  return value;
};

function AdminPanel({ user }) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [updatingUserId, setUpdatingUserId] = useState(null);
  const [profileForm, setProfileForm] = useState({ username: '', email: '', mobile: '', password: '' });
  const [profileSaving, setProfileSaving] = useState(false);

  const loadSnapshot = useCallback(async () => {
    if (!user?.is_admin) return;
    setLoading(true);
    setError('');
    try {
      const response = await config.authFetch(config.endpoints.admin.overview);
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Unable to load admin data');
      }
      const data = await response.json();
      setSnapshot(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadSnapshot();
  }, [loadSnapshot]);

  useEffect(() => {
    if (user) {
      setProfileForm({
        username: user.username || '',
        email: user.email || '',
        mobile: user.mobile || '',
        password: '',
      });
    }
  }, [user]);

  const updateUser = async (targetId, changes) => {
    setUpdatingUserId(targetId);
    setError('');
    try {
      const response = await config.authFetch(config.endpoints.admin.updateUser(targetId), {
        method: 'PATCH',
        body: JSON.stringify(changes),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || 'Failed to update user');
      }
      setSnapshot((prev) =>
        prev
          ? {
              ...prev,
              users: prev.users.map((u) => (u.id === payload.id ? payload : u)),
            }
          : prev
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleProfileSave = async () => {
    if (!user) return;
    setProfileSaving(true);
    setError('');
    try {
      const payload = {
        username: profileForm.username,
        email: profileForm.email,
        mobile: profileForm.mobile,
      };
      if (profileForm.password) {
        payload.password = profileForm.password;
      }
      const response = await config.authFetch(config.endpoints.admin.updateUser(user.id), {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to save profile');
      }
      setSnapshot((prev) =>
        prev
          ? {
              ...prev,
              users: prev.users.map((u) => (u.id === data.id ? data : u)),
            }
          : prev
      );
      setProfileForm((prev) => ({ ...prev, password: '' }));
    } catch (err) {
      setError(err.message);
    } finally {
      setProfileSaving(false);
    }
  };

  const scrollToProfile = () => {
    const el = document.getElementById('admin-profile');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const renderTable = (title, rows, columns, extraContent = null) => {
    if (!rows || rows.length === 0) return null;
    return (
      <div style={{
        background: 'linear-gradient(135deg, rgba(17, 24, 39, 0.88), rgba(30, 64, 175, 0.92))',
        borderRadius: '18px',
        padding: '20px',
        color: 'white',
        boxShadow: '0 16px 40px rgba(0,0,0,0.25)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 800, letterSpacing: '0.02em' }}>{title}</h3>
          <span style={{ fontSize: '13px', opacity: 0.85 }}>{rows.length} rows</span>
        </div>
        {extraContent}
        <div style={{ overflowX: 'auto', borderRadius: '12px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '0 6px' }}>
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.key} style={{ textAlign: 'left', padding: '10px 12px', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'rgba(255,255,255,0.8)' }}>
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} style={{ background: 'rgba(255,255,255,0.03)' }}>
                  {columns.map((col) => (
                    <td key={col.key} style={{ padding: '10px 12px', fontSize: '13px', color: 'rgba(255,255,255,0.92)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      {col.render ? col.render(row) : formatValue(row[col.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  if (!user?.is_admin) return null;

  return (
    <div style={{
      marginBottom: '28px',
      display: 'grid',
      gap: '18px',
    }}>
      <div id="admin-profile" style={{
        padding: '20px',
        borderRadius: '16px',
        background: 'linear-gradient(135deg, #0f172a, #1e3a8a)',
        color: 'white',
        boxShadow: '0 14px 30px rgba(0,0,0,0.25)',
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <p style={{ margin: 0, fontSize: '12px', letterSpacing: '0.08em', opacity: 0.75 }}>ADMIN CONSOLE</p>
            <h2 style={{ margin: '4px 0 6px', fontSize: '22px', fontWeight: 800 }}>System snapshot & user controls</h2>
            <p style={{ margin: 0, fontSize: '13px', opacity: 0.85 }}>
              Signed in as <strong>{user.username}</strong>. Edit permissions, audit every table, and keep a live pulse on data.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <button
              onClick={scrollToProfile}
              style={{
                padding: '10px 14px',
                background: 'rgba(255,255,255,0.12)',
                color: 'white',
                border: '1px solid rgba(255,255,255,0.22)',
                borderRadius: '10px',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 6px 14px rgba(0,0,0,0.18)'
              }}
            >
              Profile
            </button>
            <button
              onClick={loadSnapshot}
              style={{
                padding: '10px 14px',
                background: 'white',
                color: '#0f172a',
                border: 'none',
                borderRadius: '10px',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 10px 20px rgba(255,255,255,0.12)'
              }}
            >
              Refresh
            </button>
            {loading ? badge('Loading…', '#fbbf24', 'rgba(251, 191, 36, 0.16)') : badge('Live', '#22c55e', 'rgba(34,197,94,0.14)')}
          </div>
        </div>
        {snapshot && (
          <div style={{
            marginTop: '16px',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px'
          }}>
            <div style={{
              padding: '14px',
              borderRadius: '12px',
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.12)'
            }}>
              <p style={{ margin: '0 0 6px', fontSize: '12px', letterSpacing: '0.04em', opacity: 0.8 }}>Profile</p>
              <p style={{ margin: 0, fontSize: '15px', fontWeight: 700 }}>{user.username}</p>
              <p style={{ margin: '2px 0 0', fontSize: '12px', opacity: 0.8 }}>{user.email}</p>
            </div>
            <div style={{
              padding: '14px',
              borderRadius: '12px',
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.12)'
            }}>
              <p style={{ margin: '0 0 6px', fontSize: '12px', letterSpacing: '0.04em', opacity: 0.8 }}>DB Snapshot</p>
              <p style={{ margin: 0, fontSize: '24px', fontWeight: 800 }}>{snapshot.users?.length || 0} users</p>
              <p style={{ margin: '4px 0 0', fontSize: '12px', opacity: 0.8 }}>{snapshot.brokers?.length || 0} brokers • {snapshot.orders?.length || 0} orders</p>
            </div>
            <div style={{
              padding: '14px',
              borderRadius: '12px',
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.12)'
            }}>
              <p style={{ margin: '0 0 6px', fontSize: '12px', letterSpacing: '0.04em', opacity: 0.8 }}>Verification</p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {badge(user.is_admin ? 'ADMIN' : 'USER', user.is_admin ? '#f59e0b' : '#cbd5e1', user.is_admin ? 'rgba(245, 158, 11, 0.18)' : 'rgba(148, 163, 184, 0.16)')}
                {badge(user.is_active ? 'ACTIVE' : 'INACTIVE', user.is_active ? '#22c55e' : '#ef4444', user.is_active ? 'rgba(34, 197, 94, 0.14)' : 'rgba(239, 68, 68, 0.18)')}
                {badge(user.is_email_verified ? 'EMAIL OK' : 'EMAIL PENDING', user.is_email_verified ? '#10b981' : '#f59e0b', user.is_email_verified ? 'rgba(16, 185, 129, 0.16)' : 'rgba(245, 158, 11, 0.16)')}
                {badge(user.is_mobile_verified ? 'MOBILE OK' : 'MOBILE PENDING', user.is_mobile_verified ? '#10b981' : '#f59e0b', user.is_mobile_verified ? 'rgba(16, 185, 129, 0.16)' : 'rgba(245, 158, 11, 0.16)')}
              </div>
            </div>
          </div>
        )}
        {error && (
          <div style={{
            marginTop: '12px',
            padding: '10px',
            borderRadius: '10px',
            background: 'rgba(220, 38, 38, 0.15)',
            color: '#fecdd3',
            border: '1px solid rgba(248, 113, 113, 0.4)',
            fontSize: '13px'
          }}>
            {error}
          </div>
        )}
      </div>

      {loading && (
        <div style={{
          padding: '16px',
          borderRadius: '12px',
          background: 'rgba(15, 23, 42, 0.8)',
          color: 'white',
          border: '1px solid rgba(255,255,255,0.08)',
          fontWeight: 600,
          letterSpacing: '0.03em'
        }}>
          Pulling the latest records…
        </div>
      )}

      {!loading && snapshot && (
        <>
          <div id="profile-edit" style={{
            background: 'rgba(255,255,255,0.95)',
            borderRadius: '14px',
            padding: '18px',
            border: '1px solid #e2e8f0',
            boxShadow: '0 10px 24px rgba(0,0,0,0.08)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <p style={{ margin: 0, fontSize: '12px', letterSpacing: '0.08em', color: '#64748b', fontWeight: 700 }}>PROFILE</p>
                <h3 style={{ margin: '4px 0 0', fontSize: '18px', color: '#0f172a' }}>Edit your account</h3>
              </div>
              {profileSaving ? badge('Saving…', '#f59e0b', 'rgba(245, 158, 11, 0.16)') : badge('Ready', '#16a34a', 'rgba(22, 163, 74, 0.12)')}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>Username</label>
                <input
                  type="text"
                  value={profileForm.username}
                  onChange={(e) => setProfileForm({ ...profileForm, username: e.target.value })}
                  style={{ width: '100%', padding: '10px', borderRadius: '10px', border: '1px solid #e2e8f0', fontSize: '14px' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>Email</label>
                <input
                  type="email"
                  value={profileForm.email}
                  onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                  style={{ width: '100%', padding: '10px', borderRadius: '10px', border: '1px solid #e2e8f0', fontSize: '14px' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>Mobile</label>
                <input
                  type="text"
                  value={profileForm.mobile}
                  onChange={(e) => setProfileForm({ ...profileForm, mobile: e.target.value })}
                  style={{ width: '100%', padding: '10px', borderRadius: '10px', border: '1px solid #e2e8f0', fontSize: '14px' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>New Password</label>
                <input
                  type="password"
                  value={profileForm.password}
                  onChange={(e) => setProfileForm({ ...profileForm, password: e.target.value })}
                  placeholder="Leave blank to keep current"
                  style={{ width: '100%', padding: '10px', borderRadius: '10px', border: '1px solid #e2e8f0', fontSize: '14px' }}
                />
              </div>
            </div>

            <div style={{ marginTop: '14px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setProfileForm((prev) => ({ ...prev, password: '' }))}
                style={{
                  padding: '10px 14px',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  background: '#f8fafc',
                  color: '#0f172a',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                Reset Password Field
              </button>
              <button
                onClick={handleProfileSave}
                disabled={profileSaving}
                style={{
                  padding: '10px 16px',
                  borderRadius: '10px',
                  border: 'none',
                  background: profileSaving ? '#94a3b8' : 'linear-gradient(135deg, #2563eb, #1d4ed8)',
                  color: 'white',
                  fontWeight: 800,
                  cursor: profileSaving ? 'not-allowed' : 'pointer',
                  boxShadow: '0 10px 20px rgba(37, 99, 235, 0.25)'
                }}
              >
                Save Profile
              </button>
            </div>
          </div>

          {renderTable('Users', snapshot.users, [
            { key: 'id', label: 'ID' },
            { key: 'username', label: 'Username' },
            { key: 'email', label: 'Email' },
            { key: 'is_admin', label: 'Admin' },
            { key: 'is_active', label: 'Active' },
            { key: 'is_email_verified', label: 'Email OK' },
            { key: 'is_mobile_verified', label: 'Mobile OK' },
            { key: 'created_at', label: 'Created' },
            {
              key: 'actions',
              label: 'Actions',
              render: (row) => (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => updateUser(row.id, { is_admin: !row.is_admin })}
                    disabled={updatingUserId === row.id}
                    style={{
                      padding: '6px 10px',
                      borderRadius: '8px',
                      border: 'none',
                      background: row.is_admin ? '#f59e0b' : '#0ea5e9',
                      color: 'white',
                      fontWeight: 700,
                      cursor: updatingUserId === row.id ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {row.is_admin ? 'Remove Admin' : 'Make Admin'}
                  </button>
                  <button
                    onClick={() => updateUser(row.id, { is_active: !row.is_active })}
                    disabled={updatingUserId === row.id}
                    style={{
                      padding: '6px 10px',
                      borderRadius: '8px',
                      border: 'none',
                      background: row.is_active ? '#ef4444' : '#22c55e',
                      color: 'white',
                      fontWeight: 700,
                      cursor: updatingUserId === row.id ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {row.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  {!row.is_email_verified || !row.is_mobile_verified ? (
                    <button
                      onClick={() => updateUser(row.id, { is_email_verified: true, is_mobile_verified: true })}
                      disabled={updatingUserId === row.id}
                      style={{
                        padding: '6px 10px',
                        borderRadius: '8px',
                        border: 'none',
                        background: '#22c55e',
                        color: 'white',
                        fontWeight: 700,
                        cursor: updatingUserId === row.id ? 'not-allowed' : 'pointer',
                      }}
                    >
                      Verify User
                    </button>
                  ) : null}
                </div>
              ),
            },
          ])}

          {renderTable('Broker Credentials', snapshot.brokers, [
            { key: 'id', label: 'ID' },
            { key: 'user_id', label: 'User' },
            { key: 'broker_name', label: 'Broker' },
            { key: 'is_active', label: 'Active' },
            { key: 'created_at', label: 'Created' },
            { key: 'updated_at', label: 'Updated' },
          ])}

          {renderTable('Orders', snapshot.orders, [
            { key: 'id', label: 'ID' },
            { key: 'user_id', label: 'User' },
            { key: 'broker_id', label: 'Broker' },
            { key: 'symbol', label: 'Symbol' },
            { key: 'side', label: 'Side' },
            { key: 'quantity', label: 'Qty' },
            { key: 'status', label: 'Status' },
            { key: 'created_at', label: 'Created' },
          ])}

          {renderTable('Positions', snapshot.positions, [
            { key: 'id', label: 'ID' },
            { key: 'user_id', label: 'User' },
            { key: 'broker_id', label: 'Broker' },
            { key: 'symbol', label: 'Symbol' },
            { key: 'quantity', label: 'Qty' },
            { key: 'pnl', label: 'PnL' },
            { key: 'updated_at', label: 'Updated' },
          ])}

          {renderTable('Strategies', snapshot.strategies, [
            { key: 'id', label: 'ID' },
            { key: 'user_id', label: 'User' },
            { key: 'name', label: 'Name' },
            { key: 'strategy_type', label: 'Type' },
            { key: 'status', label: 'Status' },
            { key: 'is_live', label: 'Live' },
            { key: 'created_at', label: 'Created' },
          ])}

          {renderTable('Backtests', snapshot.backtests, [
            { key: 'id', label: 'ID' },
            { key: 'strategy_id', label: 'Strategy' },
            { key: 'total_return', label: 'Return' },
            { key: 'sharpe_ratio', label: 'Sharpe' },
            { key: 'win_rate', label: 'Win %' },
            { key: 'created_at', label: 'Created' },
          ])}

          {renderTable('Trade Reports', snapshot.trade_reports, [
            { key: 'id', label: 'ID' },
            { key: 'symbol', label: 'Symbol' },
            { key: 'side', label: 'Side' },
            { key: 'quantity', label: 'Qty' },
            { key: 'pnl', label: 'PnL' },
            { key: 'pnl_percentage', label: 'PnL %' },
            { key: 'exit_time', label: 'Exit' },
          ])}

          {renderTable('Refresh Tokens', snapshot.refresh_tokens, [
            { key: 'id', label: 'ID' },
            { key: 'user_id', label: 'User' },
            { key: 'token', label: 'Token' },
            { key: 'expires_at', label: 'Expires' },
            { key: 'created_at', label: 'Created' },
          ])}
        </>
      )}
    </div>
  );
}

export default AdminPanel;
