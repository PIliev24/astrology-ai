"""
Date Parsing Service
Handles parsing of date strings in format "dd-mmm-yyyy hh:mm"
"""

import re
from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException, status


# Month abbreviations mapping
MONTH_ABBREVIATIONS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}


def parse_birth_datetime(date_string: str) -> Dict[str, Any]:
    """
    Parse date string in format "dd-mmm-yyyy hh:mm" (e.g., "15-Jun-1990 14:30").
    
    Args:
        date_string: Date string in format "dd-mmm-yyyy hh:mm"
    
    Returns:
        Dictionary with parsed birth data:
        {
            "year": int,
            "month": int (1-12),
            "day": int (1-31),
            "hour": int (0-23),
            "minute": int (0-59)
        }
    
    Raises:
        HTTPException: If date format is invalid or date values are out of range
    """
    # Remove extra whitespace
    date_string = date_string.strip()
    
    # Pattern: dd-mmm-yyyy hh:mm or dd mmm yyyy hh:mm
    # Examples: "15-Jun-1990 14:30", "15 Jun 1990 14:30", "15-Jun-1990 14:30:00"
    pattern = r'(\d{1,2})[\s-]+([a-zA-Z]+)[\s-]+(\d{4})[\s]+(\d{1,2}):(\d{2})(?::\d{2})?'
    
    match = re.match(pattern, date_string, re.IGNORECASE)
    
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Expected 'dd-mmm-yyyy hh:mm' (e.g., '15-Jun-1990 14:30'), got: {date_string}"
        )
    
    day_str, month_str, year_str, hour_str, minute_str = match.groups()
    
    # Parse day
    try:
        day = int(day_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid day: {day_str}"
        )
    
    # Parse month
    month_lower = month_str.lower()
    if month_lower not in MONTH_ABBREVIATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid month abbreviation: {month_str}. Use Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec"
        )
    month = MONTH_ABBREVIATIONS[month_lower]
    
    # Parse year
    try:
        year = int(year_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid year: {year_str}"
        )
    
    # Parse hour
    try:
        hour = int(hour_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid hour: {hour_str}"
        )
    
    # Parse minute
    try:
        minute = int(minute_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid minute: {minute_str}"
        )
    
    # Validate ranges
    if year < 1900 or year > 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Year must be between 1900 and 2100, got: {year}"
        )
    
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Month must be between 1 and 12, got: {month}"
        )
    
    if day < 1 or day > 31:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Day must be between 1 and 31, got: {day}"
        )
    
    if hour < 0 or hour > 23:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hour must be between 0 and 23, got: {hour}"
        )
    
    if minute < 0 or minute > 59:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minute must be between 0 and 59, got: {minute}"
        )
    
    # Validate that the date is actually valid (e.g., not Feb 30)
    try:
        datetime(year, month, day, hour, minute)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date: {str(e)}"
        )
    
    return {
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute
    }

