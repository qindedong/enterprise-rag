"""
Locust 性能压测脚本

用法:
    cd backend
    locust -f perf/locustfile.py --host=http://127.0.0.1:8000
"""
import time

from locust import HttpUser, between, task


class RAGUser(HttpUser):
    """模拟真实用户：登录 → 获取 KB 列表 → RAG 问答"""

    wait_time = between(1, 3)

    def on_start(self):
        """每个用户启动时登录一次"""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "123@qq.com", "password": "12345678"},
        )
        if resp.status_code == 200:
            self.token = resp.json()["data"]["access_token"]
        else:
            self.token = None

    @task(3)
    def rag_chat(self):
        """RAG 问答（权重 3，模拟主要流量）"""
        if not self.token:
            return
        self.client.post(
            "/api/v1/knowledge-bases/eb765c6b-c7c6-452f-9617-8e6f6e07f8dc/chat/sync",
            json={"question": "年假有几天"},
            headers={"Authorization": f"Bearer {self.token}"},
            name="/chat/sync",
            timeout=120,
        )

    @task(2)
    def list_kbs(self):
        """知识库列表（权重 2）"""
        if not self.token:
            return
        self.client.get(
            "/api/v1/knowledge-bases",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/kb/list",
        )

    @task(1)
    def health(self):
        """健康检查（权重 1）"""
        self.client.get("/health", name="/health")
