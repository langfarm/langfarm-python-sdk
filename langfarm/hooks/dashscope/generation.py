import json
import logging
from typing import Any, List, Union, Dict, Generator, Callable

from langfuse.decorators import langfuse_context
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

try:
    import dashscope
except ImportError:
    raise ModuleNotFoundError(
        "Please install Dashscope to use this feature: 'pip install dashscope'"
    )

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

    def __init__(self, message: str, response: GenerationResponse):
        self.message = message
        self.response: GenerationResponse = response


class RetryGenerationException(FailedGenerationException):
    pass


class Generation(TongyiGeneration):

    @classmethod
    def response_to_output(cls, result_format: str, response: GenerationResponse) -> str:
        if result_format and "message" == result_format:
            output = response.output.choices[0].message.content
        else:
            output = response.output.text

        return output

    @classmethod
    def _up_generation_observation(cls, model: str, input_query: str, output: str, usage: dict):
        # 解释 token usage
        langfuse_context.update_current_observation(
            name="Dashscope-generation", model=model
            , input=input_query, output=output
            , usage={
                "input": usage['input_tokens']
                , "output": usage['output_tokens']
                , "unit": "TOKENS"
            }
        )

    @classmethod
    def _up_general_generation_observation(cls, input_query: Any, model: str, result_format: str, response: GenerationResponse):
        output = cls.response_to_output(result_format, response)
        cls._up_generation_observation(model, input_query, output, response.usage)

    @classmethod
    def _up_stream_generation_observation(
            cls, input_query: Any, model: str, result_format: str
            , response: Generator[GenerationResponse, None, None], incremental_output: bool = False
    ) -> Generator[GenerationResponse, None, None]:
        last_usage = None
        output = ''

        is_inc = incremental_output
        for chunk in response:
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
    def _up_error_observation(cls, input_query: Any, model: str, response: GenerationResponse):
        level = 'WARNING' if response.status_code == 429 else 'ERROR'
        langfuse_context.update_current_observation(
            name="Dashscope-generation", model=model
            , input=input_query, output=None
            , level=level
            , status_message=json.dumps({
                'status_code': response.status_code
                , 'err_code': response.code
                , 'err_msg': response.message
            }, ensure_ascii=False)
        )

    @classmethod
    def _do_call(cls, model: str, prompt: Any = None, history: list = None, api_key: str = None,
             messages: List[Message] = None, plugins: Union[str, Dict[str, Any]] = None, workspace: str = None,
             **kwargs) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:

        response = super().call(model, prompt, history, api_key, messages, plugins, workspace, **kwargs)

        return response

    @classmethod
    def check_response(cls, resp: Any) -> Any:
        """Check the response from the completion call."""
        if resp["status_code"] == 200:
            return resp
        elif resp["status_code"] in [400, 401]:
            raise FailedGenerationException(
                f"status_code: {resp['status_code']} \n "
                f"code: {resp['code']} \n message: {resp['message']}"
                , response=resp
            )
        else:
            raise RetryGenerationException(
                f"HTTP error occurred: status_code: {resp['status_code']} \n "
                f"code: {resp['code']} \n message: {resp['message']}",
                response=resp,
            )

    @classmethod
    def _up_retry_stat_to_observation(cls, max_retries: int, retry_stat: dict):
        if 'attempt_number' in retry_stat:
            retry_cnt = retry_stat['attempt_number']
            if retry_cnt > 1:
                langfuse_context.update_current_observation(
                    metadata={
                        'retry_cnt': retry_cnt - 1
                        , 'idle_second': retry_stat['idle_for']
                        , 'max_retries': max_retries
                    }
                )

    @classmethod
    def generate_with_retry(cls, max_retries: int, **kwargs: Any) -> GenerationResponse:
        """Use tenacity to retry the completion call."""
        retry_decorator = _create_retry_decorator(max_retries)

        @retry_decorator
        def _generate_with_retry(**_kwargs: Any) -> GenerationResponse:
            resp = cls._do_call(**_kwargs)
            return cls.check_response(resp)

        try:
            response = _generate_with_retry(**kwargs)
        except FailedGenerationException as e:
            response = e.response

        # 记录重试信息
        retry_stat = _generate_with_retry.statistics
        cls._up_retry_stat_to_observation(max_retries, retry_stat)
        return response

    @classmethod
    def stream_generate_with_retry(cls, max_retries: int, **kwargs: Any) -> Generator[GenerationResponse, None, None]:
        """Use tenacity to retry the completion call."""
        retry_decorator = _create_retry_decorator(max_retries)

        @retry_decorator
        def _stream_generate_with_retry(**_kwargs: Any) -> Generator[GenerationResponse, None, None]:
            responses = cls._do_call(**_kwargs)
            for resp in responses:
                yield cls.check_response(resp)

        return _stream_generate_with_retry(**kwargs)

    @classmethod
    def call(cls, model: str, prompt: Any = None, history: list = None, api_key: str = None,
             messages: List[Message] = None, plugins: Union[str, Dict[str, Any]] = None, workspace: str = None,
             **kwargs) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:

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
                max_retries
                , model=model, prompt=prompt, history=history, api_key=api_key, messages=messages
                , plugins=plugins, workspace=workspace
                , **kwargs
            )
            return cls._up_stream_generation_observation(input_query, model, result_format, response, incremental_output)
        else:
            response = cls.generate_with_retry(
                max_retries
                , model=model, prompt=prompt, history=history, api_key=api_key, messages=messages
                , plugins=plugins, workspace=workspace
                , **kwargs
            )
            if response.status_code == 200:
                cls._up_general_generation_observation(input_query, model, result_format, response)
            else:
                cls._up_error_observation(input_query, model, response)

        return response
