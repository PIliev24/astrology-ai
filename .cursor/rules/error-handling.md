# Error Handling Patterns

## Standard Error Response Format

All endpoints return standardized error responses:

```json
{
  "detail": "Error message here"
}
```

## HTTP Status Codes

Common status codes used:
- `200` - Success
- `400` - Bad request (invalid data, validation errors)
- `401` - Unauthorized (missing or invalid token)
- `500` - Internal server error

## Router Error Handling Pattern

All router endpoints must wrap business logic in try/except blocks:

```python
@router.post("/endpoint")
async def endpoint_handler(
    request: RequestModel,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Business logic here
        subject = create_astrological_subject(...)
        result = service_function(subject)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Exception Handling Guidelines

1. **Catch generic `Exception`** in routers - let service functions handle specific exceptions
2. **Return 400 status code** for client errors (invalid input, validation failures)
3. **Return 401 status code** for authentication failures (handled by middleware)
4. **Return 500 status code** for unexpected server errors (should be rare)

## Service Layer Error Handling

Service functions should:
- Raise specific exceptions with clear messages
- Let `ValueError` propagate for invalid input (e.g., missing location data)
- Handle Kerykeion-specific exceptions appropriately

## Authentication Errors

Authentication errors are handled by `middleware.auth.get_current_user()`:
- Returns `401 Unauthorized` for invalid/missing tokens
- Returns `500 Internal Server Error` if Supabase is not configured

## Validation Errors

Pydantic automatically validates request models and returns `422 Unprocessable Entity` for invalid data. No need to manually validate in routers.

## Error Messages

- Use clear, descriptive error messages
- Include relevant context when helpful
- Avoid exposing internal implementation details in production

## Logging Errors

Use the logging module for error tracking:

```python
import logging

logger = logging.getLogger(__name__)

try:
    # Business logic
except Exception as e:
    logger.error(f"Error in endpoint: {str(e)}")
    raise HTTPException(status_code=400, detail=str(e))
```

