from app.engine.option_signal_generator import _build_scan_symbol_universe


def _make_nfo_option(name: str) -> dict:
    return {
        "segment": "NFO-OPT",
        "name": name,
    }


def test_build_scan_symbol_universe_caps_total_stocks():
    instruments = [
        _make_nfo_option("RELIANCE"),
        _make_nfo_option("RELIANCE"),
        _make_nfo_option("SBIN"),
        _make_nfo_option("SBIN"),
        _make_nfo_option("TCS"),
        _make_nfo_option("TCS"),
        _make_nfo_option("INFY"),
        _make_nfo_option("INFY"),
    ]

    selected = _build_scan_symbol_universe(
        include_nifty50=True,
        include_fno_universe=True,
        max_symbols=2,
        instruments_nfo=instruments,
    )

    # First 4 are fixed index roots.
    assert selected[:4] == ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
    # Cap applies to stocks combined (NIFTY50 + F&O stock universe).
    assert len(selected) == 6


def test_build_scan_symbol_universe_without_stock_flags_returns_only_indices():
    selected = _build_scan_symbol_universe(
        include_nifty50=False,
        include_fno_universe=False,
        max_symbols=40,
        instruments_nfo=[],
    )
    assert selected == ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
