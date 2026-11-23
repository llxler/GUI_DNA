# 本地解码登记

2026-11-23，开始生成之前登记。Qwen/Qwen2.5-0.5B-Instruct 缓存版本 7ae557604adf67be50417f59c2c2f167def9a775，Transformers 本地加载 float16 SDPA。每次一条消息数组，使用原生 apply_chat_template(add_generation_prompt=True)，保留完整上下文。贪心解码，do_sample=False，max_new_tokens=768，batch size 1。每项仅生成一次，无修复或重采。06:06 UTC 后停止新增生成。输出包括原始文本、token ID、停止原因、输入长度及输入哈希。两项目分别计数。
