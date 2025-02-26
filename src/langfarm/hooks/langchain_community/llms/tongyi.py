import logging
from typing import Any

from langfuse.decorators import langfuse_context

from langfarm.hooks.misc import retry_stat_to_meta

logger = logging.getLogger(__name__)

try:
    import langchain_community  # noqa: F401
except ImportError:
    raise ModuleNotFoundError(
        "Please install langchain community to use this feature: 'pip install langchain-community'"
    )

try:
    from langchain_community.llms import tongyi
except ImportError:
    tongyi = None
    raise ModuleNotFoundError(
        "Please install langchain community to use this feature: 'pip install langchain-community'"
    )


def generate_with_retry(llm: tongyi.Tongyi, **kwargs: Any) -> Any:  # type: ignore
    """Use tenacity to retry the completion call."""
    retry_decorator = tongyi._create_retry_decorator(llm)  # type: ignore

    @retry_decorator
    def _generate_with_retry(**_kwargs: Any) -> Any:
        resp = llm.client.call(**_kwargs)
        return tongyi.check_response(resp)  # type: ignore

    _err = None
    response = None
    try:
        response = _generate_with_retry(**kwargs)
        level = "WARNING"
    except Exception as err:
        _err = err
        level = "ERROR"

    # 记录重试信息
    retry_stat = _generate_with_retry.statistics
    retry_meta = retry_stat_to_meta(llm.max_retries, retry_stat)
    if retry_meta:
        langfuse_context.update_current_observation(level=level, metadata=retry_meta)

    if _err:
        raise _err
    else:
        return response


def _hook_generate_with_retry():
    return generate_with_retry


hook_func_name = "langchain_community.llms.tongyi.generate_with_retry"

try:
    tongyi_generate_with_retry = tongyi.generate_with_retry
    tongyi.generate_with_retry = _hook_generate_with_retry()
    logger.info("hook %s success! can report retry stat message", hook_func_name)
except Exception as e:
    logger.warning("hook %s fail! %s", hook_func_name, e, exc_info=True)


class Tongyi(tongyi.Tongyi):
    pass
