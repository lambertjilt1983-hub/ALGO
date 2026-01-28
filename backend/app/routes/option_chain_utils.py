from app.brokers.zerodha import ZerodhaKite

async def get_option_chain(symbol: str, expiry: str, api_key: str, api_secret: str, access_token: str):
    """
    Fetch the full CE/PE option chain for a given index and expiry using provided credentials.
    Returns a dict with 'CE' and 'PE' lists of instruments.
    """
    import sys
    kite = ZerodhaKite(api_key, api_secret, access_token)
    instruments = await kite.get_instruments()
    if not instruments or not isinstance(instruments, list):
        print(f"[OPTION_CHAIN_UTILS] No instruments returned for {symbol} {expiry}", file=sys.stderr)
        return {'CE': [], 'PE': [], 'error': 'No instruments returned'}

    ce_options = []
    pe_options = []
    for inst in instruments:
        # Defensive: log and skip if any key is missing or None
        if inst is None:
            print(f"[OPTION_CHAIN_UTILS] Skipping None instrument for {symbol} {expiry}", file=sys.stderr)
            continue
        name = inst.get('name')
        inst_expiry = inst.get('expiry')
        inst_type = inst.get('instrument_type')
        if name is None or inst_expiry is None or inst_type is None:
            print(f"[OPTION_CHAIN_UTILS] Skipping instrument with missing fields: {inst}", file=sys.stderr)
            continue
        if name == symbol and inst_expiry == expiry and inst_type == 'CE':
            ce_options.append(inst)
        if name == symbol and inst_expiry == expiry and inst_type == 'PE':
            pe_options.append(inst)
    print(f"[OPTION_CHAIN_UTILS] {symbol} {expiry} CE count: {len(ce_options)}, PE count: {len(pe_options)}")
    return {'CE': ce_options, 'PE': pe_options}
