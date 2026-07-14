![logo](https://chaosblade.oss-cn-hangzhou.aliyuncs.com/doc/image/chaosblade-logo.png)

# Chaosblade-exec-python: 插件开发指南

## 插件介绍

一个完整的插件包含以下组件：

| 组件 | 作用 | 对应 Java 版 |
|------|------|-------------|
| Plugin | 插件入口，组装各组件 | Plugin (SPI) |
| PointCut | 定义拦截点（模块、类、方法） | PointCut (ClassMatcher + MethodMatcher) |
| Enhancer | 参数提取器（从被拦截方法中提取匹配参数） | Enhancer (Before/After) |
| ModelSpec | 定义 target 名称和支持的 matcher | ModelSpec |
| ActionSpec | 定义 action 名称和参数校验 | ActionSpec |
| ActionExecutor | 实际执行故障能力（延迟、异常、篡改返回值） | ActionExecutor |

## 调用时序

```
[HTTP Request /create]
       │
       ▼
[CreateHandler] ─── 注册到 StatusManager
       │
       ▼
[PluginLifecycleListener.add()] ─── 安装 MonkeyPatch
       │
       ▼
[应用调用目标方法]
       │
       ▼
[wrapper 函数拦截]
       │
       ├── StatusManager.exp_exists(target)? → 无实验则直通
       │
       ├── Enhancer.extract_matchers() → 提取匹配参数
       │
       ├── compare(model.matcher, actual_matchers) → 参数比对
       │
       └── ActionExecutor.run() → 触发故障能力
```

## 插件扩展步骤

以开发一个 `httpx` 客户端插件为例。

### 1. 创建插件目录

在 `src/chaosblade/plugins/` 下新建子目录：

```
src/chaosblade/plugins/httpx/
├── __init__.py
```

### 2. 自定义 Matcher Extractor

extractor 函数从被拦截方法的参数中提取匹配用的键值对：

```python
from typing import Any


def _httpx_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """从 httpx.AsyncClient.send() 参数中提取匹配器。

    httpx.AsyncClient.send(self, request, *, stream=False, auth=..., follow_redirects=...)
    - method_name: 被拦截的方法名（如 "send"）
    - obj: 绑定的实例（httpx.AsyncClient instance）
    - args: wrapper 接收到的位置参数，其中 args[1] 通常是 httpx.Request 对象
    - kwargs: 关键字参数
    """
    matchers: dict[str, str] = {}

    if len(args) >= 2:
        request = args[1]
        url = getattr(request, "url", None)
        http_method = getattr(request, "method", None)

        if url:
            matchers["url"] = str(url)
            host = getattr(url, "host", None)
            path = getattr(url, "path", None) or getattr(url, "raw_path", None)
            if host:
                matchers["host"] = str(host)
            if path:
                matchers["path"] = str(path)

        if http_method:
            matchers["method"] = str(http_method).upper()

    return matchers
```

**关键点：**
- 返回的 key 必须与 ModelSpec 中定义的 MatcherSpec 名称一致
- 只提取用于匹配的参数，不要修改原始参数

### 3. 自定义 PointCut

PointCut 定义了要拦截的目标：

```python
from chaosblade.plugins.base import DefaultPointCut


httpx_point_cut = DefaultPointCut(
    target_module="httpx._client",    # 目标模块的完整导入路径
    target_function="send",            # 目标方法名
    target_class="AsyncClient",        # 目标类名（模块级函数设为 None）
)
```

**参数说明：**
- `target_module`: Python 模块的完整点分路径（如 `redis.client`）
- `target_function`: 要拦截的方法/函数名
- `target_class`: 如果方法是类的实例方法，指定类名；模块级函数设为 `None`

### 4. 自定义 ModelSpec

ModelSpec 定义 target 名称及其支持的 matcher 和 action：

```python
from chaosblade.common.model.base_model_spec import BaseModelSpec
from chaosblade.executor.delay_executor import DelayActionExecutor
from chaosblade.executor.exception_executor import ThrowExceptionExecutor
from chaosblade.executor.return_executor import ReturnValueExecutor
from chaosblade.plugins.base import (
    DefaultActionSpec,
    DefaultFlagSpec,
    DefaultMatcherSpec,
)


class HttpxModelSpec(BaseModelSpec):
    """ModelSpec for httpx fault injection."""

    def __init__(self) -> None:
        super().__init__()
        self._register_actions()

    def get_target(self) -> str:
        """对应命令中的 target 名称: blade create httpx ..."""
        return "httpx"

    def get_short_desc(self) -> str:
        return "httpx HTTP client fault injection"

    def get_long_desc(self) -> str:
        return "Inject delay, exception or return value faults into httpx HTTP requests"

    def get_matcher_specs(self) -> list[DefaultMatcherSpec]:
        """定义匹配参数（对应 method、url、host、path 等请求参数）"""
        return [
            DefaultMatcherSpec("url", "Full request URL to match"),
            DefaultMatcherSpec("method", "HTTP method to match (GET, POST, etc.)"),
            DefaultMatcherSpec("host", "Target hostname to match"),
            DefaultMatcherSpec("path", "URL path to match"),
        ]

    def _register_actions(self) -> None:
        """注册支持的 Action（delay/exception/return）"""
        self.add_action_spec(DefaultActionSpec(
            name="delay",
            short_desc="Inject latency into httpx requests",
            flags=[
                DefaultFlagSpec("time", "Delay in milliseconds", _required=True),
                DefaultFlagSpec("offset", "Random offset range in milliseconds"),
            ],
            executor=DelayActionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="throwCustomException",
            short_desc="Throw exception from httpx requests",
            aliases=["exception"],
            flags=[
                DefaultFlagSpec("exception", "Exception class name"),
                DefaultFlagSpec("exception-message", "Exception message"),
            ],
            executor=ThrowExceptionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="returnValue",
            short_desc="Override httpx request return value",
            aliases=["return"],
            flags=[
                DefaultFlagSpec("return-value", "Value to return"),
            ],
            executor=ReturnValueExecutor(),
        ))
```

**命令对应关系：**
```
/create?target=httpx&method=GET&url=/api&action=delay&time=3000
        │          │          │        │            │       │
        │          └── MatcherSpec ────┘            │       │
        │                                           │       │
        └── ModelSpec.get_target()       ActionSpec.name  FlagSpec
```

### 5. 自定义 Plugin

将所有组件组装在一起：

```python
from chaosblade.plugins.default_enhancer import DefaultBeforeEnhancer


class HttpxPlugin:
    """httpx HTTP client fault injection plugin."""

    def __init__(self) -> None:
        self._model_spec = HttpxModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="httpx._client",
            target_function="send",
            target_class="AsyncClient",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="httpx",
            extractor=_httpx_matcher_extractor,
        )

    def get_name(self) -> str:
        return "httpx"

    def get_model_spec(self) -> HttpxModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer
```

### 6. 注册 entry_point

在 `pyproject.toml` 的 `[project.entry-points]` 中注册插件：

```toml
[project.entry-points."chaosblade.plugins"]
httpx = "chaosblade.plugins.httpx:HttpxPlugin"
```

这样 Agent 启动时会自动发现并加载该插件。

### 7. 完整文件示例

完整插件实现请直接参考 `src/chaosblade/plugins/httpx/__init__.py`。文档中的片段用于说明扩展点和组件关系，实际维护时应以源码实现为准，避免示例代码与插件行为漂移。

## 自定义 ActionExecutor

如果内置的 Delay/Exception/Return 不满足需求，可以自定义 ActionExecutor：

```python
from chaosblade.spi.action_executor import ActionExecutor


class CustomExecutor(ActionExecutor):
    """自定义故障执行器。"""

    def run(self, enhancer_model) -> None:
        """执行自定义故障逻辑。

        Args:
            enhancer_model: 包含匹配信息和 action flags 的模型
        """
        # 从 action flags 获取参数
        param = enhancer_model.action.get_flag("custom-param")

        # 实现你的故障逻辑
        # ...
```

然后在 ActionSpec 中指定：

```python
DefaultActionSpec(
    name="customAction",
    short_desc="Custom fault injection",
    flags=[DefaultFlagSpec("custom-param", "Description", _required=True)],
    executor=CustomExecutor(),
)
```

## 测试插件

```python
import pytest
from chaosblade.plugins.httpx import HttpxPlugin, HttpxModelSpec


def test_plugin_basic():
    plugin = HttpxPlugin()
    assert plugin.get_name() == "httpx"
    assert plugin.get_model_spec().get_target() == "httpx"
    assert plugin.get_point_cut().get_target_module() == "httpx._client"


def test_model_spec_actions():
    spec = HttpxModelSpec()
    assert spec.get_action_spec("delay") is not None
    assert spec.get_action_spec("throwCustomException") is not None
    assert spec.get_action_spec("returnValue") is not None


def test_matcher_extractor():
    from chaosblade.plugins.httpx import _httpx_matcher_extractor

    class URL:
        host = "api.example.com"
        path = "/api/test"

        def __str__(self):
            return "https://api.example.com/api/test"

    class Request:
        method = "GET"
        url = URL()

    matchers = _httpx_matcher_extractor("send", None, (object(), Request()), {})
    assert matchers == {
        "url": "https://api.example.com/api/test",
        "host": "api.example.com",
        "path": "/api/test",
        "method": "GET",
    }
```

## 相关文档

- [快速入门](./quick-start.md)
- [系统设计](./design.md)
- [插件使用手册索引](./README.md#支持的中间件插件)

## 贡献插件

1. Fork 仓库
2. 在 `src/chaosblade/plugins/` 下创建新插件目录
3. 实现 Plugin + ModelSpec + PointCut + Enhancer
4. 在 `pyproject.toml` 注册 entry_point
5. 编写测试
6. 提交 PR

详见 [CONTRIBUTING.md](../../CONTRIBUTING.md)。
