import os
import time

from dotenv import load_dotenv
from langfuse.decorators import observe, langfuse_context
from langfarm.hooks.dashscope import Generation

load_dotenv()


@observe(as_type="generation")
def tongyi_generation(model_name: str, query: str) -> str:
    response = Generation.call(
        api_key=os.getenv('DASHSCOPE_API_KEY'),
        model=model_name,
        prompt=query,
        result_format="message"
    )

    if response.status_code == 200:
        if response.output.text is not None:
            return response.output.text
        else:
            # result_format="message"
            return response.output.choices[0].message.content
    else:
        tip = "请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code"
        raise Exception(
            f"HTTP返回码：{response.status_code}；错误码：{response.code}；错误信息：{response.message}。{tip}")


@observe()
def dashscope_hook_call(query: str) -> str:
    output = tongyi_generation("qwen-plus", query)
    langfuse_context.update_current_trace(input=query, output=output)
    return output


if __name__ == '__main__':
    input_query = "请用50个字描写秋天的景色。"
    result = dashscope_hook_call(input_query)
    print(result)
    print("等待 2 秒，等待 langfuse 异步上报。")
    time.sleep(2)
    print("完成！")
