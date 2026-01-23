# Free Domain & Hosting Options

## 🆓 Free Domain Options

### Option 1: Free Subdomains (Best for Testing)

#### 1. **Freenom** (Free .tk, .ml, .ga, .cf, .gq domains)
- Website: https://www.freenom.com
- Free for 12 months (renewable)
- Example: `algotrade.tk`, `algotrade.ml`
- ⚠️ Limited features, not great for production

**How to get:**
1. Go to Freenom.com
2. Search for available domain
3. Select `.tk`, `.ml`, `.ga`, `.cf`, or `.gq`
4. Register (free for 1 year)
5. Point to your server IP in DNS settings

---

### Option 2: Free Subdomains from Hosting Providers

#### **Railway.app** (Recommended)
- Provides: `yourapp.up.railway.app`
- Automatic SSL
- No configuration needed
- Best for quick deployment

#### **Render.com**
- Provides: `yourapp.onrender.com`
- Automatic SSL
- Free tier available

#### **Vercel**
- Provides: `yourapp.vercel.app`
- Automatic SSL
- Free for frontend

#### **Netlify**
- Provides: `yourapp.netlify.app`
- Automatic SSL
- Free tier

---

### Option 3: Dynamic DNS Services (For Testing)

#### **DuckDNS** (Recommended)
- Website: https://www.duckdns.org
- Provides: `yourname.duckdns.org`
- Free forever
- Easy to setup

**Setup:**
```bash
# 1. Go to duckdns.org
# 2. Login with GitHub/Google
# 3. Create subdomain (e.g., algotrade)
# 4. Get your token
# 5. Update IP automatically or manually

# Auto-update IP (Linux)
echo "echo url=\"https://www.duckdns.org/update?domains=yourname&token=yourtoken&ip=\" | curl -k -o ~/duckdns/duck.log -K -" > duck.sh
chmod +x duck.sh
./duck.sh
```

#### **No-IP**
- Provides: `yourname.ddns.net`
- Free tier available
- Need to confirm every 30 days

---

### Option 4: Tunneling Services (For Development/Testing)

#### **ngrok** (Best for local testing)
```bash
# Install ngrok
# Download from: https://ngrok.com

# Run your backend
# In another terminal:
ngrok http 8000

# You'll get: https://random-id.ngrok-free.app
# Use this URL for testing
```

**Free tier**: 
- Random URL each time
- 40 connections/min
- Perfect for development

#### **Cloudflare Tunnel**
```bash
# Install cloudflared
# Windows: Download from cloudflare.com
# Linux: apt install cloudflared

# Run tunnel
cloudflared tunnel --url http://localhost:8000

# You'll get: https://random.trycloudflare.com
```

**Free tier**:
- Unlimited
- Random URL
- Good for testing

#### **LocalTunnel**
```bash
npm install -g localtunnel

# Run your app, then:
lt --port 8000

# You'll get: https://random.loca.lt
```

---

### Option 5: Free Custom Domain (Limited Time)

#### **GitHub Student Pack**
If you're a student:
- Free domain from Namecheap (.me domain)
- Website: https://education.github.com/pack
- Valid for 1 year

#### **InfinityFree Hosting**
- Free subdomain with hosting
- Website: https://infinityfree.net
- Limited resources

---

## 🎯 Recommended Setup for Your AlgoTrade App

### **For Testing/Development:**
```bash
# Option 1: Use ngrok (Easiest)
ngrok http 8000
# Backend: https://xyz.ngrok-free.app
# Update frontend API_URL to ngrok URL

# Option 2: Use Railway (Best for cloud)
# Deploy to Railway
# Get: https://algotrade.up.railway.app
# Free $5 credit/month
```

### **For Production (Free Options):**

#### **Best Free Setup:**
1. **Backend**: Railway.app (Free $5/month credit)
2. **Frontend**: Vercel (Unlimited free)
3. **Domain**: DuckDNS (Free subdomain)

**Steps:**
```bash
# 1. Deploy backend to Railway
# Get URL: https://algotrade-api.up.railway.app

# 2. Deploy frontend to Vercel
cd frontend
vercel --prod
# Get URL: https://algotrade.vercel.app

# 3. (Optional) Setup custom domain with DuckDNS
# Point algotrade.duckdns.org to Vercel
```

---

## 💡 Update Your .env File

### For ngrok (Development):
```env
CORS_ORIGINS=https://your-ngrok-url.ngrok-free.app
FRONTEND_URL=https://your-ngrok-url.ngrok-free.app
BACKEND_URL=https://your-backend-ngrok.ngrok-free.app
```

### For Railway + Vercel:
```env
CORS_ORIGINS=https://algotrade.vercel.app,https://algotrade.up.railway.app
FRONTEND_URL=https://algotrade.vercel.app
BACKEND_URL=https://algotrade-api.up.railway.app
```

### For DuckDNS:
```env
CORS_ORIGINS=https://algotrade.duckdns.org
FRONTEND_URL=https://algotrade.duckdns.org
BACKEND_URL=https://api.algotrade.duckdns.org
```

---

## 🚀 Quick Deploy Without Domain

### Railway (Simplest - Recommended)

1. **Go to**: https://railway.app
2. **Sign up** with GitHub
3. **Click**: "New Project" → "Deploy from GitHub repo"
4. **Select**: Your AlgoTrade repository
5. **Add**: PostgreSQL from marketplace
6. **Set environment variables** in Railway dashboard
7. **Done!** You get: `https://yourapp.up.railway.app`

**Frontend:**
1. Create another service
2. Point to `frontend` folder
3. Deploy
4. Get: `https://frontend.up.railway.app`

**Total cost**: FREE (includes $5 monthly credit)

---

### Render (Alternative)

1. **Go to**: https://render.com
2. **Sign up** with GitHub
3. **New** → "Web Service"
4. **Connect**: Your repository
5. **Add**: PostgreSQL database (free tier)
6. **Deploy**
7. Get: `https://algotrade.onrender.com`

**Total cost**: FREE tier available

---

## 📊 Comparison

| Option | Cost | Custom Domain | SSL | Best For |
|--------|------|---------------|-----|----------|
| Freenom | Free | Yes (.tk, .ml) | Manual | Testing |
| DuckDNS | Free | Yes (subdomain) | Manual | Personal |
| Railway | Free $5/mo | Optional | Auto | Production |
| Vercel | Free | Optional | Auto | Frontend |
| ngrok | Free | No | Auto | Dev/Testing |
| Cloudflare Tunnel | Free | No | Auto | Dev/Testing |

---

## ✅ Recommended Path

**For immediate testing:**
```bash
# Use ngrok - 2 minutes setup
ngrok http 8000
```

**For free production deployment:**
```bash
# Use Railway - 15 minutes setup
# 1. Push code to GitHub
# 2. Connect to Railway
# 3. Deploy
# 4. Get free HTTPS URL
```

**For custom domain later:**
- Buy domain ($10-15/year) from Namecheap, GoDaddy
- Point to Railway/Vercel
- Done!

---

## 🎁 Pro Tip

Start with **Railway + Vercel** (completely free):
- Deploy backend to Railway
- Deploy frontend to Vercel
- Both get free SSL
- Both get free URLs
- Total cost: $0/month for small projects
- Can add custom domain later when needed

You don't need to buy a domain to start using your app online!
