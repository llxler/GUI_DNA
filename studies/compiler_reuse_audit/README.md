> 版本边界：当前分支已抽出公共工具；原阶段哈希复验使用移除前的 Git 版本。见 [退役记录](../../docs/archive/full-history-retirement.md)。原始成绩与账本未改。

# 同库代码的构建期编译器复用审计（零API）

对原三项目240份最终同库代码及本次18份同库代码的首次/最终响应，共276个记录位置，执行保留的构建程序。包装compile时深拷贝调用计划、输入文件和返回文件，再核对最终源码与原保存页。仅在输入库未变、计划合法、最终源码等于某次编译返回时，标记精确合法复用；返回后修改与输入修改另记。files形式的运行时复用不猜测，包装错误或输出变化独立报告。

协议见[PROTOCOL.md](PROTOCOL.md)，结果在`artifacts/compiler-reuse-audit-20261116/`。`run.py/probe.cjs/__init__.py/PROTOCOL.md`在首次执行时连同输入依赖冻结，之后不得修改。只读复验会重新执行纯VM构建，不调用模型、不运行浏览器：

```bash
uv run python -m test.compiler_reuse_audit.analyze
uv run python -m test.replay_nov16
```

首次/最终是同一链的两个时间点，不能当独立样本。本审计描述已生成程序的实际路径，不改变评分，也不证明无约束代码的能力上界或某种复用路径的因果必要性。
