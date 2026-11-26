"""Database engine configuration regression tests."""
import unittest

from sqlalchemy.pool import NullPool

from app.database import engine


class DatabaseEngineTest(unittest.TestCase):
    def test_sqlite_uses_null_pool(self):
        """SQLite must not receive PostgreSQL-only pool sizing options."""
        self.assertTrue(str(engine.url).startswith("sqlite"))
        self.assertIsInstance(engine.pool, NullPool)


if __name__ == "__main__":
    unittest.main()
