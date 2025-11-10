# Astrology API

FastAPI-based astrology calculation service with Supabase authentication.

## Features

- 🔐 **Supabase Authentication** - Secure JWT-based auth for all astrology endpoints
- 📊 **Birth Chart Analysis** - Complete natal chart calculations
- 🔮 **Aspects** - Natal and synastry aspect calculations
- 📈 **Chart Generation** - SVG birth, synastry, transit, and composite charts
- 💑 **Relationship Compatibility** - Compatibility scoring and analysis

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required environment variables:

```env
# Supabase Configuration (Required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key

# GeoNames for location lookup (Optional)
GEONAMES_USERNAME=your_geonames_username

# Frontend URL for CORS (Optional)
FRONTEND_URL=https://your-frontend.com
```

### 3. Set Up Supabase

1. Create a Supabase project at https://supabase.com
2. Enable Email authentication in **Authentication > Providers**
3. Copy your project URL and anon key from **Settings > API**
4. Add them to your `.env` file

### 4. Run the API

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## Authentication

All astrology endpoints are protected and require authentication.

### Sign Up

```bash
POST /auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

Response:
```json
{
  "success": true,
  "user": {
    "id": "user-uuid",
    "email": "user@example.com"
  },
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "message": "User registered successfully. Please check your email to confirm your account."
}
```

### Login

```bash
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

Response:
```json
{
  "success": true,
  "user": {
    "id": "user-uuid",
    "email": "user@example.com"
  },
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "message": "Login successful"
}
```

### Using Protected Endpoints

Include the access token in the Authorization header:

```bash
POST /astrology/birth-chart
Authorization: Bearer your_jwt_token_here
Content-Type: application/json

{
  "name": "John Lennon",
  "year": 1940,
  "month": 10,
  "day": 9,
  "hour": 18,
  "minute": 30,
  "city": "Liverpool",
  "nation": "GB",
  "online": true
}
```

### Additional Auth Endpoints

- `GET /auth/me` - Get current user info
- `POST /auth/logout` - Logout and invalidate session
- `POST /auth/refresh` - Refresh access token using refresh token

## API Endpoints

### Protected Astrology Endpoints

All endpoints below require `Authorization: Bearer <token>` header.

#### Birth Charts
- `POST /astrology/birth-chart` - Get complete birth chart data

#### Aspects
- `POST /astrology/aspects/natal` - Get all natal aspects
- `POST /astrology/aspects/synastry` - Get synastry aspects between two people

#### Chart Generation
- `POST /astrology/chart/birth` - Generate birth chart SVG
- `POST /astrology/chart/synastry` - Generate synastry chart SVG
- `POST /astrology/chart/transit` - Generate transit chart SVG
- `POST /astrology/chart/composite` - Generate composite chart SVG

#### Relationships
- `POST /astrology/relationship/score` - Calculate compatibility score
- `POST /astrology/relationship/composite-subject` - Create composite subject

## Example Usage

### 1. Sign Up and Login

```python
import requests

# Sign up
signup_response = requests.post(
    "http://localhost:8000/auth/signup",
    json={
        "email": "astrologer@example.com",
        "password": "securepassword123"
    }
)

# Login
login_response = requests.post(
    "http://localhost:8000/auth/login",
    json={
        "email": "astrologer@example.com",
        "password": "securepassword123"
    }
)

access_token = login_response.json()["access_token"]
```

### 2. Get Birth Chart (Authenticated)

```python
headers = {"Authorization": f"Bearer {access_token}"}

birth_chart_response = requests.post(
    "http://localhost:8000/astrology/birth-chart",
    headers=headers,
    json={
        "name": "John Lennon",
        "year": 1940,
        "month": 10,
        "day": 9,
        "hour": 18,
        "minute": 30,
        "city": "Liverpool",
        "nation": "GB",
        "online": True
    }
)

print(birth_chart_response.json())
```

### 3. Calculate Compatibility

```python
compatibility_response = requests.post(
    "http://localhost:8000/astrology/relationship/score",
    headers=headers,
    json={
        "subject1": {
            "name": "Person 1",
            "year": 1990,
            "month": 1,
            "day": 15,
            "hour": 10,
            "minute": 30,
            "lng": -0.1276,
            "lat": 51.5074,
            "tz_str": "Europe/London"
        },
        "subject2": {
            "name": "Person 2",
            "year": 1992,
            "month": 5,
            "day": 20,
            "hour": 14,
            "minute": 45,
            "lng": -0.1276,
            "lat": 51.5074,
            "tz_str": "Europe/London"
        }
    }
)

print(compatibility_response.json())
```

## Documentation

- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Project Structure

```
astrology-api/
├── api/                    # FastAPI routers
│   ├── auth.py            # Authentication endpoints
│   ├── birth_chart_router.py
│   ├── aspects_router.py
│   ├── charts_router.py
│   └── relationships_router.py
├── middleware/            # Auth middleware
│   └── auth.py           # JWT verification
├── models/               # Pydantic models
│   └── astrology.py     # Request/response models
├── services/            # Business logic
│   ├── birth_chart.py
│   ├── aspects.py
│   ├── charts.py
│   └── relationships.py
├── main.py             # FastAPI application
└── .env               # Environment variables (not in git)
```

## Security

- All astrology endpoints are protected with JWT authentication
- Passwords are securely hashed by Supabase
- Email verification is required for new accounts (configurable in Supabase)
- Refresh tokens allow seamless re-authentication

## Error Handling

All endpoints return standardized error responses:

```json
{
  "detail": "Error message here"
}
```

Common status codes:
- `200` - Success
- `400` - Bad request (invalid data)
- `401` - Unauthorized (missing or invalid token)
- `500` - Internal server error

## Development

See `POSTMAN_EXAMPLES.json` for complete API request examples.

## License

MIT
