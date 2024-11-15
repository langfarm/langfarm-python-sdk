# Langfarm

langfarm 是 LLM 应用程序开发的工具集，增加 LLM 应用开发的便利。

# Tongyi 集成 Langfuse

## 准备：本地安装部署 Langfuse

请参考：[Langfuse 快速开始](http://chenlb.com/llm/langfuse/getting-started.html)

## 使用 Langchain 的 Callback

使用示例

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
