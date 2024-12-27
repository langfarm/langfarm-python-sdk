import logging

from langfuse.callback import langchain as langfuse_callback
from langfuse.callback.langchain import LangchainCallbackHandler

logger = logging.getLogger(__name__)

try:
    import langchain_core
except ImportError:
    raise ModuleNotFoundError(
        "Please install langchain core to use this feature: 'pip install langchain-core'"
    )

try:
    from langchain_core.outputs import LLMResult
except ImportError:
    LLMResult = None


def _hook_parse_usage(func):
    def _parse_usage(response: LLMResult):
        from langfuse.callback.langchain import _parse_usage_model
        llm_usage = None
        # tongyi usage
        # generations[0][0].generation_info[token_usage]
        if hasattr(response, "generations"):
            for generation in response.generations:
                for generation_chunk in generation:
                    if generation_chunk.generation_info and (
                            "token_usage" in generation_chunk.generation_info
                    ):
                        _usage = _parse_usage_model(
                            generation_chunk.generation_info["token_usage"]
                        )
                        # 只上报3个字段
                        llm_usage = {
                            'input': _usage['input']
                            , 'output': _usage['output']
                            , 'total': _usage['total']
                        }
                        break
        if llm_usage is None:
            # 调用找到使用原来的函数找。
            llm_usage = func(response)
        return llm_usage
    return _parse_usage


hook_func_name = "langfuse.callback.langchain._parse_usage"

try:
    langfuse_parse_usage = langfuse_callback._parse_usage
    langfuse_callback._parse_usage = _hook_parse_usage(langfuse_parse_usage)
    logger.info("hook %s success! can parse 'token_usage'", hook_func_name)
except Exception as e:
    logger.warning("hook %s fail! %s", hook_func_name, e, exc_info=True)


class CompatibleTongyiCallbackHandler(LangchainCallbackHandler):
    pass
