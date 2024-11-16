# Langfarm

langfarm 是 LLM 应用程序开发的工具集，增加 LLM 应用开发的便利。

## Tongyi 集成 Langfuse

### 准备：本地安装部署 Langfuse

请参考：[Langfuse 快速开始](http://chenlb.com/llm/langfuse/getting-started.html)

### 使用 Langchain 的 Callback

安装依赖
```bash
pip install langchain-community
pip install langfarm
# 加载 .env 配置
pip install python-dotenv
```

使用示例

重点是 `from langfarm.hooks.langfuse.callback import CallbackHandler` 代替 `from langfuse.callback import CallbackHandler`

```python
import time

from dotenv import load_dotenv
from langchain_community.llms import Tongyi
from langfarm.hooks.langfuse.callback import CallbackHandler

# 加载 .env 配置
load_dotenv()

llm = Tongyi(model="qwen-plus")
langfuse_handler = CallbackHandler()

query = '请用50个字描写春天的景色。'
result = llm.invoke(query, config={"callbacks": [langfuse_handler]})

print(result)
print("等待 5 秒，等待 langfuse 异步上报。")
time.sleep(5)
print("完成！")
```

然后打开 langfuse 界面查看，http://localhost:3000/

### dashscope 使用 observe 也可以取得 token 用量

安装依赖
```bash
pip install dashscope
pip install langfarm
# 加载 .env 配置
pip install python-dotenv
```

使用示例

重点是 `from langfarm.hooks.dashscope import Generation` 代码 `from dashscope import Generation`

```python
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

```