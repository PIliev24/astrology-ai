# Kerykeion Integration Rules

## Astrological Subject

Core entity returned by `create_astrological_subject()`. Contains:
- Birth data properties (`.year`, `.month`, `.day`, `.hour`, `.minute`)
- Location (`.lng`, `.lat`, `.tz_str`, `.city`, `.nation`)
- Calculated positions (`.sun`, `.moon`, `.planets`, `.houses`)
- All data is **pre-calculated on instantiation**

## House Systems

Default is `"P"` (Placidus). Common options:
- `"P"` - Placidus (default)
- `"K"` - Koch
- `"E"` - Equal
- `"W"` - Whole Sign

Pass via `houses_system` parameter in `create_astrological_subject()`.

## Zodiac Types

- `"Tropic"` (default) - Western tropical zodiac
- `"Sidereal"` - Vedic/sidereal zodiac (requires `sidereal_mode`, e.g., `"LAHIRI"`)

When using `"Sidereal"`, always provide `sidereal_mode` parameter.

## Chart Themes

`KerykeionChartSVG` supports these themes:
- `"classic"` - Default classic theme
- `"dark"` - Dark theme
- `"dark_high_contrast"` - High contrast dark theme
- `"light"` - Light theme

## Aspect Handling Distinction

### Natal Aspects
Returns **ALL** aspects:
```python
from kerykeion import NatalAspects

aspects = NatalAspects(subject).all_aspects
```

The `/aspects/natal` endpoint explicitly returns **all** aspects, not just relevant ones.

### Synastry Aspects
Returns only **RELEVANT** aspects:
```python
from kerykeion import SynastryAspects

aspects = SynastryAspects(subject1, subject2).relevant_aspects
```

## Chart Generation Output

All chart generation functions return **file paths** to SVG files:
```python
svg_path = generate_birth_chart_svg(subject, ...)
# Returns: "/path/to/home/John_Lennon_Natal_Chart.svg"
```

Charts save to user's home directory by default; override with `output_directory` parameter.

**Do not construct paths manually** - let the service functions handle path generation.

## Perspective Types

Supported perspective types:
- `"Apparent Geocentric"` (default) - Standard geocentric perspective
- `"Heliocentric"` - Sun-centered perspective
- `"Topocentric"` - Location-specific perspective

## Chart Languages

Chart generation supports multiple languages via `chart_language` parameter:
- `"EN"` - English (default)
- `"ES"` - Spanish
- `"IT"` - Italian
- And others supported by Kerykeion

## Active Points

For chart generation, `active_points` parameter accepts a list of celestial bodies to include:
```python
active_points=["Sun", "Moon", "Mercury", "Venus", "Mars"]
```

If `None`, all default points are included.

