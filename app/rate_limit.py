"""Shared Limiter singleton for slowapi rate limiting.

Import this module in both main.py (to attach to app.state) and in
routers that need rate limiting (to apply @limiter.limit decorators).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
