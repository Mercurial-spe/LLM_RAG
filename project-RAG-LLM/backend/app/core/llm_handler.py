# backend/app/core/llm_handler.py

from openai import OpenAI
from .. import config  # <-- 保留相对导入，完全没问题！

def call_model_stream(user_prompt: str):
    """封装了调用LLM并流式返回的核心功能"""
    client = OpenAI(
        base_url='https://api-inference.modelscope.cn/v1',
        # 使用最简洁的方式直接赋值
        api_key=config.MODELSCOPE_API_KEY, 
    )

    response = client.chat.completions.create(
        model='ZhipuAI/GLM-4.6',
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': user_prompt}
        ],
        stream=True
    )
    yield from response

# --- 只有当你直接运行这个文件时，下面的代码才会执行 ---
if __name__ == "__main__":
    print("--- [开始] 单独测试 llm_handler.py ---")
    
    # 将执行代码放在这里
    test_prompt = "你好，请介绍一下你自己"
    print(config.MODELSCOPE_API_KEY)
    print(f"用户问题: {test_prompt}")
    print("模型回答: ", end='')

    try:
        stream_response = call_model_stream(test_prompt)
        for chunk in stream_response:
            # 检查 content 是否存在且不为 None
            if chunk.choices[0].delta and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end='', flush=True)
        print() # 结束后换行
    except Exception as e:
        print(f"\n测试出错: {e}")

    print("--- [结束] 测试 llm_handler.py ---")