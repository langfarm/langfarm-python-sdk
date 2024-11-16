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
print("等待 2 秒，等待 langfuse 异步上报。")
time.sleep(2)
print("完成！")
