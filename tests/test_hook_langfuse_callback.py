import logging
import time
import unittest

from langchain_community.llms import Tongyi
from langfarm.hooks.langfuse.callback import CallbackHandler
from tests import base

logger = logging.getLogger(__name__)


class HookLangfuseCallbackTestCase(base.BaseTestCase):

    def test_use_tongyi_with_langfuse_callback(self):
        query = '请用50个字描写春天的景色。'
        llm = Tongyi(model="qwen-plus")
        # base.BaseTestCase 的 setUpClass() 使用 load_dotenv() 加载了 .env 配置
        # LANGFUSE_PUBLIC_KEY
        # LANGFUSE_SECRET_KEY
        # LANGFUSE_HOST
        # 也可以在构造函数里设置
        langfuse_handler = CallbackHandler()
        r = llm.invoke(query, config={"callbacks": [langfuse_handler]})
        logger.info("Tongyi 输出 -> %s", r)
        s = 5
        logger.info("等待 %d 秒，等待 langfuse 异步上报。", s)
        time.sleep(s)
        trace = langfuse_handler.trace
        trace_id = trace.id if trace else None
        logger.info("trace_id = %s", trace_id)
        assert trace_id
        logger.info("完成!")


if __name__ == '__main__':
    unittest.main()
