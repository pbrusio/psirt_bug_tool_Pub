# PSIRT Analysis API Backend

FastAPI backend for PSIRT vulnerability analysis and device verification.

## Architecture

```
┌─────────────────────────────────────────┐
│         Frontend (React + Vite)         │
│  - User interface for PSIRT analysis    │
│  - Device verification forms            │
└─────────────────────────────────────────┘
                    ↕ HTTP/REST
┌─────────────────────────────────────────┐
│         Backend API (FastAPI)           │
│  - /api/v1/analyze-psirt                │
│  - /api/v1/verify-device                │
│  - /api/v1/results/{id}                 │
└─────────────────────────────────────────┘
                    ↕ Function Calls
┌─────────────────────────────────────────┐
│      Existing Python Backend            │
│  - SEC-8B inference (predict_and_verify)│
│  - Device verification (device_verifier)│
│  - FAISS retrieval (fewshot_inference)  │
└─────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

Dependencies are also installed in the main project venv.

### 2. Start the Server

```bash
./run_server.sh
```

Or manually:

```bash
cd ..
source venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs (Swagger UI)
- **Health**: http://localhost:8000/api/v1/health

### 3. Test the API

```bash
python backend/test_api.py
```

Or use curl:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Analyze PSIRT
curl -X POST http://localhost:8000/api/v1/analyze-psirt \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "A vulnerability in the IOx application hosting...",
    "platform": "IOS-XE",
    "advisory_id": "cisco-sa-iox-dos-95Fqnf7b"
  }'
```

## API Endpoints

### POST /api/v1/analyze-psirt

Analyze PSIRT with SEC-8B and return predicted labels.

**Request:**
```json
{
  "summary": "PSIRT summary text",
  "platform": "IOS-XE",
  "advisory_id": "cisco-sa-xxx" (optional)
}
```

**Response:**
```json
{
  "analysis_id": "uuid",
  "predicted_labels": ["APP_IOx", "SEC_CoPP"],
  "confidence": 0.93,
  "config_regex": ["^iox$", "^control-plane"],
  "show_commands": ["show iox", "show policy-map control-plane"],
  "timestamp": "2025-10-06T14:30:00Z"
}
```

### POST /api/v1/verify-device

Verify device against PSIRT analysis.

**Request:**
```json
{
  "analysis_id": "uuid-from-previous-call",
  "device": {
    "host": "192.168.0.33",
    "username": "admin",
    "password": "Pa22word",
    "device_type": "cisco_ios"
  },
  "psirt_metadata": {
    "product_names": ["Cisco IOS XE Software, Version 17.3.1"],
    "bug_id": "cisco-sa-iox-dos-95Fqnf7b"
  }
}
```

**Response:**
```json
{
  "verification_id": "uuid",
  "device_hostname": "C9200L-Switch",
  "device_version": "17.03.05",
  "version_check": {
    "affected": true,
    "reason": "Version in affected range"
  },
  "feature_check": {
    "present": ["SEC_CoPP"],
    "absent": ["APP_IOx"]
  },
  "overall_status": "NOT VULNERABLE",
  "reason": "Version affected but IOx not configured",
  "evidence": {...}
}
```

### GET /api/v1/results/{analysis_id}

Retrieve cached analysis result.

### GET /api/v1/health

Health check endpoint.

## Project Structure

```
backend/
├── app.py                  # Main FastAPI application
├── api/
│   ├── __init__.py
│   ├── routes.py          # API endpoints
│   └── models.py          # Pydantic models
├── core/
│   ├── __init__.py
│   ├── config.py          # Configuration
│   ├── sec8b.py           # SEC-8B wrapper
│   └── verifier.py        # Device verification wrapper
├── db/
│   ├── __init__.py
│   └── cache.py           # Results cache (in-memory)
├── requirements.txt
├── run_server.sh
├── test_api.py
└── README.md
```

## Configuration

Edit `backend/core/config.py` to customize:

- **Model**: SEC-8B model name and quantization
- **Paths**: FAISS index, feature files
- **API**: Rate limits, timeouts
- **Cache**: Expiry time

## Development

### Running in Development Mode

The server runs in reload mode by default (auto-restart on code changes).

### API Documentation

FastAPI automatically generates interactive API docs:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Logging

Logs are printed to console. Configure logging in `app.py`.

## Production Deployment

### Docker (Recommended)

Create `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Expose port
EXPOSE 8000

