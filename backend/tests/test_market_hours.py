import pytest
from datetime import datetime, time
from unittest.mock import patch
from app.core.market_hours import market_status


class TestMarketStatus:
    """Unit tests for market_status function"""

    @patch('app.core.market_hours._nse_market_open')
    def test_before_market_open(self, mock_nse):
        """Test status before 9:15 AM"""
        mock_nse.return_value = True  # Even if NSE open, should be closed before time
        test_time = datetime(2026, 3, 9, 8, 30, 0)  # 8:30 AM
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == False
        assert result["reason"] == "Before market open"
        assert result["current_time"] == "08:30"

    @patch('app.core.market_hours._nse_market_open')
    def test_after_market_close(self, mock_nse):
        """Test status after 3:30 PM"""
        mock_nse.return_value = True
        test_time = datetime(2026, 3, 9, 16, 0, 0)  # 4:00 PM
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == False
        assert result["reason"] == "After market close"
        assert result["current_time"] == "16:00"

    @patch('app.core.market_hours._nse_market_open')
    def test_during_market_hours_nse_open(self, mock_nse):
        """Test status during market hours when NSE is open"""
        mock_nse.return_value = True
        test_time = datetime(2026, 3, 9, 10, 30, 0)  # 10:30 AM
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == True
        assert result["reason"] == "Open (NSE status)"
        assert result["current_time"] == "10:30"

    @patch('app.core.market_hours._nse_market_open')
    def test_during_market_hours_nse_closed(self, mock_nse):
        """Test status during market hours when NSE is closed"""
        mock_nse.return_value = False
        test_time = datetime(2026, 3, 9, 10, 30, 0)  # 10:30 AM
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == False
        assert result["reason"] == "Closed (NSE status)"
        assert result["current_time"] == "10:30"

    @patch('app.core.market_hours._nse_market_open')
    def test_weekend_closed(self, mock_nse):
        """Test status on weekend"""
        mock_nse.return_value = None  # To test fallback logic
        # Saturday
        test_time = datetime(2026, 3, 8, 10, 30, 0)  # Saturday
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == False
        assert result["reason"] == "Weekend"

    @patch('app.core.market_hours._nse_market_open')
    @patch('app.core.market_hours.is_market_holiday')
    def test_market_holiday_closed(self, mock_holiday, mock_nse):
        """Test status on market holiday"""
        mock_nse.return_value = None
        mock_holiday.return_value = True
        test_time = datetime(2026, 3, 9, 10, 30, 0)  # Sunday or holiday
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == False
        assert result["reason"] == "Holiday"

    @patch('app.core.market_hours._nse_market_open')
    def test_at_market_open_time(self, mock_nse):
        """Test exactly at 9:15 AM"""
        mock_nse.return_value = True
        test_time = datetime(2026, 3, 9, 9, 15, 0)
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == True
        assert result["reason"] == "Open (NSE status)"

    @patch('app.core.market_hours._nse_market_open')
    def test_at_market_close_time(self, mock_nse):
        """Test exactly at 3:30 PM"""
        mock_nse.return_value = True
        test_time = datetime(2026, 3, 9, 15, 30, 0)
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == True
        assert result["reason"] == "Open (NSE status)"

    @patch('app.core.market_hours._nse_market_open')
    def test_one_minute_before_open(self, mock_nse):
        """Test 9:14 AM"""
        mock_nse.return_value = True
        test_time = datetime(2026, 3, 9, 9, 14, 0)
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == False
        assert result["reason"] == "Before market open"

    @patch('app.core.market_hours._nse_market_open')
    def test_one_minute_after_close(self, mock_nse):
        """Test 3:31 PM"""
        mock_nse.return_value = True
        test_time = datetime(2026, 3, 9, 15, 31, 0)
        result = market_status(time(9, 15), time(15, 30), test_time)

        assert result["is_open"] == False
        assert result["reason"] == "After market close"