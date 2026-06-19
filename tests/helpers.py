from __future__ import annotations

from backend.domains.users.dependencies import get_user_store


class FakeNoUserStore:
    def has_users(self):
        return False


def allow_anonymous_until_bootstrap(app):
    app.dependency_overrides[get_user_store] = lambda: FakeNoUserStore()
    return app
