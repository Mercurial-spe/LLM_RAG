# 程序的入口， 这里只是个测试 ，来说明项目大概结构， 后面应该会全改掉
from app.core.llm_handler import call_model_stream 

if __name__ == "__main__":
    print("--- [开始] 单独测试 llm_handler.py ---")
    
    # 将执行代码放在这里
    test_prompt = "你好，请介绍一下你自己"
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