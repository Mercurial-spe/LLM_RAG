# Agent 入门教学文档（2026 主流架构视角，配 LangGraph 例子）

面向对象：正在入门 Agent 的大三计算机学生
学习目标：读完后你能把任何 Agent 项目拆成固定模块，不再“看框架一脸懵”；学 LangChain/LangGraph 时能知道每个概念解决什么问题、该放在哪里。

---

## 0. 你需要的前置心智：Agent 不是“更聪明的聊天”，而是“会跑流程的程序”

**一句话定义（工程视角）**
Agent 是一个“多步闭环程序”：它会反复 **做决策 → 调工具/系统 → 把结果写回状态 → 再决策**，直到任务完成或被终止。

你把它当成“能使用工具的程序”，而不是“会说话的模型”，会立刻清醒很多。

---

## 1. 最小 Agent 闭环：你先把这个跑通，后面所有复杂度都从这里长出来

### 1.1 最小闭环伪代码

```text
state = init(user_input)
loop:
  decision = LLM(state, tool_schemas)
  if decision == "call_tool":
      result = run_tool(decision)
      state = merge(state, result)
  else:
      return decision.final_answer
```

你要记住这里的三个关键点（后面所有架构都在强化它们）：

1. **LLM 只负责“决定下一步做什么”**（它本质上不可靠、也不记忆）
2. **state 是系统的“真记忆”**（能持久化、可回放、可恢复）
3. **tool 是“真的去干活”**（网络、数据库、文件、业务系统）

### 1.2 新手最常见的误区

* 误区 A：把 state 全塞进 prompt，越做越长、越做越乱
* 误区 B：工具直接抛异常，导致整个流程崩掉
* 误区 C：没有“可恢复”，一失败就从头来，用户体验灾难
* 误区 D：流程控制写成一坨 if/else，后期根本没法维护

---

## 2. 主流架构“三层模型”：把复杂 Agent 拆开，你就不会迷茫

你可以把 90% 的 Agent 项目稳定拆成三层：

```
┌──────────────┐
│ 认知层        │  LLM：决定做什么（输出动作/结构化结果）
└──────┬───────┘
       │
┌──────▼───────┐
│ 编排层        │  图/状态机：决定“下一步到哪”，维护全局 state
└──────┬───────┘
       │
┌──────▼───────┐
│ 执行层        │  Tools/Services：访问外部世界（DB/HTTP/文件/业务系统）
└──────────────┘
```

接下来我们按层讲清楚：每层的职责、最容易踩坑的点、以及在 LangGraph 里怎么落地。

---

## 3. 认知层：把 LLM 当“无状态决策器”，别当数据库、更别当后端

### 3.1 认知层到底做什么？

**输入：**

* 当前 state 的关键切片（不要把所有东西都塞给它）
* 工具列表（工具名 + 参数 schema + 描述）
* 一些系统规则（安全、风格、输出格式）

**输出（最常见两类）：**

1. **工具调用意图**：调用哪个工具、参数是什么
2. **最终答案（或结构化输出）**：直接结束

> 认知层的“产物”更像“动作指令”，而不是业务执行结果。

### 3.2 你如何判断认知层设计得好？

✅ 好的设计：

* 模型输出是**可解析、可校验**的（最好是结构化）
* 让模型“做选择”，不要让它“做执行”
* prompt 只放**决策需要的信息**，其余数据留在 state/存储里

❌ 不好的设计：

* 把数据库连接、HTTP 请求、复杂业务逻辑都交给模型“描述”
* 输出格式漂移（今天是 JSON，明天是段落文本）
* 让模型在一次回答里“凭空记住”大量历史细节

### 3.3 入门建议：先把“输出稳定性”当第一优先级

你做课程项目时，经常失败在：

* JSON 解析失败
* 字段缺失/类型不对
* 模型胡编参数

解决思路是：**让输出有 schema**（哪怕你手写校验也行），并且失败要能回到“可恢复的下一步”（这就是编排层的价值）。

---

## 4. 编排层：为什么 2026 主流都在用“图/状态机”，LangGraph 为什么重要

你可以把编排层理解成：**Agent 的操作系统 / 运行时**。
它做三件事：

1. **控制流**：下一步执行哪个节点（LLM？工具？校验？结束？）
2. **状态流转**：state 在每一步如何更新、如何合并
3. **工程能力**：可持久化、可恢复、中断与恢复、流式输出、调试回放

LangGraph 的核心抽象非常适合学习这套体系：

* **Node**：一个步骤（普通 Python 函数）
* **Edge**：步骤之间的连接
* **Conditional Edge**：分支路由逻辑
* **State**：共享状态（强烈建议 TypedDict/Pydantic）
* **Reducer**：规定“状态怎么合并”
* **Checkpointer**：每一步持久化，让流程可恢复
* **Interrupt/Resume**：让流程可以暂停等待人工输入/审批
* **Streaming**：把过程输出给前端/日志