# Run server
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t psirt-api .
docker run -p 8000:8000 -v $(pwd)/models:/app/models psirt-api
```

### Docker Compose

See `docker-compose.yml` in project root for full stack deployment.

## Testing

### Unit Tests

```bash
pytest backend/tests/
```

### Integration Tests

```bash
python backend/test_api.py
```

### Manual Testing

Use the interactive docs at http://localhost:8000/docs

## Security

### Authentication & Authorization
- **API Key Auth**: Write operations (POST/PUT/DELETE) require `X-ADMIN-KEY` header (when `DEV_MODE=false`)
- **Credentials**: SSH passwords are never logged
- **Host Validation**: Device host fields are validated (IPv4, IPv6, FQDN only)

### Rate Limiting
Built-in sliding window rate limiter (per IP):
- **Default**: 100 requests/minute
- **Analyze PSIRT**: 30 requests/minute
- **Verify Device**: 20 requests/minute
- **Scan Device**: 60 requests/minute

Configure via environment variables:
```bash
export RATE_LIMIT_DEFAULT=100
export RATE_LIMIT_ANALYZE=30
export RATE_LIMIT_VERIFY=20
export RATE_LIMIT_SCAN=60
export RATE_LIMIT_WINDOW=60  # seconds
```

### CORS Configuration
Configure allowed origins via environment variable:
```bash
export ALLOWED_ORIGINS="https://your-domain.com,https://app.example.com"
```

### HTTPS / TLS (Production Required)

**⚠️ IMPORTANT: Never expose HTTP directly in production.**

The backend runs HTTP on port 8000 for local development. For production, **always** use a TLS-terminating reverse proxy:

**Option 1: Nginx**
```nginx
server {
    listen 443 ssl;
    server_name psirt.example.com;

    ssl_certificate /etc/ssl/certs/psirt.crt;
    ssl_certificate_key /etc/ssl/private/psirt.key;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Option 2: Traefik**
```yaml
http:
  routers:
    psirt:
      rule: "Host(`psirt.example.com`)"
      service: psirt
      tls:
        certResolver: letsencrypt

  services:
    psirt:
      loadBalancer:
        servers:
          - url: "http://localhost:8000"
```

**Option 3: Cloud Run / App Engine**
- Deploy behind GCP's built-in HTTPS termination
- Set `ALLOWED_ORIGINS` to your frontend domain

### Security Checklist for Production
- [ ] Set `DEV_MODE=false`
- [ ] Configure `ADMIN_API_KEY` for write operations
- [ ] Set `ALLOWED_ORIGINS` to specific domains (not `*`)
- [ ] Deploy behind TLS-terminating reverse proxy
- [ ] Disable direct HTTP exposure of `run_server.sh`
- [ ] Review rate limits for your use case

## Troubleshoremove_api.py`:

**Error: "Cannot connect to API"**
- Make sure server is running: `./backend/run_server.sh`

**Error: "Analysis ID not found"**
- Analysis results expire after 24 hours
- Make sure you use the ID from `/analyze-psirt` response

**Error: "SSH connection failed"**
- Verify device IP and credentials
- Check network connectivity
- Ensure device allows SSH

**Error: "Module not found"**
- Activate venv: `source venv/bin/activate`
- Install dependencies: `pip install -r backend/requirements.txt`

## Status

✅ **Backend Complete and Tested**
- SEC-8B integration working with GPT-4o corrected labels
- FAISS retrieval working (145 examples)
- Device verification tested on C9200L
- Full E2E test passing (analyze → verify)

## Next Steps

1. ✅ Backend API implemented
2. ✅ GPT-4o label filtering (145 examples)
3. ✅ APP_IOx taxonomy addition
4. 🔲 Frontend React app
5. 🔲 Export functionality (PDF, JSON, CSV)
6. 🔲 Credential encryption
7. 🔲 Docker deployment
8. 🔲 Authentication

See `FRONTEND_DESIGN.md` for full implementation plan.
