from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.engine import paper_trade_updater as updater
from app.models.trading import PaperTrade
from app.routes import paper_trading as ptr


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return Session()


def test_paper_trade_open_manual_exit_and_history_visibility(monkeypatch):
    db = _make_session()
    try:
        monkeypatch.setattr(
            ptr,
            "market_status",
            lambda *_args, **_kwargs: {"is_open": True, "reason": "open", "current_time": "10:00"},
        )

        create_res = ptr.create_paper_trade(
            ptr.PaperTradeCreate(
                symbol="NFO:NIFTY26MAR22500CE",
                side="BUY",
                quantity=10,
                entry_price=100.0,
                stop_loss=95.0,
                target=110.0,
            ),
            db,
        )

        assert create_res["success"] is True
        trade_id = create_res["trade_id"]

        active_before = ptr.get_active_paper_trades(db)
        assert len(active_before["trades"]) == 1
        assert active_before["trades"][0]["id"] == trade_id

        close_res = ptr.update_paper_trade(
            trade_id,
            ptr.PaperTradeUpdate(status="MANUAL_CLOSE"),
            db,
        )
        assert close_res["success"] is True
        assert close_res["trade"]["status"] == "MANUAL_CLOSE"

        active_after = ptr.get_active_paper_trades(db)
        assert len(active_after["trades"]) == 0

        history = ptr.get_paper_trade_history(days=7, limit=50, db=db)
        assert len(history["trades"]) == 1
        assert history["trades"][0]["status"] == "MANUAL_CLOSE"
    finally:
        db.close()


def test_paper_update_prices_handles_multiple_open_trades(monkeypatch):
    db = _make_session()
    try:
        t1 = PaperTrade(
            user_id=1,
            symbol="NFO:NIFTY26MAR22500CE",
            side="BUY",
            quantity=1,
            entry_price=100.0,
            current_price=100.0,
            stop_loss=95.0,
            target=110.0,
            status="OPEN",
            trading_date=date.today(),
        )
        t2 = PaperTrade(
            user_id=1,
            symbol="NFO:BANKNIFTY26MAR50000CE",
            side="BUY",
            quantity=1,
            entry_price=200.0,
            current_price=200.0,
            stop_loss=180.0,
            target=220.0,
            status="OPEN",
            trading_date=date.today(),
        )
        db.add_all([t1, t2])
        db.commit()
        db.refresh(t1)
        db.refresh(t2)

        class _FakeKite:
            def ltp(self, symbols):
                return {
                    "NFO:NIFTY26MAR22500CE": {"last_price": 112.0},
                    "NFO:BANKNIFTY26MAR50000CE": {"last_price": 205.0},
                }

        monkeypatch.setattr(updater, "_get_kite", lambda: _FakeKite())
        monkeypatch.setattr(updater, "_price_update_cache", {"last_update": 0.0, "min_interval": 0.0})

        result = updater.update_open_paper_trades(db, force=True)

        assert result["success"] is True
        assert result["updated_count"] == 2
        assert result["closed_count"] == 1

        rows = db.query(PaperTrade).order_by(PaperTrade.id.asc()).all()
        assert rows[0].status == "TARGET_HIT"
        assert rows[0].exit_time is not None
        assert rows[1].status == "OPEN"
        assert rows[1].current_price == 205.0
    finally:
        db.close()


def test_paper_update_trade_price_target_hit():
    db = _make_session()
    try:
        trade = PaperTrade(
            user_id=1,
            symbol="NFO:NIFTY26MAR22500CE",
            side="BUY",
            quantity=1,
            entry_price=100.0,
            current_price=100.0,
            stop_loss=95.0,
            target=110.0,
            status="OPEN",
            trading_date=date.today(),
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        result = ptr.update_paper_trade(
            trade.id,
            ptr.PaperTradeUpdate(current_price=112.0),
            db,
        )

        assert result["success"] is True
        assert result["trade"]["status"] == "TARGET_HIT"

        row = db.query(PaperTrade).filter(PaperTrade.id == trade.id).first()
        assert row.status == "TARGET_HIT"
        assert row.exit_time is not None
    finally:
        db.close()


def test_paper_update_trade_price_stop_loss_hit():
    db = _make_session()
    try:
        trade = PaperTrade(
            user_id=1,
            symbol="NFO:BANKNIFTY26MAR50000CE",
            side="BUY",
            quantity=1,
            entry_price=200.0,
            current_price=200.0,
            stop_loss=190.0,
            target=220.0,
            status="OPEN",
            trading_date=date.today(),
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        result = ptr.update_paper_trade(
            trade.id,
            ptr.PaperTradeUpdate(current_price=188.0),
            db,
        )

        assert result["success"] is True
        assert result["trade"]["status"] == "SL_HIT"

        row = db.query(PaperTrade).filter(PaperTrade.id == trade.id).first()
        assert row.status == "SL_HIT"
        assert row.exit_time is not None
    finally:
        db.close()


def test_paper_updater_breakeven_trail_then_sl_hit(monkeypatch):
    db = _make_session()
    try:
        trade = PaperTrade(
            user_id=1,
            symbol="NFO:NIFTY26MAR22500CE",
            side="BUY",
            quantity=1,
            entry_price=100.0,
            current_price=100.0,
            stop_loss=95.0,
            target=110.0,
            status="OPEN",
            trading_date=date.today(),
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        class _SequencedKite:
            def __init__(self):
                self.calls = 0

            def ltp(self, symbols):
                self.calls += 1
                if self.calls == 1:
                    return {"NFO:NIFTY26MAR22500CE": {"last_price": 106.0}}  # 50% to target -> breakeven SL
                return {"NFO:NIFTY26MAR22500CE": {"last_price": 99.0}}  # back below breakeven -> SL_HIT

        kite = _SequencedKite()
        monkeypatch.setattr(updater, "_get_kite", lambda: kite)
        monkeypatch.setattr(updater, "_price_update_cache", {"last_update": 0.0, "min_interval": 0.0})

        first = updater.update_open_paper_trades(db, force=True)
        assert first["success"] is True

        row_after_first = db.query(PaperTrade).filter(PaperTrade.id == trade.id).first()
        assert row_after_first.status == "OPEN"
        assert row_after_first.stop_loss == 100.0

        second = updater.update_open_paper_trades(db, force=True)
        assert second["success"] is True

        row_after_second = db.query(PaperTrade).filter(PaperTrade.id == trade.id).first()
        assert row_after_second.status == "SL_HIT"
        assert row_after_second.exit_price == 100.0
        assert row_after_second.exit_time is not None
    finally:
        db.close()
