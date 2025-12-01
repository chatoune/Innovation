# Quickstart Guide: Client/Server Application Platform

**Branch**: `001-architecture-docs` | **Date**: 2025-12-01

## Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- PostgreSQL 14+
- Git

## Project Setup

### 1. Clone and Setup Environment

```bash
# Clone repository
git clone <repository-url>
cd Innovation

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your database credentials
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/innovation
# SECRET_KEY=your-secret-key-here
# CORS_ORIGINS=http://localhost:5173
```

### 3. Database Setup

```bash
# Create database
createdb innovation

# Run migrations
alembic upgrade head

# Seed initial data (admin user, roles, permissions)
python -m src.db.seed
```

### 4. Frontend Setup

```bash
# Navigate to frontend
cd ../frontend

# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Edit .env
# VITE_API_URL=http://localhost:8000/api/v1
```

## Running the Application

### Start Backend

```bash
cd backend
uvicorn src.main:app --reload --port 8000
```

Backend will be available at:
- API: http://localhost:8000/api/v1
- Docs: http://localhost:8000/docs (Swagger UI)
- ReDoc: http://localhost:8000/redoc

### Start Frontend

```bash
cd frontend
npm run dev
```

Frontend will be available at: http://localhost:5173

## Default Credentials

After seeding the database:

| Email | Password | Role |
|-------|----------|------|
| admin@example.com | Admin123! | Administrator |

**Important**: Change the admin password immediately in production!

## Development Workflow

### Backend Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src

# Format code
black src tests
isort src tests

# Type checking
mypy src

# Create new migration
alembic revision --autogenerate -m "description"
```

### Frontend Development

```bash
# Run tests
npm test

# Run tests in watch mode
npm run test:watch

# Lint code
npm run lint

# Format code
npm run format

# Type checking
npm run typecheck

# Build for production
npm run build
```

## Project Structure Overview

```
Innovation/
├── backend/
│   ├── src/
│   │   ├── api/           # FastAPI routes
│   │   ├── core/          # Config, security
│   │   ├── db/            # Database setup
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   └── main.py        # App entry point
│   ├── tests/
│   ├── alembic/           # Migrations
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── pages/         # Route pages
│   │   ├── services/      # API client
│   │   ├── stores/        # State management
│   │   └── main.tsx       # App entry point
│   ├── tests/
│   └── package.json
│
└── specs/                 # Feature specifications
```

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/login | Email/password login |
| POST | /auth/webauthn/login/options | Get FIDO2 login challenge |
| POST | /auth/webauthn/login/verify | Complete FIDO2 login |
| GET | /auth/me | Get current user + permissions |
| GET | /users | List users (paginated) |
| POST | /users | Create user |
| GET | /roles | List roles |
| POST | /roles | Create role |
| GET | /modules | Get navigation for current user |
| POST | /import | Upload Excel file |
| GET | /import/jobs/{id} | Check import status |
| GET | /audit | Query audit logs |

Full API documentation available at `/docs` when backend is running.

## Configuration Reference

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | required |
| SECRET_KEY | JWT signing key | required |
| ACCESS_TOKEN_EXPIRE_MINUTES | Token lifetime | 30 |
| CORS_ORIGINS | Allowed origins (comma-separated) | required |
| LOG_LEVEL | Logging level | INFO |

### Frontend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| VITE_API_URL | Backend API base URL | required |

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
pg_isready

# Check connection string format
# postgresql+asyncpg://user:password@host:port/database
```

### CORS Errors

Ensure `CORS_ORIGINS` in backend `.env` includes the frontend URL:
```
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Migration Conflicts

```bash
# Reset migrations (development only!)
alembic downgrade base
alembic upgrade head
```

### WebAuthn/FIDO2 Issues

- FIDO2 requires HTTPS in production
- For local development, use localhost (browsers allow WebAuthn on localhost)
- Ensure browser supports WebAuthn (Chrome 67+, Firefox 60+, Safari 13+)
