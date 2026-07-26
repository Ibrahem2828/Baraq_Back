"""Test discovery limited to applications enabled by the Django project.

The repository deliberately retains two uninstalled, legacy AI prototypes for
reference while the production integration lives in ``apps.ai_integration``.
Django's default ``test`` command discovers every Python package below the
repository root, including those prototypes. That makes a deployment check
execute code which is neither installed nor routed by this project.

Explicit test labels remain untouched, so a developer can still run a legacy
suite deliberately while it is being migrated or removed.
"""

from __future__ import annotations

from importlib.util import find_spec

from django.apps import apps
from django.test.runner import DiscoverRunner


class EnabledAppsDiscoverRunner(DiscoverRunner):
    """Discover tests from installed project apps when no label is supplied."""

    def build_suite(self, test_labels=None, **kwargs):
        if not test_labels:
            test_labels = [
                f"{app_config.name}.tests"
                for app_config in apps.get_app_configs()
                if app_config.name.startswith("apps.")
                and find_spec(f"{app_config.name}.tests") is not None
            ]
        return super().build_suite(test_labels, **kwargs)
