# AlgoTrade Pro - Production Deployment Guide

## 🚀 Deployment Options

### Option 1: VPS Deployment (Recommended for Full Control)

#### Prerequisites
- Ubuntu 22.04 LTS server
- Domain name pointed to your server IP
- At least 2GB RAM, 2 CPU cores
- SSH access to server

#### Step 1: Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Install Git
sudo apt install git -y
```

#### Step 2: Clone Repository
```bash
git clone https://github.com/yourusername/algotrade-pro.git
cd algotrade-pro
```

#### Step 3: Configure Environment
```bash
# Copy production environment file
cp .env.production.example .env

# Edit with your actual values
nano .env
```

**IMPORTANT**: Update these values:
- `SECRET_KEY` - Generate: `openssl rand -hex 32`
- `ENCRYPTION_KEY` - Generate: `openssl rand -hex 16`
- `DATABASE_URL` - Your PostgreSQL connection string
- `CORS_ORIGINS` - Your domain(s)
- Broker API keys

#### Step 4: Setup SSL with Traefik
```bash
# Create traefik directory
mkdir -p traefik/logs
touch traefik/acme.json
chmod 600 traefik/acme.json

# Edit docker-compose.production.yml
# Replace:
# - yourdomain.com with your actual domain
# - your-email@example.com with your email
nano docker-compose.production.yml
```

#### Step 5: Deploy
```bash
# Build and start all services
docker compose -f docker-compose.production.yml up -d

# Check logs
docker compose -f docker-compose.production.yml logs -f

# Verify all containers are running
docker ps
```

#### Step 6: Database Setup
```bash
# Run migrations
docker exec algotrade_backend_prod alembic upgrade head

# Or manually connect and setup
docker exec -it algotrade_db_prod psql -U algotrade -d trading_db
```

---

### Option 2: Cloud Platforms

#### A. Deploy on Railway.app
1. Fork the repository
2. Connect to Railway
3. Add PostgreSQL database
4. Set environment variables
5. Deploy backend and frontend separately

#### B. Deploy on Render.com
1. Create account on Render
2. New Web Service → Connect repository
3. Add PostgreSQL database
4. Configure environment variables
5. Deploy

#### C. Deploy on DigitalOcean App Platform
1. Create new app
2. Connect GitHub repository
3. Configure components (backend + frontend)
4. Add managed database
5. Deploy

---

### Option 3: AWS Deployment

#### Using AWS EC2 + RDS
```bash
# 1. Launch EC2 instance (t3.medium recommended)
# 2. Create RDS PostgreSQL instance
# 3. Configure security groups
# 4. SSH into EC2 and follow VPS deployment steps
# 5. Use RDS endpoint in DATABASE_URL
```

#### Using AWS ECS/Fargate (Container-based)
1. Push Docker images to ECR
2. Create ECS cluster
3. Define task definitions
4. Create services
5. Setup ALB for routing
6. Configure Route53 for DNS

---

## 🔒 Security Checklist

- [ ] Change all default passwords
- [ ] Generate new SECRET_KEY and ENCRYPTION_KEY
- [ ] Enable HTTPS/SSL
- [ ] Setup firewall (ufw/firewalld)
- [ ] Configure CORS properly
- [ ] Enable rate limiting
- [ ] Setup database backups
- [ ] Use environment variables for secrets
- [ ] Enable Docker logging
- [ ] Setup monitoring (Grafana/Prometheus)
- [ ] Configure fail2ban for SSH

## 🔧 Post-Deployment

### Enable Firewall
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Setup Database Backups
```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec algotrade_db_prod pg_dump -U algotrade trading_db > /backups/backup_$DATE.sql
# Keep only last 7 days
find /backups -name "backup_*.sql" -mtime +7 -delete
EOF

chmod +x backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /path/to/backup.sh") | crontab -
```

### Monitoring
```bash
# View logs
docker compose -f docker-compose.production.yml logs -f backend
docker compose -f docker-compose.production.yml logs -f frontend

# Check resource usage
docker stats

# Monitor application
curl https://api.yourdomain.com/health
```

## 🌐 DNS Configuration

Point your domain to server IP:
```
A     @              -> YOUR_SERVER_IP
A     www            -> YOUR_SERVER_IP
A     api            -> YOUR_SERVER_IP
```

## 📊 Scaling

### Horizontal Scaling
```bash
# Scale backend workers
docker compose -f docker-compose.production.yml up -d --scale backend=3
```

### Load Balancer
Use Nginx or Traefik for load balancing multiple backend instances.

## 🆘 Troubleshooting

### Check container status
```bash
docker ps -a
docker logs algotrade_backend_prod
docker logs algotrade_frontend_prod
```

### Restart services
```bash
docker compose -f docker-compose.production.yml restart
```

### Database connection issues
```bash
# Check if database is accessible
docker exec -it algotrade_db_prod psql -U algotrade -d trading_db
```

### SSL issues
```bash
# Check Traefik logs
docker logs traefik

# Verify acme.json permissions
ls -l traefik/acme.json  # Should be 600
```

## 📝 Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| SECRET_KEY | JWT signing key | Random 64-char string |
| ENCRYPTION_KEY | Data encryption key | Random 32-char string |
| CORS_ORIGINS | Allowed origins | `https://yourdomain.com` |
| ZERODHA_API_KEY | Zerodha API credentials | Your API key |
| LOG_LEVEL | Logging level | `INFO` |

## 💰 Cost Estimates

### VPS Hosting
- **DigitalOcean**: $12-24/month (2GB RAM droplet)
- **Linode**: $12-24/month
- **Vultr**: $12-24/month
- **Hetzner**: €4-8/month (Europe)

### Cloud Platforms
- **Railway**: ~$20-30/month
- **Render**: ~$25-35/month
- **Heroku**: ~$25-50/month

### AWS
- **EC2 + RDS**: ~$30-60/month
- **ECS Fargate**: ~$40-80/month

## 🎯 Quick Start Commands

```bash
# Clone and deploy
git clone https://github.com/yourusername/algotrade-pro.git
cd algotrade-pro
cp .env.production.example .env
# Edit .env with your values
docker compose -f docker-compose.production.yml up -d

# Check status
docker ps
curl https://api.yourdomain.com/health

# View logs
docker compose -f docker-compose.production.yml logs -f
```

## 📞 Support

For deployment issues:
1. Check logs first
2. Review this guide
3. Check GitHub issues
4. Contact support

---

**Remember**: Never commit `.env` file or expose API keys!
