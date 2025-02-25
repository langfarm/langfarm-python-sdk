import os
import time
import unittest

from base import BaseTestCase, get_test_logger
from langchain_community.llms import Tongyi
from langchain_core.language_models import BaseLLM

from langfarm.hooks.langfuse.callback import CallbackHandler

logger = get_test_logger(__name__)


class HookLangfuseCallbackTestCase(BaseTestCase):
    def assert_callback_report_data(self, query: str, output: str, langfuse_handler: CallbackHandler):
        s = 2
        logger.info("等待 %d 秒，等待 langfuse 异步上报。", s)
        langfuse_handler.flush()
        time.sleep(s)
        trace = langfuse_handler.trace
        trace_id = trace.id if trace else None
        logger.info("trace_id = %s", trace_id)
        assert trace_id
        assert langfuse_handler.langfuse
        tr = langfuse_handler.langfuse.fetch_trace(trace_id)
        assert tr
        assert tr.data
        tr = tr.data

        assert tr.input == query
        assert tr.output == output

        assert tr.observations
        assert len(tr.observations) > 0
        obs = tr.observations[0]
        assert obs
        assert obs.usage

        logger.info("observation.usage=%s", obs.usage)

        assert obs.usage.input
        assert obs.usage.output
        assert obs.usage.total
        assert obs.usage.input > 0
        assert obs.usage.output > 0
        assert obs.usage.total > 0

        usage = langfuse_handler.get_usage()
        assert usage
        logger.info("get_usage=%s", usage)
        assert obs.usage.input == usage["input"]  # type: ignore
        assert obs.usage.output == usage["output"]  # type: ignore
        assert obs.usage.total == usage["total"]  # type: ignore
        logger.info("完成!")

    def test_use_tongyi_with_langfuse_callback(self):
        query = "请用50个字描写春天的景色。"
        llm = Tongyi(model="qwen-plus", api_key=os.getenv("DASHSCOPE_API_KEY"))
        # base.BaseTestCase 的 setUpClass() 使用 load_dotenv() 加载了 .env 配置
        # LANGFUSE_PUBLIC_KEY
        # LANGFUSE_SECRET_KEY
        # LANGFUSE_HOST
        # 也可以在构造函数里设置
        langfuse_handler = CallbackHandler()
        output = llm.invoke(query, config={"callbacks": [langfuse_handler]})
        logger.info("Tongyi 输出 -> %s", output)
        self.assert_callback_report_data(query, output, langfuse_handler)

    def test_use_tongyi_stream_with_langfuse_callback(self):
        query = "请用50个字描写春天的景色。"
        llm: BaseLLM = Tongyi(model="qwen-turbo", api_key=os.getenv("DASHSCOPE_API_KEY"))
        langfuse_handler = CallbackHandler(trace_name="Tongyi-stream")
        chunks = llm.stream(query, config={"callbacks": [langfuse_handler]})
        output_chunk = []
        for chunk in chunks:
            output_chunk.append(chunk)
            logger.info("Tongyi 输出 -> %s", chunk)

        output = "".join(output_chunk)
        logger.info("chunks => %s", output)

        self.assert_callback_report_data(query, output, langfuse_handler)


if __name__ == "__main__":
    unittest.main()
