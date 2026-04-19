## 文本向量计算api ：
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 百炼服务的base_url
)

completion = client.embeddings.create(
    model="text-embedding-v4",
    input='衣服的质量杠杠的，很漂亮，不枉我等了这么久啊，喜欢，以后还来这里买',
    dimensions=1024, # 指定向量维度（仅 text-embedding-v3及 text-embedding-v4支持该参数）
    encoding_format="float"
)

print(completion.model_dump_json())



## 重排序api:
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank' \
--header "Authorization: Bearer $DASHSCOPE_API_KEY" \
--header 'Content-Type: application/json' \
--data '{
    "model": "qwen3-rerank",
    "input":{
         "query": "什么是文本排序模型",
         "documents": [
         "文本排序模型广泛用于搜索引擎和推荐系统中，它们根据文本相关性对候选文本进行排序",
         "量子计算是计算科学的一个前沿领域",
         "预训练语言模型的发展给文本排序模型带来了新的进展"
         ]
    },
    "parameters": {
        "return_documents": true,
        "top_n": 5
    }
}'

输出示例
{
    "status_code": 200,
    "request_id": "4b0805c0-6b36-490d-8bc1-4365f4c89905",
    "code": "",
    "message": "",
    "output": {
        "results": [
            {
                "index": 0,
                "relevance_score": 0.9334521178273196,
                "document": {
                    "text": "文本排序模型广泛用于搜索引擎和推荐系统中，它们根据文本相关性对候选文本进行排序"
                }
            },
            {
                "index": 2,
                "relevance_score": 0.34100082626411193,
                "document": {
                    "text": "预训练语言模型的发展给文本排序模型带来了新的进展"
                }
            }
        ]
    },
    "usage": {
        "total_tokens": 79
    }
}
