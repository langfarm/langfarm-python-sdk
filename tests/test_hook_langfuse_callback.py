import logging
import os
import time
import unittest

from langchain_community.llms import Tongyi
from langchain_core.language_models import BaseLLM

from langfarm.hooks.langfuse.callback import CallbackHandler
from tests import base

logger = logging.getLogger(__name__)


class HookLangfuseCallbackTestCase(base.BaseTestCase):

    def test_use_tongyi_with_langfuse_callback(self):
        query = '请用50个字描写春天的景色。'
        llm = Tongyi(model="qwen-plus", api_key=os.getenv("DASHSCOPE_API_KEY"))
        # base.BaseTestCase 的 setUpClass() 使用 load_dotenv() 加载了 .env 配置
        # LANGFUSE_PUBLIC_KEY
        # LANGFUSE_SECRET_KEY
        # LANGFUSE_HOST
        # 也可以在构造函数里设置
        langfuse_handler = CallbackHandler()
        r = llm.invoke(query, config={"callbacks": [langfuse_handler]})
        logger.info("Tongyi 输出 -> %s", r)
        s = 2
        logger.info("等待 %d 秒，等待 langfuse 异步上报。", s)
        time.sleep(s)
        trace = langfuse_handler.trace
        trace_id = trace.id if trace else None
        logger.info("trace_id = %s", trace_id)
        assert trace_id
        tr = langfuse_handler.langfuse.fetch_trace(trace_id)
        assert tr
        assert tr.data
        tr = tr.data

        assert tr.input == query
        assert tr.output == r

        assert tr.observations
        assert len(tr.observations) > 0
        obs = tr.observations[0]
        assert obs
        assert obs.usage

        logger.info(obs.usage)

        assert obs.usage.input > 0
        assert obs.usage.output > 0
        assert obs.usage.total > 0
        logger.info("完成!")

    def test_use_tongyi_stream_with_langfuse_callback(self):
        query = '请用200个字描写春天的景色。'
        llm: BaseLLM = Tongyi(model="qwen-turbo", api_key=os.getenv("DASHSCOPE_API_KEY"))
        langfuse_handler = CallbackHandler(trace_name="Tongyi-stream")
        chunks = llm.stream(query, config={"callbacks": [langfuse_handler]})
        output_chunk = []
        for chunk in chunks:
            output_chunk.append(chunk)
            logger.info("Tongyi 输出 -> %s", chunk)

        output = "".join(output_chunk)
        logger.info("chunks => %s", output)

        s = 2
        logger.info("等待 %d 秒，等待 langfuse 异步上报。", s)
        time.sleep(s)

        trace = langfuse_handler.trace
        trace_id = trace.id if trace else None
        logger.info("trace_id = %s", trace_id)
        assert trace_id
        tr = langfuse_handler.langfuse.fetch_trace(trace_id)
        assert tr
        assert tr.data
        tr = tr.data

        assert tr.input == query
        assert tr.output == output
        logger.info("完成!")


if __name__ == '__main__':
    unittest.main()
