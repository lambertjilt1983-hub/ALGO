import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import config from '../config/api';

const API_URL = config.API_BASE_URL;

export default function ZerodhaCallbackPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const request_token = params.get('request_token');
    const status = params.get('status');
    if (!request_token || status !== 'success') {
      toast.error('Zerodha login failed or cancelled.');
      navigate('/brokers');
      return;
    }
    const access_token = localStorage.getItem('access_token');
    if (!access_token) {
      toast.error('User not authenticated. Please login.');
      navigate('/login');
      return;
    }
    // Call backend to exchange request_token for access_token
    axios.get(`${API_URL}/brokers/zerodha/callback`, {
      params: { request_token, status },
      headers: { Authorization: `Bearer ${access_token}` },
    })
      .then(res => {
        if (res.data.status === 'success') {
          toast.success('Zerodha connected successfully!');
        } else {
          toast.error(res.data.message || 'Failed to connect Zerodha.');
        }
        navigate('/brokers');
      })
      .catch(() => {
        toast.error('Failed to complete Zerodha login.');
        navigate('/brokers');
      });
  }, [navigate]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <div className="text-xl font-bold mb-4">Completing Zerodha login...</div>
      <div className="text-gray-600">Please wait, do not close this window.</div>
    </div>
  );
}
