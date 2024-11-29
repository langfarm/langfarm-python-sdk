import logging
import os
import unittest
from typing import Any, List, Union, Dict, Generator

from dashscope.api_entities.dashscope_response import Message, GenerationResponse, GenerationUsage, GenerationOutput
from langfuse.api import ObservationLevel
from langfuse.client import FetchTraceResponse
from langfuse.decorators import observe, langfuse_context
from tenacity import stop_after_attempt, retry, wait_fixed, before_sleep_log, wait_random

from langfarm.hooks.dashscope import Generation
from tests.base import LangfuseSDKTestCase

logger = logging.getLogger(__name__)


class MyException(Exception):
    pass


class MockGeneration(Generation):

    max_fail_cnt = 3
    fail_cnt = 0

    @classmethod
    def _reset_fail_cnt(cls):
        cls.fail_cnt = 0

    @classmethod
    def _do_call(cls, model: str, prompt: Any = None, history: list = None, api_key: str = None,
                 messages: List[Message] = None, plugins: Union[str, Dict[str, Any]] = None, workspace: str = None,
                 **kwargs) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:

        cls.fail_cnt += 1
        if cls.fail_cnt >= cls.max_fail_cnt:
            response = GenerationResponse(
                status_code=200
                , usage=GenerationUsage(input_tokens=20, output_tokens=5)
                , output=GenerationOutput(text='mock for success', finish_reason='done')
            )
        else:
            response = GenerationResponse(
                status_code=429, code='RateLimit', message='mock test rate-limit'
                , usage=GenerationUsage(input_tokens=20, output_tokens=5)
                , output=GenerationOutput(text='mock for rate-limit', finish_reason='done')
            )

        return response


class MockErrorGeneration(Generation):

    @classmethod
    def _do_call(cls, model: str, prompt: Any = None, history: list = None, api_key: str = None,
                 messages: List[Message] = None, plugins: Union[str, Dict[str, Any]] = None, workspace: str = None,
                 **kwargs) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:

        response = GenerationResponse(
            status_code=400, code='BadRequest', message='mock test bad request'
        )
        return response


