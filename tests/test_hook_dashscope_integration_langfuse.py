import logging
import os
import time
import unittest
from typing import Generator

from dashscope.api_entities.dashscope_response import GenerationResponse
from langfuse.decorators import observe, langfuse_context

from langfarm.hooks.dashscope import Generation
from tests.base import LangfuseSDKTestCase

logger = logging.getLogger(__name__)


class HookDashscopeTestCase(LangfuseSDKTestCase):

    @observe(as_type="generation")
    def tongyi_generation(self, model_name: str, query: str) -> str:
        response = Generation.call(
            api_key=os.getenv('DASHSCOPE_API_KEY'),
            model=model_name,
            prompt=query,
            # result_format="message"
        )

        if response.status_code == 200:
            if hasattr(response.output, "text"):
                return response.output.text
            else:
                # result_format="message"
                return response.output.choices[0].message.content
        else:
            tip = "请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code"
            raise Exception(
                f"HTTP返回码：{response.status_code}；错误码：{response.code}；错误信息：{response.message}。{tip}")

    @observe()
    def dashscope_hook_call(self, query: str) -> (str, str):
        output = self.tongyi_generation("qwen-plus", query)
        langfuse_context.update_current_trace(input=query, output=output)
        return langfuse_context.get_current_trace_id(), output

    def test_dashscope_integration_observe(self):
        query = "请用50个字描写春天的景色。"
        trace_id, output = self.dashscope_hook_call(query)
        self.flush()
        time.sleep(2)
        tr = self.langfuse_sdk.fetch_trace(trace_id)

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

        logger.info(obs.usage)

        assert obs.usage.input > 0
        assert obs.usage.output > 0
        assert obs.usage.total > 0
        logger.info("完成!")

    @observe(as_type="generation")
    def stream_tongyi_generation(
            self, model_name: str, query: str, result_format: str, is_inc_output: bool
    ) -> Generator[GenerationResponse, None, None]:
        response = Generation.call(
            api_key=os.getenv('DASHSCOPE_API_KEY'),
            model=model_name,
            prompt=query,
            result_format=result_format,
            stream=True,
            incremental_output=is_inc_output
        )

        return response

    @observe()
    def stream_dashscope_hook_call(self, query: str, is_inc_output: bool = True) -> (str, str):
        result_format = "message"
        chunks = self.stream_tongyi_generation("qwen-turbo", query, result_format, is_inc_output)
        langfuse_context.update_current_trace(input=query, name=f"stream[{is_inc_output}]_hook_call")

        output = ''

        for chunk in chunks:
            # do something ...
            chunk_output = Generation.response_to_output(result_format, chunk)
            if is_inc_output:
                output += chunk_output
            else:
                output = chunk_output
            # logger.info("chunk usage=%s, out => %s", chunk.usage, chunk_output)

        langfuse_context.update_current_trace(output=output)

        return langfuse_context.get_current_trace_id(), output

    def assert_stream_dashscope_integration_observe(self, query: str, is_inc: bool):
        trace_id, output = self.stream_dashscope_hook_call(query, is_inc)
        self.flush()
        time.sleep(2)
        tr = self.langfuse_sdk.fetch_trace(trace_id)

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

        logger.info(obs.usage)

        assert obs.usage.input > 0
        assert obs.usage.output > 0
        assert obs.usage.total > 0
        logger.info("完成!")

    def test_stream_dashscope_integration_observe(self):
        query = "请用200个字描写春天的景色。"
        self.assert_stream_dashscope_integration_observe(query, False)

    def test_stream_dashscope_integration_observe_inc(self):
        query = "请用200个字描写夏天的景色。"
        self.assert_stream_dashscope_integration_observe(query, True)


if __name__ == '__main__':
    unittest.main()
