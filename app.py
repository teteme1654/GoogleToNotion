"""WSGI entry point for Render deployment.

This module exposes the Flask application instance defined in ``api.py``
under the conventional ``app`` name so that process managers like
Gunicorn can import it via ``gunicorn app:app``.
"""

from api import app as application

# Gunicorn (and similar servers) look for a module-level ``app`` variable by
# default. Alias the imported ``application`` object to keep that behavior
# while avoiding circular imports.
app = application