class MyTestCase(LangfuseSDKTestCase):

    def setUp(self):
        super().setUp()
        self.cnt = 0
        MockGeneration._reset_fail_cnt()

    @retry(stop=stop_after_attempt(4), wait=wait_fixed(1)+wait_random(0, 2), before_sleep=before_sleep_log(logger, logging.WARNING))
    def raise_my_exception(self):
        self.cnt += 1
        if self.cnt >= 3:
            logger.info("cnt = %s", self.cnt)
        else:
            raise MyException(f"Fail cnt={self.cnt}")

    def test_demo_retry(self):
        logger.info("start demo_retry")
        try:
            self.raise_my_exception()
        except Exception as e:
            logger.error("error %s", e)

        retry_stat = self.raise_my_exception.statistics
        logger.info(retry_stat)
        assert retry_stat['attempt_number'] == 3
        assert retry_stat['idle_for'] >= 2

    @observe(as_type="generation")
    def tongyi_gen(self, query: str, model_name: str, max_retries: int = 10) -> str:
        response = MockGeneration.call(
            api_key=os.getenv('DASHSCOPE_API_KEY'),
            model=model_name,
            prompt=query,
            max_retries=max_retries,
        )
        if response.status_code == 200:
            if hasattr(response.output, "text"):
                return response.output.text
            else:
                # result_format="message"
                return response.output.choices[0].message.content
        else:
            return ''

    @observe()
    def test_dashscope_retry(self):
        MockGeneration.max_fail_cnt = 3
        logger.info("start dashscope_retry")
        query = 'start dashscope retry'
        output = self.tongyi_gen(query, 'qwen-plus')
        logger.info("output=%s", output)
        langfuse_context.update_current_trace(
            input=query, output=output
        )
        langfuse_context.flush()

        trace_id = langfuse_context.get_current_trace_id()

        trace: FetchTraceResponse = self.langfuse_sdk.fetch_trace(trace_id)
        # print(trace)
        observations = trace.data.observations
        assert observations
        assert len(observations) > 0
        obs = observations[0]
        assert obs
        assert obs.metadata
        assert obs.level == ObservationLevel.WARNING
        assert 'run_cnt' in obs.metadata
        assert obs.metadata['run_cnt'] == 3
        assert 'idle_second' in obs.metadata
        assert obs.metadata['idle_second'] >= 2
        assert 'max_retries' in obs.metadata

    @observe()
    def test_dashscope_no_retry(self):
        MockGeneration.max_fail_cnt = 1
        logger.info("start dashscope_retry")
        query = 'start dashscope retry'
        output = self.tongyi_gen(query, 'qwen-plus')
        logger.info("output=%s", output)
        langfuse_context.update_current_trace(
            input=query, output=output
        )
        langfuse_context.flush()

        trace_id = langfuse_context.get_current_trace_id()
        trace: FetchTraceResponse = self.langfuse_sdk.fetch_trace(trace_id)
        # print(trace)
        observations = trace.data.observations
        assert observations
        assert len(observations) > 0
        obs = observations[0]
        assert obs
        assert obs.metadata is None
        assert obs.level == ObservationLevel.DEFAULT

    @observe()
    def test_dashscope_over_max_retry(self):
        MockGeneration.max_fail_cnt = 4
        logger.info("start dashscope_retry")
        query = 'start dashscope retry'
        output = self.tongyi_gen(query, 'qwen-plus', 3)
        logger.info("output=%s", output)
        langfuse_context.update_current_trace(
            input=query, output=output
        )
        langfuse_context.flush()

        trace_id = langfuse_context.get_current_trace_id()
        trace: FetchTraceResponse = self.langfuse_sdk.fetch_trace(trace_id)
        # print(trace)
        observations = trace.data.observations
        assert observations
        assert len(observations) > 0
        obs = observations[0]
        assert obs
        assert obs.metadata
        assert obs.level == ObservationLevel.ERROR
        assert 'run_cnt' in obs.metadata
        assert obs.metadata['run_cnt'] == 3
        assert 'idle_second' in obs.metadata
        assert obs.metadata['idle_second'] >= 2
        assert 'max_retries' in obs.metadata

        # error
        assert 'status_code' in obs.metadata
        assert obs.metadata['status_code'] == 429
        assert 'err_code' in obs.metadata
        assert obs.metadata['err_code'] == 'RateLimit'

        # status_message
        assert obs.status_message

    @observe(as_type="generation")
    def tongyi_fail_gen(self, query: str, model_name: str, max_retries: int = 10) -> str:
        response = MockErrorGeneration.call(
            api_key=os.getenv('DASHSCOPE_API_KEY'),
            model=model_name,
            prompt=query,
            max_retries=max_retries,
        )
        if response.status_code == 200:
            if hasattr(response.output, "text"):
                return response.output.text
            else:
                # result_format="message"
                return response.output.choices[0].message.content
        else:
            return ''

    @observe()
    def test_dashscope_bad_request(self):
        logger.info("start dashscope_retry")
        query = 'start dashscope retry'
        output = self.tongyi_fail_gen(query, 'qwen-plus', 3)
        logger.info("output=%s", output)
        langfuse_context.update_current_trace(
            input=query, output=output
        )
        langfuse_context.flush()

        trace_id = langfuse_context.get_current_trace_id()
        trace: FetchTraceResponse = self.langfuse_sdk.fetch_trace(trace_id)
        print(trace)
        observations = trace.data.observations
        assert observations
        assert len(observations) > 0
        obs = observations[0]
        assert obs
        assert obs.metadata
        assert obs.level == ObservationLevel.ERROR

        # error
        assert 'status_code' in obs.metadata
        assert obs.metadata['status_code'] == 400
        assert 'err_code' in obs.metadata
        assert obs.metadata['err_code'] == 'BadRequest'

        # status_message
        assert obs.status_message


if __name__ == '__main__':
    unittest.main()
