import os
import time
from typing import Any, Dict, Generator, List, Union, Type

from dashscope.api_entities.dashscope_response import (
    GenerationOutput,
    GenerationResponse,
    GenerationUsage,
    Message,
)

from langfuse import Langfuse

from langfarm.hooks.dashscope import Generation
from langfuse.decorators import langfuse_context, observe

from base import get_test_logger

logger = get_test_logger(__name__)

class MockGeneration(Generation):
    max_fail_cnt = 3
    fail_cnt = 0

    @classmethod
    def _reset_fail_cnt(cls):
        cls.fail_cnt = 0

    @classmethod
    def _do_call(
        cls,
        model: str,
        prompt: Any = None,
        history: list = None,
        api_key: str = None,
        messages: List[Message] = None,
        plugins: Union[str, Dict[str, Any]] = None,
        workspace: str = None,
        **kwargs,
    ) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:
        cls.fail_cnt += 1
        if cls.fail_cnt >= cls.max_fail_cnt:
            response = GenerationResponse(
                status_code=200,
                usage=GenerationUsage(input_tokens=20, output_tokens=5),
                output=GenerationOutput(text="mock for success", finish_reason="done"),
            )
        else:
            response = GenerationResponse(
                status_code=429,
                code="RateLimit",
                message="mock test rate-limit",
                usage=GenerationUsage(input_tokens=20, output_tokens=5),
                output=GenerationOutput(text="mock for rate-limit", finish_reason="done"),
            )

        return response

class MockOutputGeneration(Generation):

    input_tokens: int = 0
    output: str = "mock for success"

    @classmethod
    def with_input_tokens(cls, input_tokens: int) -> Type["MockOutputGeneration"]:
        cls.input_tokens = input_tokens
        return cls

    @classmethod
    def with_output(cls, output: str) -> Type["MockOutputGeneration"]:
        cls.output = output
        return cls

    @classmethod
    def _do_call(
        cls,
        model: str,
        prompt: Any = None,
        history: list = None,
        api_key: str = None,
        messages: List[Message] = None,
        plugins: Union[str, Dict[str, Any]] = None,
        workspace: str = None,
        **kwargs,
    ) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:

        response = GenerationResponse(
            status_code=200,
            usage=GenerationUsage(input_tokens=cls.input_tokens, output_tokens=len(cls.output)),
            output=GenerationOutput(text=cls.output, finish_reason="done"),
        )

        return response


class MockErrorGeneration(Generation):
    @classmethod
    def _do_call(
        cls,
        model: str,
        prompt: Any = None,
        history: list = None,
        api_key: str = None,
        messages: List[Message] = None,
        plugins: Union[str, Dict[str, Any]] = None,
        workspace: str = None,
        **kwargs,
    ) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:
        response = GenerationResponse(status_code=400, code="BadRequest", message="mock test bad request")
        return response


@observe(as_type="generation")
def tongyi_generation(model_name: str, query: str) -> str:
    response = MockOutputGeneration.call(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
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
            f"HTTP返回码：{response.status_code}；错误码：{response.code}；错误信息：{response.message}。{tip}"
        )

@observe()
def dashscope_call(query: str) -> (str, str):
    output = tongyi_generation("qwen-plus", query)
    langfuse_context.update_current_trace(input=query, output=output)
    return langfuse_context.get_current_trace_id(), output


def assert_trace(langfuse_sdk: Langfuse, query: str, output: str, trace_id: str):
    langfuse_sdk.flush()
    sleep_time = 1
    logger.info("等待 %s 秒，等待 langfuse 异步上报。trace_id=%s", sleep_time, trace_id)
    time.sleep(sleep_time)
    tr = langfuse_sdk.fetch_trace(trace_id)

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