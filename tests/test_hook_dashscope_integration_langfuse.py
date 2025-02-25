import os
import time
import unittest
from typing import Generator, Optional

from mock import MockOutputGeneration, dashscope_call, assert_trace  # type: ignore
from base import LangfuseSDKTestCase, get_test_logger
from dashscope.api_entities.dashscope_response import GenerationResponse
from langfuse.decorators import langfuse_context, observe

from langfarm.hooks.dashscope import Generation

logger = get_test_logger(__name__)


class HookDashscopeTestCase(LangfuseSDKTestCase):
    def test_dashscope_integration_observe(self):
        query = "请用50个字描写春天的景色。"
        my_output = (
            "mock: 春天，大地复苏，桃花盛开，嫩绿的柳枝随风轻舞，溪水潺潺流淌，鸟儿欢快鸣叫，万物充满生机与希望。"
        )
        MockOutputGeneration.with_input_tokens(len(query)).with_output(my_output)
        trace_id, output = dashscope_call(query)
        assert_trace(self.langfuse_sdk, query, output, trace_id)

    @observe(as_type="generation")
    def stream_tongyi_generation(
        self, model_name: str, query: str, result_format: str, is_inc_output: bool
    ) -> Generator[GenerationResponse, None, None]:
        response = Generation.call(
            api_key=os.getenv("DASHSCOPE_API_KEY") or "",
            model=model_name,
            prompt=query,
            result_format=result_format,
            stream=True,
            incremental_output=is_inc_output,
        )

        return response

    @observe()
    def stream_dashscope_hook_call(self, query: str, is_inc_output: bool = True) -> tuple[Optional[str], str]:
        result_format = "message"
        chunks = self.stream_tongyi_generation("qwen-turbo", query, result_format, is_inc_output)
        langfuse_context.update_current_trace(input=query, name=f"stream[{is_inc_output}]_hook_call")

        output = ""

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
        logger.info("trace_id=%s", trace_id)
        logger.info("output=%s", output)
        assert trace_id
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

        assert obs.usage.input
        assert obs.usage.input > 0
        assert obs.usage.output
        assert obs.usage.output > 0
        assert obs.usage.total
        assert obs.usage.total > 0
        logger.info("完成!")

    def test_stream_dashscope_integration_observe(self):
        query = "请用50个字描写春天的景色。"
        self.assert_stream_dashscope_integration_observe(query, False)

    def test_stream_dashscope_integration_observe_inc(self):
        query = "请用50个字描写夏天的景色。"
        self.assert_stream_dashscope_integration_observe(query, True)


if __name__ == "__main__":
    unittest.main()
