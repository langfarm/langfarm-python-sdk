from typing import Any, Dict, Generator, List, Union

from dashscope.api_entities.dashscope_response import (
    GenerationOutput,
    GenerationResponse,
    GenerationUsage,
    Message,
)

from langfarm.hooks.dashscope import Generation


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