### 4.1 你必须掌握的一个概念：State 是“系统内存”，不是聊天记录

入门时你可以把 state 设计成这几类字段：

* `messages`：对话消息（用于让模型知道上下文）
* `task`：当前任务目标
* `facts`：检索到的资料/事实（结构化存储）
* `plan`：当前计划或子任务列表
* `tool_results`：工具输出（结构化）
* `final`：最终结果

**关键：**模型需要看什么，就从 state 取什么；state 不是 prompt，state 是“真数据”。

---

## 5. 执行层：把 Tools 当成 SpringMVC 的 Controller（这个类比非常好用）

执行层本质是传统后端工程那一套，只是调用方从“前端”变成了“编排层 + 模型决策”。

### 5.1 SpringMVC 映射（强烈建议你用这个记）

* **Tool = Controller**

  * 定义接口签名（参数 schema）
  * 参数校验（类型/必填/范围/枚举）
  * 权限校验（能不能查这个数据、能不能执行这个动作）
  * 异常捕获与统一返回

* **Service = 业务层**

  * 组合业务逻辑
  * 幂等处理（尤其是“可能被重试”的动作）
  * 降级策略（超时怎么办、备用数据源怎么办）

* **Repository = 数据层**

  * DB / 缓存 / 向量库 / 文件存储
  * 查询与持久化

### 5.2 新手一定要改掉的点：不要“异常直接炸穿”

工具调用失败是常态：超时、限流、网络抖动、权限不足……
正确做法是：**工具返回结构化错误，而不是抛异常让流程崩掉**。

建议工具返回类似：

```json
{
  "ok": false,
  "error_code": "DB_TIMEOUT",
  "message": "数据库查询超时",
  "retryable": true
}
```

然后由编排层决定：重试？换数据源？询问用户？结束？

这会让你的 Agent 稳定性提升一个数量级。

---

## 6. 用 LangGraph 把“三层架构”落地：从最简单的图开始

下面给你一个非常“教学友好”的递进路线：每一步只加一个新能力。

> 说明：代码是示意级别（便于你理解结构），你把其中的 “LLM 调用” 替换成 LangChain 的模型调用即可。

---

### 6.1 第 1 步：最小图（LLM 决策 → 工具 → LLM 总结）

**目标：**理解 nodes、edges、state 的基本运行方式。

```python
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage

class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    query: str
    docs: list[str]
    answer: str

def llm_decide(state: State) -> dict:
    user_text = state["messages"][-1].content
    # 教学简化：有“资料/搜索”就认为需要工具
    if "搜索" in user_text or "资料" in user_text:
        return {"query": user_text, "messages": [AIMessage(content="我需要先检索资料。")]}
    return {"answer": "我可以直接回答（示例）。", "messages": [AIMessage(content="无需检索，我直接回答。")]}

def search_tool(state: State) -> dict:
    q = state["query"]
    docs = [f"doc about {q} #1", f"doc about {q} #2"]
    return {"docs": docs}

def llm_write(state: State) -> dict:
    docs = state.get("docs", [])
    answer = "总结：\n" + "\n".join(docs)
    return {"answer": answer, "messages": [AIMessage(content="我已完成总结。")]}

def route(state: State) -> str:
    return "tool" if state.get("query") else "end"

g = StateGraph(State)
g.add_node("decide", llm_decide)
g.add_node("tool", search_tool)
g.add_node("write", llm_write)

g.add_edge(START, "decide")
g.add_conditional_edges("decide", route, {"tool": "tool", "end": END})
g.add_edge("tool", "write")
g.add_edge("write", END)

graph = g.compile()
out = graph.invoke({"messages": [HumanMessage(content="帮我搜索 LangGraph reducer 的资料")]} )
print(out["answer"])
```

你应该观察到的对应关系：

* `llm_decide / llm_write`：认知层（做决定/写输出）
* 图结构：编排层（控制流）
* `search_tool`：执行层（工具）
* `State`：贯穿全局的数据结构

---

### 6.2 第 2 步：把“状态合并”正规化（Reducer 思维）

你会很快发现一个痛点：多节点都要往 `messages` 里加东西，如果你手写 append，很容易乱。
LangGraph 的 reducer（例如 `add_messages`）就是为了解决这种“合并规则”问题。

入门要点：

* 节点只返回“增量更新”
* reducer 负责“怎么合并到全局 state”

这就是为什么上面示例里 `messages` 用了：

```python
messages: Annotated[list[AnyMessage], add_messages]
```

你不用手写 `state["messages"].append(...)`，可维护性会强很多。

---

### 6.3 第 3 步：加上 Checkpointer（让流程可恢复，像“事务快照”）

当你的图变长（10+ 步），你会遇到现实问题：

* 第 7 步工具超时了，能不能从第 7 步继续？
* 用户关掉页面，回来能不能接着跑？
* 你能不能回放调试“第 5 步为什么走错分支”？

