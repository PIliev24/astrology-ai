# Code Style Guidelines

## Docstrings

Use **Google-style format** with Args/Returns sections:

```python
def function_name(param1: str, param2: int) -> dict:
    """
    Brief description of what the function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Dictionary containing the result
    
    Raises:
        ValueError: If param1 is invalid
    """
    pass
```

## Router Docstrings

Router endpoints should include FastAPI `summary` and `description` parameters:

```python
@router.post(
    "/endpoint",
    summary="Brief one-line summary",
    description="Longer description explaining what the endpoint does"
)
async def endpoint_handler(request: RequestModel):
    """
    Additional detailed docstring if needed.
    """
    pass
```

## Type Hints

**All service functions must have type hints** for:
- All parameters
- Return types

```python
from typing import Optional, Dict, Any
from kerykeion import AstrologicalSubject

def service_function(
    subject: AstrologicalSubject,
    optional_param: Optional[str] = None
) -> Dict[str, Any]:
    """Function with complete type hints."""
    pass
```

## Logging

Use the `logging` module (configured in `main.py`):

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error message")
```

## Code Organization

### Imports Order
1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# Standard library
import os
from typing import Optional

# Third-party
from fastapi import APIRouter, HTTPException
from kerykeion import AstrologicalSubject

# Local
from models.astrology import BirthDataRequest
from services.birth_chart import create_astrological_subject
```

### Function Organization
- Keep functions focused and single-purpose
- Extract complex logic into helper functions
- Keep router endpoints thin - delegate to services

## Naming Conventions

- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private functions**: Prefix with `_` if internal use only

## Response Format

All successful API responses should follow this structure:

```python
return {
    "success": True,
    "data": result_data,  # or "aspects", "chart_path", etc.
    # Additional fields as needed
}
```

## Comments

- Use comments to explain **why**, not **what**
- Code should be self-documenting through good naming
- Add comments for complex business logic or non-obvious decisions

## Line Length

- Aim for 88-100 characters per line (Black formatter default)
- Break long lines at logical points
- Use parentheses for multi-line expressions

