# Railway sometimes starts "gunicorn main:app" by default.
# This tiny file makes that work too - the real website is in app.py.
from app import app  # noqa: F401
