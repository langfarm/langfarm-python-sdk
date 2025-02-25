import logging
from datetime import datetime
from typing import Any, List, Union, Dict, Generator, Callable, Optional

from langfuse.decorators import langfuse_context
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

from langfarm.hooks.misc import retry_stat_to_meta

try:
    import dashscope  # noqa: F401
except ImportError:
    raise ModuleNotFoundError("Please install Dashscope to use this feature: 'pip install dashscope'")

try:
    from dashscope import Generation as TongyiGeneration
    from dashscope.api_entities.dashscope_response import Message, GenerationResponse
except ImportError:
    TongyiGeneration = None
    Message = None
    GenerationResponse = None


logger = logging.getLogger(__name__)


def _create_retry_decorator(max_retries: int) -> Callable[[Any], Any]:
    min_seconds = 1
    max_seconds = 4
    # Wait 2^x * 1 second between each retry starting with
    # 4 seconds, then up to 10 seconds, then 10 seconds afterward
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=min_seconds, max=max_seconds),
        retry=(retry_if_exception_type(RetryGenerationException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


class FailedGenerationException(Exception):
    def __init__(self, message: str, response: GenerationResponse):  # type: ignore
        self.message = message
        self.response = response


class RetryGenerationException(FailedGenerationException):
    pass


class Generation(TongyiGeneration):  # type: ignore
    @classmethod
    def response_to_output(cls, result_format: Optional[str], response: GenerationResponse) -> str:  # type: ignore
        if result_format and "message" == result_format:
            output = response.output.choices[0].message.content
        else:
            output = response.output.text

        return output

    @classmethod
    def _up_generation_observation(cls, model: str, input_query: str, output: str, usage: dict, **kwargs):
        # 解释 token usage
        langfuse_context.update_current_observation(
            name="Dashscope-generation",
            model=model,
            input=input_query,
            output=output,
            usage={"input": usage["input_tokens"], "output": usage["output_tokens"], "unit": "TOKENS"},  # type: ignore
            **kwargs,
        )

    @classmethod
    def _up_general_generation_observation(
        cls,
        input_query: Any,
        model: str,
        result_format: Optional[str],
        response: GenerationResponse,  # type: ignore
        retry_meta: Optional[dict],
    ):
        metadata = None
        level = None
        if retry_meta:
            # 追加 retry 相关 meta
            metadata = {**retry_meta}
            # 有 retry 按 warn 算
            level = "WARNING"
        if response.status_code == 200:
            output = cls.response_to_output(result_format, response)
            cls._up_generation_observation(model, input_query, output, response.usage, level=level, metadata=metadata)
        else:
            cls._up_error_observation(input_query, model, response, metadata)

    @classmethod
    def _up_stream_generation_observation(
        cls,
        input_query: Any,
        model: str,
        result_format: Optional[str],
        response: Generator[GenerationResponse, None, None],  # type: ignore
        incremental_output: bool = False,
    ) -> Generator[GenerationResponse, None, None]:  # type: ignore
        last_usage = None
        is_first = True
        output = ""

        is_inc = incremental_output
        for chunk in response:
            if is_first:
                langfuse_context.update_current_observation(completion_start_time=datetime.now())
                is_first = False
            last_usage = chunk.usage
            chunk_output = cls.response_to_output(result_format, chunk)
            if is_inc:
                # 增量输出，需要拼接
                output += chunk_output
            else:
                output = chunk_output

            # 生成 response 的 Generator
            yield chunk

        # 没有 usage 加上空的
        if last_usage is None:
            last_usage = {"input_tokens": 0, "output_tokens": 0}

        # 解释 token usage
        cls._up_generation_observation(model, input_query, output, last_usage)

    @classmethod
    def _up_error_observation(
        cls,
        input_query: Any,
        model: str,
        response: GenerationResponse,  # type: ignore
        metadata: Optional[dict] = None,
    ):
        level = "ERROR"
        err_meta = {"status_code": response.status_code, "err_code": response.code}
        if metadata:
            err_meta.update(metadata)
        langfuse_context.update_current_observation(
            name="Dashscope-generation",
            model=model,
            input=input_query,
            output=None,
            level=level,
            status_message=response.message,
            metadata=err_meta,
        )

    @classmethod
    def _do_call(
        cls,
        model: str,
        prompt: Any = None,
        history: Optional[list] = None,
        api_key: Optional[str] = None,
        messages: Optional[List[Message]] = None,  # type: ignore
        plugins: Optional[Union[str, Dict[str, Any]]] = None,
        workspace: Optional[str] = None,
        **kwargs,
    ) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:  # type: ignore
        response = super().call(model, prompt, history, api_key, messages, plugins, workspace, **kwargs)

        return response

    @classmethod
    def check_response(cls, resp: Any) -> Any:
        """Check the response from the completion call."""
        if resp["status_code"] == 200:
            return resp
        elif resp["status_code"] in [400, 401]:
            raise FailedGenerationException(
                f"status_code: {resp['status_code']} \n code: {resp['code']} \n message: {resp['message']}",
                response=resp,
            )
        else:
            raise RetryGenerationException(
                f"HTTP error occurred: status_code: {resp['status_code']} \n "
                f"code: {resp['code']} \n message: {resp['message']}",
                response=resp,
            )

    @classmethod
    def generate_with_retry(cls, max_retries: int, **kwargs: Any) -> tuple[GenerationResponse, Optional[dict]]:  # type: ignore
        """Use tenacity to retry the completion call."""
        retry_decorator = _create_retry_decorator(max_retries)

        @retry_decorator
        def _generate_with_retry(**_kwargs: Any) -> GenerationResponse:  # type: ignore
            resp = cls._do_call(**_kwargs)
            return cls.check_response(resp)

        try:
            response = _generate_with_retry(**kwargs)
        except FailedGenerationException as e:
            response = e.response

        # 记录重试信息
        retry_stat = _generate_with_retry.statistics
        return response, retry_stat_to_meta(max_retries, retry_stat)

    @classmethod
    def stream_generate_with_retry(cls, max_retries: int, **kwargs: Any) -> Generator[GenerationResponse, None, None]:  # type: ignore
        """Use tenacity to retry the completion call."""
        retry_decorator = _create_retry_decorator(max_retries)

        @retry_decorator
        def _stream_generate_with_retry(**_kwargs: Any) -> Generator[GenerationResponse, None, None]:  # type: ignore
            responses = cls._do_call(**_kwargs)
            for resp in responses:
                yield cls.check_response(resp)

        return _stream_generate_with_retry(**kwargs)

    @classmethod
    def call(
        cls,
        model: str,
        prompt: Any = None,
        history: Optional[list] = None,
        api_key: Optional[str] = None,
        messages: Optional[List[Message]] = None,  # type: ignore
        plugins: Optional[Union[str, Dict[str, Any]]] = None,
        workspace: Optional[str] = None,
        **kwargs,
    ) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:  # type: ignore
        # input
        input_query = None
        if prompt:
            input_query = prompt
        if messages:
            input_query = messages

        # output
        result_format = kwargs.get("result_format")
        incremental_output = kwargs.get("incremental_output", False)

        # is stream
        stream = kwargs.get("stream", False)
        max_retries = kwargs.pop("max_retries", 10)
        if stream:
            response = cls.stream_generate_with_retry(
                max_retries,
                model=model,
                prompt=prompt,
                history=history,
                api_key=api_key,
                messages=messages,
                plugins=plugins,
                workspace=workspace,
                **kwargs,
            )
            return cls._up_stream_generation_observation(
                input_query, model, result_format, response, incremental_output
            )
        else:
            response, retry_stat = cls.generate_with_retry(
                max_retries,
                model=model,
                prompt=prompt,
                history=history,
                api_key=api_key,
                messages=messages,
                plugins=plugins,
                workspace=workspace,
                **kwargs,
            )
            cls._up_general_generation_observation(input_query, model, result_format, response, retry_stat)
            return response
