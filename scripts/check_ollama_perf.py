#!/usr/bin/env python3
"""
检查 Ollama 性能和并发能力
"""

import time
import requests
import concurrent.futures
from statistics import mean, median

OLLAMA_HOST = "http://localhost:11434"
MODEL = "bge-m3:latest"
TEST_TEXT = "This is a test sentence for embedding performance measurement." * 10

def single_embed():
    """单次 embedding 请求"""
    start = time.time()
    resp = requests.post(
        f"{OLLAMA_HOST}/api/embeddings",
        json={"model": MODEL, "prompt": TEST_TEXT},
        timeout=30
    )
    resp.raise_for_status()
    return time.time() - start

def test_single_thread():
    """测试单线程性能"""
    print("=" * 60)
    print("单线程性能测试（10次请求）")
    print("=" * 60)
    
    times = []
    for i in range(10):
        t = single_embed()
        times.append(t)
        print(f"  请求 {i+1}: {t:.3f}s")
    
    print(f"\n  平均耗时: {mean(times):.3f}s")
    print(f"  中位数: {median(times):.3f}s")
    print(f"  吞吐量: {1/mean(times):.2f} 请求/秒")
    return mean(times)

def test_concurrent(n=8):
    """测试并发性能"""
    print("\n" + "=" * 60)
    print(f"并发性能测试（{n}并发请求）")
    print("=" * 60)
    
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as executor:
        futures = [executor.submit(single_embed) for _ in range(n)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    total_time = time.time() - start
    
    print(f"  总耗时: {total_time:.3f}s")
    print(f"  平均每请求: {mean(results):.3f}s")
    print(f"  吞吐量: {n/total_time:.2f} 请求/秒")
    
    if total_time < mean(results) * n * 0.8:
        print("  ✅ Ollama 支持并发处理")
    else:
        print("  ⚠️  Ollama 似乎是串行处理（有锁）")
    
    return n/total_time

def check_ollama_info():
    """检查 Ollama 信息"""
    print("=" * 60)
    print("Ollama 系统信息")
    print("=" * 60)
    
    try:
        # 获取版本
        resp = requests.get(f"{OLLAMA_HOST}/api/version")
        print(f"  版本: {resp.json().get('version', 'unknown')}")
    except:
        print("  无法获取版本信息")
    
    try:
        # 获取模型列表
        resp = requests.get(f"{OLLAMA_HOST}/api/tags")
        models = resp.json().get('models', [])
        print(f"  已加载模型数: {len(models)}")
        for m in models:
            if MODEL in m.get('name', ''):
                size = m.get('size', 0) / 1024 / 1024
                print(f"  - {m['name']}: {size:.1f} MB")
    except Exception as e:
        print(f"  无法获取模型信息: {e}")

if __name__ == "__main__":
    check_ollama_info()
    
    single_time = test_single_thread()
    throughput_4 = test_concurrent(4)
    throughput_8 = test_concurrent(8)
    throughput_16 = test_concurrent(16)
    
    print("\n" + "=" * 60)
    print("优化建议")
    print("=" * 60)
    
    if throughput_16 < throughput_4 * 1.5:
        print("""
⚠️  检测到 Ollama 并发处理能力有限！

建议优化方案：

1. 【推荐】启动多个 Ollama 实例进行负载均衡：
   
   # 实例1（默认端口 11434）
   OLLAMA_HOST=0.0.0.0:11434 ollama serve &
   
   # 实例2（端口 11435）
   OLLAMA_HOST=0.0.0.0:11435 ollama serve &
   
   # 实例3（端口 11436）
   OLLAMA_HOST=0.0.0.0:11436 ollama serve &
   
   然后在 .env 中配置：
   KB_EMBEDDING_HOSTS=http://localhost:11434,http://localhost:11435,http://localhost:11436

2. 使用 GPU 加速 Ollama（如果可用）：
   
   # 检查 Ollama 是否使用 GPU
   ollama ps
   
   # 确保模型加载到 GPU
   CUDA_VISIBLE_DEVICES=0 ollama serve

3. 使用更轻量的 embedding 模型：
   - nomic-embed-text (768维，更快)
   - all-minilm (384维，最快)

4. 减少 PDF 处理的并发线程数（避免过度竞争）：
   KB_PDF_WORKERS=4
""")
    else:
        print(f"\n✅ Ollama 并发性能良好！可以继续使用当前配置。")
        print(f"   建议线程数: {min(16, int(throughput_16 / throughput_4 * 4))}")
