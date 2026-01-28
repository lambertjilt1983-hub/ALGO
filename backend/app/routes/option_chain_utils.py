from app.brokers.zerodha import ZerodhaKite

async def get_option_chain(symbol: str, expiry: str):
    """
    Fetch the full CE/PE option chain for a given index and expiry.
    Returns a dict with 'CE' and 'PE' lists of instruments.
    """
    kite = ZerodhaKite()  # You may need to pass credentials/session here
    instruments = await kite.get_instruments()
    ce_options = [inst for inst in instruments if inst['name'] == symbol and inst['expiry'] == expiry and inst['instrument_type'] == 'CE']
    pe_options = [inst for inst in instruments if inst['name'] == symbol and inst['expiry'] == expiry and inst['instrument_type'] == 'PE']
    return {'CE': ce_options, 'PE': pe_options}
