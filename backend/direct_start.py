# Direct server start without any cache
import sys
sys.dont_write_bytecode = True

if __name__ == '__main__':
    # Set path
    sys.path.insert(0, r'F:\ALGO\backend')

    # Import and check
        import logging
        logging.basicConfig(level=logging.INFO)
        logging.info("=" * 60)
        logging.info("VERIFYING SOURCE CODE VALUES...")
        logging.info("=" * 60)

    # Read source file
    with open(r'F:\ALGO\backend\app\routes\auto_trading_simple.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if '25157.50' in content:
              logging.info("✓ Source file contains CORRECT value: 25157.50")
        else:
              logging.warning("✗ Source file MISSING correct value!")

    print("\nStarting server...")
        logging.info("\nStarting server...")
        logging.info("=" * 60)

    # Now start uvicorn
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
