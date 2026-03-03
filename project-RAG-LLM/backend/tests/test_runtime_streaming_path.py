import sys
import types
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 该测试仅验证 AgentRuntime.stream_messages 的控制流，避免在导入阶段要求完整 LLM 依赖
if "langchain_ollama" not in sys.modules:
    stub_module = types.ModuleType("langchain_ollama")

    class _ChatOllama:  # pragma: no cover
        pass

    stub_module.ChatOllama = _ChatOllama
    sys.modules["langchain_ollama"] = stub_module

from app.agents.runtime import AgentRuntime


class _FakeGraph:
    def __init__(self):
        self.stream_calls = 0
        self.invoke_calls = 0

    def stream(self, *_args, **_kwargs):
        self.stream_calls += 1
        yield {"orchestrator": {}}
        yield {"respond": {}}

    def get_state(self, *_args, **_kwargs):
        return SimpleNamespace(
            values={
                "messages": [{"role": "user", "content": "q"}],
                "tool_results": [],
                "artifacts": {},
            }
        )

    def invoke(self, *_args, **_kwargs):
        self.invoke_calls += 1
        return {}


def _build_runtime_for_test():
    runtime = AgentRuntime.__new__(AgentRuntime)
    runtime.session_id = "s1"
    runtime.temperature = 0.2
    runtime.top_k = 5
    runtime.messages_to_keep = 6
    runtime.max_tokens = 512
    runtime.use_web_search = False
    runtime.llm_model = "mock-model"
    runtime.graph = _FakeGraph()
    return runtime


def test_stream_messages_uses_single_graph_execution_path():
    runtime = _build_runtime_for_test()
    runtime._stream_respond = lambda _state: iter([{"type": "text", "content": "hello world"}])

    chunks = list(runtime.stream_messages("q", thread_id="thread-1"))

    assert runtime.graph.stream_calls == 1
    assert runtime.graph.invoke_calls == 0
    assert chunks == [{"type": "text", "content": "hello world"}]
