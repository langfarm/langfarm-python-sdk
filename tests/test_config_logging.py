import unittest

from base import BaseTestCase, get_test_logger

logger = get_test_logger(__name__)


class MyTestCase(BaseTestCase):
    def test_log_config(self):
        logger.info("test logging config")


if __name__ == "__main__":
    unittest.main()