这就需要 **checkpoint 持久化**。

在 LangGraph 里你只要在 compile 时提供 checkpointer，并使用 `thread_id`：

```python
from langgraph.checkpoint.memory import InMemorySaver

graph = g.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "student-001"}}

out = graph.invoke({"messages":[HumanMessage(content="...")]}, config=config)
```

> 教学理解：
>
> * `thread_id` 像“会话/任务主键”
> * 每一步的 state 都会被保存
> * 以后你可以“恢复/回放/审计”

真正做项目时，你会把 InMemorySaver 换成能落盘/入库的实现。

---

### 6.4 第 4 步：加 Interrupt（让它支持“人工审批/补信息”）

生产里经常要这样：

* 发送邮件 / 下单 / 删除数据 这种高风险动作必须审批
* 用户信息不全，要问一句再继续

Interrupt 的思路是：**在图中间暂停，把“需要的输入”抛给外部；外部给了输入后再 resume。**

入门要点（非常重要）：

* interrupt 前的代码在 resume 时可能会重跑，所以 interrupt 前最好不要做副作用（发邮件/写库）。
* 把副作用放到“审批通过之后”的节点里。

---

## 7. 什么是“好的 Agent 架构”：给你一套入门者也能用的判断标准

你以后看到一个 Agent 项目，可以用下面这 10 条快速打分：

### 7.1 结构是否清晰（能不能一眼拆成模块）

* 是否明确区分：LLM 决策 vs 工具执行 vs 流程控制？
* 是否有统一的 State 数据结构？还是到处传 dict？

### 7.2 可靠性是否像“后端系统”

* 工具失败是否会优雅返回并进入恢复流程？
* 有无重试/超时/降级策略？
* 副作用是否幂等（避免重复下单/重复发消息）？

### 7.3 可维护性是否过关

* 流程是否显式（图/状态机），还是 if/else 泥球？
* 新增一个工具/分支需要改多少地方？
* 有无统一的 schema 校验？

### 7.4 安全边界是否清楚

* 工具有无权限控制与 allowlist？
* 高风险动作是否支持审批（HITL）？
* 是否防止模型越权调用工具？

### 7.5 可观测性是否足够

* 出问题能否定位到“哪一步、哪个工具、哪个输入”？
* 是否能回放一次执行过程？

> 入门阶段你不需要一次全做完，但你要知道：
> **“好架构”不是 prompt 写得多漂亮，而是这个系统像一个可靠后端一样可控、可恢复、可调试。**

---

## 8. 学 LangChain / LangGraph 的“层层递进路线”（照这个学，效率最高）

### 第 1 周：只做“闭环”，别做复杂

1. 用 LangChain 跑通工具调用（一个工具就够）
2. 输出格式固定（能解析）
3. 写一个最小 while-loop agent（哪怕不用 LangGraph）

你达到的能力：**知道 Agent 闭环是什么，知道失败点在哪里。**

### 第 2–3 周：转 LangGraph，把流程正规化

1. StateGraph + nodes + conditional edges
2. reducer（尤其 messages 合并）
3. 加 1–2 个分支：失败分支、重试分支、结束分支

你达到的能力：**能画出执行图，并把代码结构写得不乱。**

### 第 4 周：做一个“像样的课程项目”

1. checkpointer + thread_id（可恢复）
2. interrupt（审批/补信息）
3. streaming（进度条/调试输出）
4. 工具层按 SpringMVC 分层（Controller/Service/Repo）

你达到的能力：**你做出来的东西更像产品，而不是 demo。**

---

## 9. 建议你做的三个练手项目（从易到难）

### 项目 A：资料问答助手（最适合入门）

* 工具：检索（向量库或本地文档）
* 图结构：decide → retrieve → write
* 要点：state 里保存 docs，输出结构化 summary

### 项目 B：带审批的“自动发邮件/发通知”助手

* 工具：draft_email、send_email
* 图结构：plan → draft → **interrupt(审批)** → send
* 要点：副作用只在审批后发生；工具返回结构化错误

### 项目 C：多工具任务（3 个工具 + 2 个分支）

* 工具：search、db_query、calculator
* 图结构：route_by_intent → tool → validate → write
* 要点：路由清晰、失败可恢复、错误可统计

---

## 10. 你读完后应当获得的“稳定心智模型”

当你再看到一个 Agent 框架/项目时，你脑子里应该自动出现这张图：

* **认知层**：LLM 负责选择动作（并输出结构化内容）
* **编排层**：图/状态机负责流程与 state（可恢复、可中断、可观测）
* **执行层**：Tools/Services/Repo 像后端一样做契约、校验、权限、异常与幂等（SpringMVC 类比）

只要你能稳定地把任何项目映射到这三层，你就不会迷茫；学 LangChain/LangGraph 也会变成“把概念放回正确位置”的过程，而不是背 API。

