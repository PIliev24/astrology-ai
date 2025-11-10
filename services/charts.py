"""
Chart Generation (SVG) Services
"""

from typing import Optional, List, Literal, Any
from kerykeion import AstrologicalSubject, KerykeionChartSVG, CompositeSubjectFactory


def generate_birth_chart_svg(
    subject: AstrologicalSubject,
    output_directory: Optional[str] = None,
    theme: Literal["classic", "dark", "dark_high_contrast", "light"] = "classic",
    active_points: Optional[List[str]] = None,
    chart_language: str = "EN",
) -> str:
    """
    Generate SVG birth/natal chart.
    
    Args:
        subject: AstrologicalSubject instance
        output_directory: Custom output directory (default: home directory)
        theme: Visual theme for the chart
        active_points: List of points to include in chart
        chart_language: Chart language code (e.g., "EN", "ES", "IT")
    
    Returns:
        Path to generated SVG file
    """
    kwargs = {"first_obj": subject, "theme": theme, "chart_language": chart_language}
    
    if output_directory:
        kwargs["new_output_directory"] = output_directory
    if active_points:
        kwargs["active_points"] = active_points
    
    chart = KerykeionChartSVG(**kwargs)
    return chart.makeSVG()


def generate_synastry_chart_svg(
    subject1: AstrologicalSubject,
    subject2: AstrologicalSubject,
    output_directory: Optional[str] = None,
    theme: str = "classic",
    chart_language: str = "EN",
) -> str:
    """
    Generate synastry chart comparing two subjects.
    
    Args:
        subject1: First AstrologicalSubject
        subject2: Second AstrologicalSubject
        output_directory: Custom output directory
        theme: Visual theme
        chart_language: Chart language
    
    Returns:
        Path to generated SVG file
    """
    kwargs = {
        "first_obj": subject1,
        "chart_type": "Synastry",
        "second_obj": subject2,
        "theme": theme,
        "chart_language": chart_language,
    }
    
    if output_directory:
        kwargs["new_output_directory"] = output_directory
    
    chart = KerykeionChartSVG(**kwargs)
    return chart.makeSVG()


def generate_transit_chart_svg(
    subject: AstrologicalSubject,
    transit: AstrologicalSubject,
    output_directory: Optional[str] = None,
    theme: str = "classic",
    chart_language: str = "EN",
) -> str:
    """
    Generate transit chart.
    
    Args:
        subject: Natal AstrologicalSubject
        transit: Transit AstrologicalSubject (current positions)
        output_directory: Custom output directory
        theme: Visual theme
        chart_language: Chart language
    
    Returns:
        Path to generated SVG file
    """
    kwargs = {
        "first_obj": subject,
        "chart_type": "Transit",
        "second_obj": transit,
        "theme": theme,
        "chart_language": chart_language,
    }
    
    if output_directory:
        kwargs["new_output_directory"] = output_directory
    
    chart = KerykeionChartSVG(**kwargs)
    return chart.makeSVG()


def generate_composite_chart_svg(
    subject1: AstrologicalSubject,
    subject2: AstrologicalSubject,
    output_directory: Optional[str] = None,
    theme: str = "classic",
    chart_language: str = "EN",
) -> str:
    """
    Generate composite chart (midpoint method).
    
    Args:
        subject1: First AstrologicalSubject
        subject2: Second AstrologicalSubject
        output_directory: Custom output directory
        theme: Visual theme
        chart_language: Chart language
    
    Returns:
        Path to generated SVG file
    """
    factory = CompositeSubjectFactory(subject1, subject2)
    composite_model = factory.get_midpoint_composite_subject_model()
    
    kwargs = {
        "first_obj": composite_model,
        "chart_type": "Composite",
        "theme": theme,
        "chart_language": chart_language,
    }
    
    if output_directory:
        kwargs["new_output_directory"] = output_directory
    
    chart = KerykeionChartSVG(**kwargs)
    return chart.makeSVG()
