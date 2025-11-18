import os
import tiktoken

# 1. 设置环境变量，指向你存放编码文件的文件夹路径
#    请将 "path/to/your/tiktoken_cache" 替换为你的实际路径
#    例如：r"C:\my_projects\tiktoken_cache" 或 "/home/user/tiktoken_cache"


# (可选) 验证文件是否存在
expected_file_path = os.path.join(tiktoken_cache_dir, "9b5ad71b2ce5302211f9c61530b329a4922fc6a4")
if not os.path.exists(expected_file_path):
    print(f"警告：在缓存目录 {tiktoken_cache_dir} 中未找到所需的编码文件 {expected_file_path}")
    # 在这里你可以根据需要决定是继续（可能会失败）还是中止

# 2. 现在可以正常加载编码器，tiktoken 会从你指定的目录加载文件
try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
    
    # 3. 正常使用
    text = "Hello, nice to meet you"
    tokens = tokenizer.encode(text)
    
    print(f"文本: {text}")
    print(f"Tokens: {tokens}")
    print(f"Token 数量: {len(tokens)}")

except Exception as e:
    print(f"加载 tiktoken 编码器时出错: {e}")
    print("请确保 TIKTOKEN_CACHE_DIR 环境变量设置正确，并且文件已按要求重命名并放置在指定目录中。")