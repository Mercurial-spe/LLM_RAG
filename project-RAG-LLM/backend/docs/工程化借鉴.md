基于对代码库的深入分析，现在我来为你生成一份结构化的学习笔记。

---

# 📚 crewAI 源码学习笔记：Agent 工作流与编排机制

> 仓库：[crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | 分析提交：`1ac5801`

---

## 一、整体架构概览

crewAI 的架构分为两个核心层次：

```
┌─────────────────────────────────────────────────────────┐
│                      Flow 层（宏观编排）                   │
│   Flow + @start/@listen/@router  →  状态机式流程控制      │
│─────────────────────────────────────────────────────────��
│                      Crew 层（微观执行）                   │
│   Crew + Agent + Task  →  多 Agent 协作任务执行           │
└─────────────────────────────────────────────────────────┘
```

**设计理念**：Flow 是外层编排者（定义业务流程走向），Crew 是内层执行单元（完成具体 AI 任务）。两者可以嵌套组合，构建复杂的生产级 Agent 应用。

---

## 二、核心概念：Crew（Agent 协作单元）

### 2.1 Crew 的数据模型

```python
class Crew(FlowTrackable, BaseModel):
    """
    核心字段：
    - agents: list[BaseAgent]        # 参与的 Agent 列表
    - tasks:  list[Task]             # 要执行的任务列表
    - process: Process               # 流程模式（sequential / hierarchical）
    - memory: bool | Any             # 是否开启统一记忆系统
    - cache: bool                    # 是否开启工具结果缓存（默认 True）
    - planning: bool                 # 是否在执行前自动规划
    - manager_llm: str               # 层次模式下 manager 使用的 LLM
    - manager_agent: BaseAgent       # 自定义 manager agent
    - max_rpm: int                   # 每分钟最大请求数（限流）
    - verbose: bool                  # 是否输出详细日志
    - step_callback / task_callback  # 每步/每任务执行后的回调钩子
    """
```

### 2.2 两种流程模式（Process）

#### ✅ Sequential（顺序，默认）

```
Task1 → Task2 → Task3 → ... → CrewOutput
  └── 上一个 task 的输出自动作为下一个 task 的 context
```

```python
# 内部实现：顺序执行
def _run_sequential_process(self) -> CrewOutput:
    """Executes tasks sequentially and returns the final output."""
    # → 调用 _execute_tasks(self.tasks)
    # → 逐个 task 获取 context，调用 agent.execute_task()
    # → 收集所有 task_output，构建 CrewOutput
```

#### ✅ Hierarchical（层次/管理者委派）

```
Manager Agent
    ├── 分析任务 → 委派给 Agent A
    ├── 验证输出 → 可重新委派
    └── 汇总最终结果 → CrewOutput
```

```python
def _run_hierarchical_process(self) -> CrewOutput:
    """Creates and assigns a manager agent to complete the tasks."""
    self._create_manager_agent()   # 自动创建 or 使用自定义 manager
    return self._execute_tasks(self.tasks)
```

**关键点**：

- 需要设置 `process=Process.hierarchical` + `manager_llm="gpt-4o"`
- Manager Agent 负责：任务分配、结果验证、重新委派
- 任务不预先绑定 Agent，由 Manager 动态决定

### 2.3 Crew 启动方式（kickoff 家族）

| 方法                                    | 说明                     |
| --------------------------------------- | ------------------------ |
| `kickoff(inputs)`                     | 同步启动                 |
| `kickoff_async(inputs)`               | 异步启动（线程包装同步） |
| `akickoff(inputs)`                    | 原生 async/await 启动    |
| `kickoff_for_each(inputs_list)`       | 批量输入，串行执行       |
| `kickoff_for_each_async(inputs_list)` | 批量输入，并行执行       |

```python
def kickoff(self, inputs=None, input_files=None) -> CrewOutput:
    # 1. 如果开启 stream，返回 CrewStreamingOutput（流式）
    # 2. 设置 baggage context（可观测性追踪）
    # 3. 输入插值 → 任务规划（可选）→ 执行流程
    # 4. 内存存储 → 返回 CrewOutput
```

---

## 三、核心概念：Agent（执行单元）

### 3.1 Agent 的继承体系

```
BaseModel (Pydantic)
  └── BaseAgent (ABC)          # 定义抽象接口：execute_task / create_agent_executor
        └── Agent              # 完整实现，含 LLM + 工具 + 记忆
              └── LiteAgent    # 轻量版，无 crew 绑定
```

### 3.2 Agent 执行任务的流程

```python
def execute_task(self, task, context=None, tools=None):
    # 1. handle_reasoning(self, task)       # 是否需要推理注入
    # 2. task_prompt = task.prompt()        # 构建任务 prompt
    # 3. task_prompt += context             # 注入上下文
    # 4. 查询 Memory（相关历史��忆）
    # 5. handle_knowledge_retrieval(...)    # 知识库检索
    # 6. prepare_tools(self, tools, task)   # 准备工具
    # 7. emit AgentExecutionStartedEvent
    # 8. executor.invoke(task_prompt)       # 核心：进入 ReAct 执行循环
    # 9. emit AgentExecutionCompletedEvent
    # 10. save_last_messages(self)          # 保存消息历史
```

### 3.3 ReAct 执行循环（关键机制）

crewAI 实现了经典的 **ReAct（Reason + Act）** 模式：

```
┌─────────────────────────────────────────────────────┐
│                  ReAct 循环                           │
│                                                       │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐   │
│  │  Thought │ →  │  Action  │ →  │  Observation │   │
│  │  (LLM)   │    │  (Tool)  │    │  (结果)       │   │
│  └──────────┘    └──────────┘    └──────────��───┘   │
│       ↑                                    │          │
│       └────────────────────────────────────┘          │
│  直到 LLM 输出 "Final Answer" → AgentFinish           │
└─────────────────────────────────────────────────────┘
```

```python
def _invoke_loop_react(self) -> AgentFinish:
    """ReAct 文本解析模式（传统方式）"""
    formatted_answer = None
    while not isinstance(formatted_answer, AgentFinish):
        # 1. 检查是否超过 max_iter
        # 2. 限流检查（RPM）
        # 3. get_llm_response() → 获取 LLM 输出
        # 4. parse_llm_output() → 解析为 AgentAction or AgentFinish
        # 5. 如果是 AgentAction → execute_tool_and_check_finality()
        # 6. 将工具结果追加到 messages → 继续循环
    return formatted_answer
```

**两种工具调用模式**：

- **ReAct 文本解析**：LLM 输出 `Action: tool_name / Action Input: {...}` 格式，正则解析
- **Native Function Calling**：LLM 原生支持（如 GPT-4），直接返回结构化 tool_calls

```python
def _invoke_loop(self) -> AgentFinish:
    # 自动选择：Native 还是 ReAct
    use_native_tools = (
        self.llm.supports_function_calling() and self.original_tools
    )
    if use_native_tools:
        return self._invoke_loop_native_tools()
    return self._invoke_loop_react()   # 回退到 ReAct
```

---

## 四、核心概念：Flow（宏观流程编排）

这是 crewAI 最具特色的设计，用**事件驱动的装饰器**替代传统的命令式流程控制。

### 4.1 三大核心装饰器

```python
# 1. @start() —— 流程入口（可多个，并行启动）
@start()
def begin(self):
    return "initial data"

# 2. @listen(method) —— 监听某步骤完成后触发
@listen(begin)
def process(self, data):          # data 是 begin() 的返回值
    return f"processed: {data}"

# 3. @router(method) —— 条件路由，返回字符串标签
@router(process)
def route(self):
    if self.state.success:
        return "success"          # 触发 @listen("success") 的方法
    return "failed"
```

### 4.2 Flow 的执行机制（FlowMeta 元类）

```python
class FlowMeta(type):
    """在类定义时自动扫描所有方法的装饰器，构建执行图"""
    # 收集 start_methods、listeners（触发关系图）、routers
    # cls._start_methods = [...]
    # cls._listeners = {"method_name": ("OR"/"AND", [trigger_methods])}
    # cls._routers = {...}
    # cls._router_paths = {"method": ["label1", "label2"]}
```

**执行拓扑**：`@start` → 触发 `@listen` → 若有 `@router` → 根据返回值触发对应 `@listen("label")`

### 4.3 Flow 的状态管理

两种状态模式（借鉴自 Redux/Pydantic 理念）：

```python
# 模式一：非结构化（dict，灵活）
class MyFlow(Flow):                         # 无泛型参数
    @start()
    def begin(self):
        self.state["key"] = "value"         # 直接赋值

# 模式二：结构化（Pydantic BaseModel，类型安全）
class AppState(BaseModel):
    topic: str = ""
    results: list[str] = []
    is_done: bool = False

class MyFlow(Flow[AppState]):               # 泛型参数
    @start()
    def begin(self):
        self.state.topic = "AI"             # 类型检查 + 自动补全
        self.state.results.append("item")
```

**状态生命周期**：

```
初始化 → 方法修改 → 自动传递 → [可持久化] → 最终状态
   ↑                              ↓
  kickoff()            FlowPersistence（SQLite 等）
```

### 4.4 条件组合：or_ 和 and_

```python
from crewai.flow.flow import Flow, listen, start, or_, and_

class MyFlow(Flow):
    @listen(or_(method_a, method_b))    # 任一完成即触发
    def process_either(self):
        ...

    @listen(and_(method_a, method_b))   # 两者都完成才触发（并行汇聚）
    def process_both(self):
        ...
```

### 4.5 Flow + Crew 嵌套（生产级模式）

```python
class AppState(BaseModel):
    user_input: str = ""
    research_results: str = ""
    final_report: str = ""

class ProductionFlow(Flow[AppState]):
    @start()
    def gather_input(self):
        self.state.user_input = "AI Ethics"

    @listen(gather_input)
    def run_research_crew(self):
        # 在 Flow 步骤中启动一个 Crew
        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, writing_task],
            process=Process.sequential,
        )
        result = crew.kickoff(inputs={"topic": self.state.user_input})
        self.state.research_results = result.raw

    @listen(run_research_crew)
    def finalize(self):
        self.state.final_report = f"Report: {self.state.research_results}"
```

---

## 五、实验性特性：AgentExecutor as a Flow

一个极具借鉴价值的设计——**把 Agent 的 ReAct 循环本身实现为一个 Flow**：

```python
class AgentExecutor(Flow[AgentReActState], CrewAgentExecutorMixin):
    """将 ReAct 循环表达为 Flow 的事件图"""
    # Flow 状态：
    # AgentReActState: { messages, iterations, current_answer, is_finished }

    @start()
    def initialize_reasoning(self): ...       # 初始化

    @router(...)
    def check_max_iterations(self):           # 检查迭代上限
        if 超限: return "force_final_answer"
        return "continue_reasoning"

    @listen("continue_reasoning")
    def call_llm_and_parse(self): ...         # 调用 LLM

    @router(call_llm_and_parse)
    def route_by_answer_type(self):           # 判断是 Action 还是 Finish
        if AgentAction: return "execute_tool"
        return "agent_finished"

    @listen("execute_tool")
    def execute_tool_action(self): ...        # 执行工具

    @router(execute_tool_action)
    def increment_and_continue(self):
        self.state.iterations += 1
        return "initialized"                  # 循环回去！
```

**这揭示了一个深刻设计原则**：Flow 足够通用，连 Agent 内部的推理循环都可以用它来表达。

---

## 六、记忆系统（Memory）

### 架构演变

旧版（分散）→ 新版（统一 `Memory` 类）：

| 类型     | 旧名称     | 底层存储          | 用途                      |
| -------- | ---------- | ----------------- | ------------------------- |
| 短期记忆 | `short`  | ChromaDB（向量）  | 当次执行的上下文          |
| 长期记忆 | `long`   | SQLite            | �� session 持久化       |
| 实体记忆 | `entity` | ChromaDB          | 人物/概念/地点追踪        |
| 新版统一 | `Memory` | LanceDB + LLM分析 | 自动推断 scope/importance |

### 记忆的工作流

```python
# 任务执行时，Agent 自动：
# 1. 从 Memory 中 recall 相关历史（向量相似度 + 时间衰减 + 重要度）
matches = unified_memory.recall(task.description, limit=5)
memory_str = "\n".join(m.format() for m in matches)
task_prompt += f"\nRelevant memories:\n{memory_str}"

# 2. 执行完毕后，自动保存记忆
# RememberTool: agents 也可以主动调用 "Save to memory" 工具
```

```python
# 开启方式
crew = Crew(
    agents=[...], tasks=[...],
    memory=True,                    # 使用默认 Memory()
    embedder={                      # 可选：自定义 embedding 模型
        "provider": "ollama",
        "config": {"model": "mxbai-embed-large"},
    }
)
```

---

## 七、工具系统（Tools）

Crew 会在执行时动态组装每个 Agent 的工具集：

```python
# Crew 为 Agent 自动注入的工具类型：
# 1. _add_delegation_tools()   → 层次模式下的"委派给其他Agent"工具
# 2. _add_memory_tools()       → RememberTool / RecallTool
# 3. _add_code_execution_tools() → 代码执行工具
# 4. _add_file_tools()         → 文件输入处理
# 5. _add_mcp_tools()          → MCP 协议工具
# 6. _add_platform_tools()     → 平台集成工具
```

---

## 八、事件总线（Event Bus）

crewAI 内置了一个轻量级事件系统，用于可观测性：

```python
# 贯穿整个执行链的关键事件（可订阅用于 logging/tracing）
AgentExecutionStartedEvent   # Agent 开始执行
AgentExecutionCompletedEvent # Agent 执行完成
TaskStartedEvent             # Task 开始
MemoryRetrievalStartedEvent  # 记忆检索开始
MemoryRetrievalCompletedEvent
FlowStartedEvent             # Flow 启动
LiteAgentExecutionStartedEvent
```

---

## 九、项目脚手架模式（@CrewBase 装饰器）

crewAI 推荐的工程化组织方式：

```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

@CrewBase
class MyCrew:
    """YAML 配置驱动的 Crew 定义"""
    agents_config = "config/agents.yaml"   # 角色/目标/背景故事配置
    tasks_config  = "config/tasks.yaml"    # 任务描述/期望输出配置

    @agent
    def researcher(self) -> Agent:         # 装饰器自动收集到 self.agents
        return Agent(config=self.agents_config["researcher"])

    @task
    def research_task(self) -> Task:       # 装饰器自动收集到 self.tasks
        return Task(config=self.tasks_config["research_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,            # 自动从 @agent 收集
            tasks=self.tasks,              # 自动从 @task 收集
            process=Process.sequential,
        )
```

---

## 十、设计模式总结与借鉴要点

### 可借鉴的关键设计决策

| 设计点              | crewAI 的做法                                 | 借鉴价值                 |
| ------------------- | --------------------------------------------- | ------------------------ |
| **流程编排**  | 事件驱动装饰器（@start/@listen/@router）      | 解耦步骤，DAG 自动推导   |
| **状态管理**  | Pydantic BaseModel 作为 Flow 泛型状态         | 类型安全 + 验证 + 序列化 |
| **Agent循环** | ReAct 循环 / Native Function Calling 自动切换 | 兼容不同 LLM 能力        |
| **工具注入**  | Crew 级动态组装，不污染 Agent 定义            | 关注点分离               |
| **记忆系统**  | 统一 Memory 类 + LLM 自动分析重要度           | 智能化记忆管理           |
| **可观测性**  | Event Bus 贯穿全链路                          | 零侵入式追踪             |
| **并发**      | async/await + 同步包装双模式                  | 灵活适配不同调用场景     |
| **配置驱动**  | YAML 配置 + @CrewBase 装饰器                  | 配置与代码分离           |

### 核心设计哲学

> **"Flow 优先"**：先定义业务流程的 **状态** 和 **转换关系**，再把具体 AI 能力（Crew/Agent）插入到流程节点中。这与函数式状态机思想高度一致。

---

以上笔记已覆盖 crewAI 中 **Agent 工作流编排** 的所有核心机制，包括 `Flow/Crew/Agent/Task/Memory/Tools/ReAct循环` 的实现原理和代码位置，可直接用于指导你自己的 Agent 项目开发 🎯
