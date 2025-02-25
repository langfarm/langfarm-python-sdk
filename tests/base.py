import logging.config
import os
import unittest
from typing import final

import yaml
from dotenv import load_dotenv
from langfuse import Langfuse

root_dir = __file__[: -len("/tests/base.py")]
log_file = f"{root_dir}/tests/logging.yaml"


def config_log(base_dir: str):
    # 读取 yaml 格式的日志配置
    with open(log_file) as f:
        log_config = yaml.full_load(f)
        out_log_file = log_config["handlers"]["file_handler"]["filename"]
        log_dir = f"{root_dir}/logs"
        if not os.path.exists(log_dir):
            print("创建日志目录：", log_dir)
            os.makedirs(log_dir, exist_ok=True)
        log_config["handlers"]["file_handler"]["filename"] = f"{base_dir}/{out_log_file}"
        logging.config.dictConfig(log_config)


def get_test_logger(name: str):
    return logging.getLogger(f"tests.{name}")


config_log(root_dir)
logger = get_test_logger(__name__)
# 打印空行
print()
logger.info("配置 log_file = %s", log_file)
# load .env
dotenv_file = f"{root_dir}/.env"
logger.info("配置 .env = %s", dotenv_file)
load_dotenv(dotenv_file, verbose=True)


class BaseTestCase(unittest.TestCase):
    @classmethod
    @final
    def setUpClass(cls):
        """
        初始化配置: 日志(logging.yaml)；环境变量(.env)。

        子类不要覆盖，使用 _set_up_class() 代替 setUpClass()
        :return:
        """

        cls._set_up_class()

    @classmethod
    def _set_up_class(cls):
        pass

    def setUp(self):
        # 打印空行
        print()


class LangfuseSDKTestCase(BaseTestCase):
    langfuse_sdk: Langfuse = None

    @classmethod
    def _set_up_class(cls):
        cls.langfuse_sdk = Langfuse()
        cls.langfuse_sdk.auth_check()

    @classmethod
    @final
    def tearDownClass(cls):
        """
        关闭 langfuse_sdk

        子类不要覆盖，使用 _tear_down_class() 代替 tearDownClass()
        :return:
        """
        if cls.langfuse_sdk:
            cls.langfuse_sdk.shutdown()
        cls._tear_down_class()

    @classmethod
    def _tear_down_class(cls):
        pass

    def flush(self):
        self.langfuse_sdk.flush()


if __name__ == "__main__":
    unittest.main()
