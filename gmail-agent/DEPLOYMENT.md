# Deployment Guide

Panduan untuk deploy Gmail Agent ke production.

## 🚀 Deployment Options

### 1. Docker Deployment

#### Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY server/ ./server/
COPY .env .env

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "server.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Build and Run

```bash
# Build image
docker build -t gmail-agent .

# Run container
docker run -p 8000:8000 --env-file .env gmail-agent
```

### 2. Cloud Deployment

#### Heroku

```bash
# Install Heroku CLI
# Create Procfile
echo "web: uvicorn server.api:app --host 0.0.0.0 --port \$PORT" > Procfile

# Deploy
heroku create gmail-agent-app
heroku config:set COMPOSIO_API_KEY=your-key
heroku config:set GROQ_API_KEY=your-key
git push heroku main
```

#### AWS Lambda (with Mangum)

```python
# Add to requirements.txt
mangum==0.17.0

# Update api.py
from mangum import Mangum

app = create_app()
handler = Mangum(app)
```

#### Google Cloud Run

```bash
# Build and deploy
gcloud run deploy gmail-agent \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### 3. VPS Deployment (Ubuntu)

```bash
# Install dependencies
sudo apt update
sudo apt install python3-pip python3-venv nginx

# Clone repository
git clone your-repo
cd gmail-agent

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Setup systemd service
sudo nano /etc/systemd/system/gmail-agent.service
```

**Service file:**
```ini
[Unit]
Description=Gmail Agent API
After=network.target

[Service]
User=your-user
WorkingDirectory=/path/to/gmail-agent
Environment="PATH=/path/to/gmail-agent/.venv/bin"
EnvironmentFile=/path/to/gmail-agent/.env
ExecStart=/path/to/gmail-agent/.venv/bin/uvicorn server.api:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

```bash
# Start service
sudo systemctl daemon-reload
sudo systemctl start gmail-agent
sudo systemctl enable gmail-agent
```

**Nginx configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🔐 Security Best Practices

### 1. Environment Variables

Never commit `.env` file. Use environment variables or secrets management:

```bash
# AWS Secrets Manager
aws secretsmanager create-secret --name gmail-agent/composio-key

# Kubernetes Secrets
kubectl create secret generic gmail-agent-secrets \
  --from-literal=COMPOSIO_API_KEY=your-key \
  --from-literal=GROQ_API_KEY=your-key
```

### 2. API Authentication

Add authentication middleware:

```python
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != os.getenv("API_TOKEN"):
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials

# Use in endpoints
@app.post("/agent")
def run_agent(token: str = Depends(verify_token)):
    # ...
```

### 3. Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/agent")
@limiter.limit("10/minute")
def run_agent(request: Request):
    # ...
```

### 4. CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📊 Monitoring

### 1. Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@app.post("/agent")
def run_agent(request: RunGmailAgentRequest):
    logger.info(f"Agent request from user: {request.user_id}")
    # ...
```

### 2. Health Checks

```python
@app.get("/health")
def health_check():
    # Check dependencies
    try:
        composio_client.connected_accounts.list(limit=1)
        return {"status": "healthy", "composio": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### 3. Metrics

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

## 🔄 CI/CD Pipeline

### GitHub Actions

```yaml
name: Deploy Gmail Agent

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run tests
        run: |
          pytest
      
      - name: Deploy to production
        run: |
          # Your deployment script
```

## 📈 Scaling

### Horizontal Scaling

```bash
# Docker Compose
version: '3.8'
services:
  gmail-agent:
    image: gmail-agent
    deploy:
      replicas: 3
    ports:
      - "8000-8002:8000"
```

### Load Balancing

```nginx
upstream gmail_agent {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}

server {
    location / {
        proxy_pass http://gmail_agent;
    }
}
```

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   lsof -ti:8000 | xargs kill -9
   ```

2. **Permission denied**
   ```bash
   sudo chown -R $USER:$USER /path/to/gmail-agent
   ```

3. **Module not found**
   ```bash
   pip install -r requirements.txt --force-reinstall
   ```

## 📚 Additional Resources

- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Composio Production Guide](https://docs.composio.dev/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
