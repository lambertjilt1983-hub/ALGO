#!/usr/bin/env python
"""Simple test to check if backend can handle requests"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/test")
async def test():
    """Test endpoint"""
    return {"message": "working"}

if __name__ == "__main__":
    import uvicorn
    print("Starting test server on port 8004...")
    uvicorn.run(app, host="0.0.0.0", port=8004, log_level="debug")
