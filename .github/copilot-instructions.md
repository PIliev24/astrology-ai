# Astrology API - AI Coding Guide

## Architecture Overview

FastAPI-based astrology calculation service wrapping the **Kerykeion** library. The API provides birth chart calculations, astrological aspects, SVG chart generation, and relationship compatibility analysis.

**Key dependencies:** `kerykeion` (core astrology engine), `fastapi`, `pydantic`, `redis`, `supabase`, `openai`

### Project Structure
- `api/` - FastAPI routers grouped by domain (birth_chart, aspects, charts, relationships)
- `services/` - Business logic wrapping kerykeion library functions
- `models/` - Pydantic request/response models
- `middleware/` - Auth and i18n
- `cache/` - SQLite cache for GeoNames data (managed by kerykeion)

## Critical Patterns

### 1. Subject Creation Pattern
All endpoints follow this standardized flow:
```python
# Router calls service helper with destructured request fields
subject = create_astrological_subject(
    name=request.name,
    year=request.year,
    month=request.month,
    # ... all fields from BirthDataRequest
)
```
**Never instantiate `AstrologicalSubject` directly** - always use `services.birth_chart.create_astrological_subject()` which handles:
- Location resolution (city/nation OR lng/lat/tz_str)
- Optional field handling (sidereal_mode, geonames_username from env)
- Online geocoding mode auto-activation

### 2. Location Data Requirements
Kerykeion requires EITHER:
- `city` + `nation` (with `online=True` for auto-geocoding)
- `lng` + `lat` + `tz_str` (explicit coordinates)

Missing required location fields will raise `ValueError` in `create_astrological_subject()`.

### 3. Pydantic Request Models
All API endpoints use strongly-typed Pydantic models from `models/astrology.py`:
- `BirthDataRequest` - Single subject (birth chart, aspects, chart generation)
- `TwoSubjectsRequest` - Nested subjects (synastry, relationships)
- `ChartGenerationRequest`, `SynastryChartRequest`, `TransitChartRequest` - Chart-specific

### 4. Aspect Handling Distinction
```python
# Natal aspects - returns ALL aspects
aspects = NatalAspects(subject).all_aspects

# Synastry aspects - returns only RELEVANT aspects
aspects = SynastryAspects(subject1, subject2).relevant_aspects
```
The `/aspects/natal` endpoint explicitly returns **all** aspects, not just relevant ones.

### 5. Chart Generation Output
All chart generation functions return **file paths** to SVG files:
```python
svg_path = generate_birth_chart_svg(subject, ...)
# Returns: "/path/to/home/John_Lennon_Natal_Chart.svg"
```
Charts save to user's home directory by default; override with `output_directory` parameter.

## Development Workflow

### Running the API
```powershell
# Development server with auto-reload
python main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Variables
Required in `.env`:
```
GEONAMES_USERNAME=your_username  # For online geocoding with city/nation
FRONTEND_URL=https://your-frontend.com  # Optional, for CORS
```

### Testing Endpoints
Use `POSTMAN_EXAMPLES.json` for complete request examples. Key endpoints:
- `POST /astrology/birth-chart` - Birth data extraction
- `POST /astrology/aspects/natal` - All natal aspects
- `POST /astrology/aspects/synastry` - Compatibility aspects
- `POST /astrology/chart/birth` - SVG birth chart generation
- `POST /astrology/relationship/score` - Compatibility percentage

## Router Organization Pattern

Each router follows this structure:
1. Import service functions from `services/`
2. Define router with prefix and tags
3. Implement endpoints that:
   - Accept Pydantic request model
   - Call `create_astrological_subject()` for each subject
   - Pass subjects to service functions
   - Return `{"success": True, "data": ...}` structure
   - Wrap in try/except → `HTTPException(status_code=400, detail=str(e))`

**No business logic in routers** - delegate to `services/` functions.

## Kerykeion Integration Notes

### Astrological Subject
Core entity returned by `create_astrological_subject()`. Contains:
- Birth data properties (`.year`, `.month`, `.day`, `.hour`, `.minute`)
- Location (`.lng`, `.lat`, `.tz_str`, `.city`, `.nation`)
- Calculated positions (`.sun`, `.moon`, `.planets`, `.houses`)
- All data is pre-calculated on instantiation

### House Systems
Default is `"P"` (Placidus). Common options: `"K"` (Koch), `"E"` (Equal), `"W"` (Whole Sign).

### Zodiac Types
- `"Tropic"` (default) - Western tropical zodiac
- `"Sidereal"` - Vedic/sidereal zodiac (requires `sidereal_mode`, e.g., `"LAHIRI"`)

### Chart Themes
`KerykeionChartSVG` supports: `"classic"`, `"dark"`, `"dark_high_contrast"`, `"light"`

## Incomplete Features (Empty Files)
- `middleware/auth.py` - No authentication implemented
- `middleware/i18n.py` - No internationalization
- `models/cache.py` - Redis caching planned but not implemented
- `models/ai.py` - OpenAI integration planned

**Don't import from these files** - they're empty placeholders.

## Common Pitfalls

1. **Creating subjects without validation** - Always destructure Pydantic request models rather than passing dicts
2. **Forgetting online mode** - If using `city`/`nation` without coordinates, set `online=True`
3. **Mixing location formats** - Don't provide both city/nation AND lng/lat in same request
4. **Assuming relevant aspects** - Natal endpoint returns `.all_aspects`, not `.relevant_aspects`
5. **Hardcoding output paths** - SVG functions handle path generation; return paths, don't construct them

## Code Style

- Docstrings: Google-style format with Args/Returns
- Router docstrings: Include FastAPI `summary` and `description` parameters
- Service functions: Type hints for all parameters and returns
- Error handling: Catch generic `Exception` in routers, return 400 with error message
- Logging: Use `logging` module (configured in `main.py`)
