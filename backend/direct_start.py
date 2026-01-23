# Direct server start without any cache
import sys
sys.dont_write_bytecode = True

if __name__ == '__main__':
    # Set path
    sys.path.insert(0, r'F:\ALGO\backend')

    # Import and check
    print("=" * 60)
    print("VERIFYING SOURCE CODE VALUES...")
    print("=" * 60)

    # Read source file
    with open(r'F:\ALGO\backend\app\routes\auto_trading_simple.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if '25157.50' in content:
            print("✓ Source file contains CORRECT value: 25157.50")
        else:
            print("✗ Source file MISSING correct value!")

    print("\nStarting server...")
    print("=" * 60)

    # Now start uvicorn
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
