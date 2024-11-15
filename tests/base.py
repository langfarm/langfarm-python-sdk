import logging.config
import unittest

import yaml
from dotenv import load_dotenv


def config_log(base_dir: str):
    # 读取 yaml 格式的日志配置
    with open(f'{base_dir}/logging.yaml') as f:
        log_config = yaml.full_load(f)
        out_log_file = log_config['handlers']['file_handler']['filename']
        log_config['handlers']['file_handler']['filename'] = f'{base_dir}/{out_log_file}'
        logging.config.dictConfig(log_config)


logger = logging.getLogger(__name__)


class BaseTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 配置日志
        base_dir = __file__[:-len('/tests/base.py')]
        log_file = f'{base_dir}/logging.yaml'
        config_log(base_dir)

        # 打印空行
        print()
        logger.info("配置 log_file = %s", log_file)

        # load .env
        dotenv_file = f'{base_dir}/.env'
        logger.info("配置 .env = %s", dotenv_file)
        load_dotenv(dotenv_file, verbose=True)

    def setUp(self):
        # 打印空行
        print()


if __name__ == '__main__':
    unittest.main()
