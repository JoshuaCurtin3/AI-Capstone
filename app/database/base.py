"""Database-engine-level helpers that are not tied to one domain's models.

This is the home for things like custom DB routers, connection health
checks, or raw-SQL helpers — NOT for model class definitions (those live in
each domain app's models.py) and NOT for migrations (Django keeps those
per-app under <app>/migrations/).

TODO: add a router/helper here once a concrete need exists.
"""
