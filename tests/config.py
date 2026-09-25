"""
Configuration for tests using centralized config.
"""

from config import get_database_url

# Use the centralized configuration
database_url = get_database_url()