from typing import Union


def retry_stat_to_meta(max_retries: int, retry_stat: dict) -> Union[dict, None]:
    retry_meta = None
    if "attempt_number" in retry_stat:
        retry_cnt = retry_stat["attempt_number"]
        if retry_cnt > 1:
            retry_meta = {"run_cnt": retry_cnt, "idle_second": retry_stat["idle_for"], "max_retries": max_retries}
    return retry_meta
