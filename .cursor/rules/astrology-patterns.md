# Astrology API Patterns

## Subject Creation Pattern

**CRITICAL**: Never instantiate `AstrologicalSubject` directly. Always use `services.birth_chart.create_astrological_subject()`.

### Standard Flow

All endpoints follow this pattern:

```python
# Router calls service helper with destructured request fields
subject = create_astrological_subject(
    name=request.name,
    year=request.year,
    month=request.month,
    day=request.day,
    hour=request.hour,
    minute=request.minute,
    city=request.city,
    nation=request.nation,
    lng=request.lng,
    lat=request.lat,
    tz_str=request.tz_str,
    zodiac_type=request.zodiac_type,
    sidereal_mode=request.sidereal_mode,
    houses_system=request.houses_system,
    perspective_type=request.perspective_type,
    online=request.online,
    geonames_username=request.geonames_username,
)
```

The `create_astrological_subject()` function handles:
- Location resolution (city/nation OR lng/lat/tz_str)
- Optional field handling (sidereal_mode, geonames_username from env)
- Online geocoding mode auto-activation

## Location Data Requirements

Kerykeion requires **EITHER**:

1. **City + Nation** (with `online=True` for auto-geocoding):
   ```python
   city="Liverpool"
   nation="GB"
   online=True
   ```

2. **Explicit Coordinates**:
   ```python
   lng=-0.1276
   lat=51.5074
   tz_str="Europe/London"
   ```

**Never mix both formats** - provide either city/nation OR lng/lat/tz_str, not both.

Missing required location fields will raise `ValueError` in `create_astrological_subject()`.

## Pydantic Request Models

All API endpoints use strongly-typed Pydantic models from `models/astrology.py`:

- `BirthDataRequest` - Single subject (birth chart, aspects, chart generation)
- `TwoSubjectsRequest` - Nested subjects (synastry, relationships)
- `ChartGenerationRequest` - Birth chart SVG generation
- `SynastryChartRequest` - Synastry chart generation
- `TransitChartRequest` - Transit chart generation

**Always destructure Pydantic request models** - never pass dicts directly to service functions.

## Router Organization Pattern

Each router follows this structure:

1. **Import service functions** from `services/`
2. **Define router** with prefix and tags:
   ```python
   router = APIRouter(prefix="/astrology/birth-chart", tags=["Birth Chart"])
   ```
3. **Implement endpoints** that:
   - Accept Pydantic request model
   - Call `create_astrological_subject()` for each subject
   - Pass subjects to service functions
   - Return `{"success": True, "data": ...}` structure
   - Wrap in try/except → `HTTPException(status_code=400, detail=str(e))`

**No business logic in routers** - delegate to `services/` functions.

### Example Router Structure

```python
from fastapi import APIRouter, HTTPException, Depends
from models.astrology import BirthDataRequest
from services.birth_chart import create_astrological_subject, get_birth_chart_data
from middleware.auth import get_current_user

router = APIRouter(prefix="/astrology/birth-chart", tags=["Birth Chart"])

@router.post(
    "",
    summary="Get complete birth chart data",
    description="Create an astrological subject and retrieve all planetary and house positions"
)
async def get_birth_chart(
    request: BirthDataRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        subject = create_astrological_subject(
            name=request.name,
            year=request.year,
            # ... all fields from BirthDataRequest
        )
        
        chart_data = get_birth_chart_data(subject)
        return {"success": True, "data": chart_data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Common Pitfalls

1. **Creating subjects without validation** - Always destructure Pydantic request models rather than passing dicts
2. **Forgetting online mode** - If using `city`/`nation` without coordinates, set `online=True`
3. **Mixing location formats** - Don't provide both city/nation AND lng/lat in same request
4. **Hardcoding output paths** - SVG functions handle path generation; return paths, don't construct them

