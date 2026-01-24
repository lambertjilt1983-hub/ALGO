#!/bin/bash
set -e

# Navigate to frontend and build
cd frontend
npm ci
npm run build

# Start nginx (for production)
exec nginx -g "daemon off;"
