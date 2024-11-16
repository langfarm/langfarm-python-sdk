from typing import Any, List, Union, Dict, Generator

from langfuse.decorators import langfuse_context

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


class Generation(TongyiGeneration):

    @classmethod
    def response_to_output(cls, result_format: str, response: GenerationResponse) -> str:
        if result_format and "message" == result_format:
            output = response.output.choices[0].message.content
        else:
            output = response.output.text

        return output

    @classmethod
    def _up_current_observation(cls, model: str, input_query: str, output: str, usage: dict):
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
    def _up_general_observation(cls, input_query: Any, model: str, result_format: str, response: GenerationResponse):
        output = cls.response_to_output(result_format, response)
        cls._up_current_observation(model, input_query, output, response.usage)

    @classmethod
    def _up_stream_observation(
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
        cls._up_current_observation(model, input_query, output, last_usage)

    @classmethod
    def call(cls, model: str, prompt: Any = None, history: list = None, api_key: str = None,
             messages: List[Message] = None, plugins: Union[str, Dict[str, Any]] = None, workspace: str = None,
             **kwargs) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:
        response = super().call(model, prompt, history, api_key, messages, plugins, workspace, **kwargs)

        # input
        input_query = None
        if prompt:
            input_query = prompt
        if messages:
            input_query = messages

        # output
        result_format = kwargs.get("result_format")
        incremental_output = kwargs.get("incremental_output", False)
        if isinstance(response, Generator):
            return cls._up_stream_observation(input_query, model, result_format, response, incremental_output)
        else:
            if response.status_code == 200:
                cls._up_general_observation(input_query, model, result_format, response)

        return response
