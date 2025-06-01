# __init__.py
"""
UI Faculty Natural BFS Crawler Package

This package contains the natural BFS web crawler for UI faculty pages.
The crawler follows natural website navigation patterns:
Homepage -> Akademik -> Fakultas -> Individual Faculty Pages

Features:
- Natural BFS navigation (no URL cheating)
- Priority-based link discovery
- Navigation stage detection
- Faculty information extraction
- Respectful crawling with delays
"""

from .bfs_crawler import NaturalUIFacultyCrawler
from .url_utils import BFSURLUtils

__version__ = "2.0.0"
__author__ = "UI Faculty Crawler Team"
__description__ = "Natural BFS crawler for UI faculty information"

__all__ = [
    'NaturalUIFacultyCrawler',
    'BFSURLUtils'
]

def create_natural_crawler(base_url="https://www.ui.ac.id/", delay=1):
    """
    Create a natural BFS crawler instance
    
    Args:
        base_url (str): Starting URL (default: UI homepage)
        delay (int): Delay between requests in seconds
    
    Returns:
        NaturalUIFacultyCrawler: Configured crawler instance
    """
    return NaturalUIFacultyCrawler(base_url=base_url, delay=delay)

def run_natural_discovery(max_depth=4, max_pages=50, delay=2):
    """
    Run natural faculty discovery with sensible defaults
    
    Args:
        max_depth (int): Maximum crawl depth
        max_pages (int): Maximum pages to crawl
        delay (int): Delay between requests
    
    Returns:
        list: Discovered faculty data
    """
    crawler = create_natural_crawler(delay=delay)
    return crawler.natural_crawl_bfs(max_depth=max_depth, max_pages=max_pages)

# Package metadata
NATURAL_NAVIGATION_FLOW = [
    "🏠 Homepage (www.ui.ac.id)",
    "📚 Akademik Section", 
    "🏛️ Fakultas Listing",
    "🎓 Individual Faculty Pages"
]

SUPPORTED_FACULTY_INFO = [
    "Faculty name and description",
    "Academic programs",
    "Departments", 
    "Contact information",
    "Navigation discovery path"
]