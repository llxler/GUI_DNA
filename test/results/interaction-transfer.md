# 开发原语到完整交互序列

Two specification-derived applications, development-only library construction, one full target per app and 12 heldout interaction sequences. Not official benchmark scores or 24 independent tasks.

| 来源应用 | 建库提示 | 做法 | 首次/最终 | 应用全过 | 轨迹通过（相关） |
|---|---|---|---|---:|---:|
| todos | none | free | first | 0/2 | 0/24 |
| todos | none | free | final | 0/2 | 4/24 |
| todos | direct | plan | first | 4/4 | 48/48 |
| todos | direct | plan | final | 4/4 | 48/48 |
| todos | direct | free_lib | first | 3/4 | 36/48 |
| todos | direct | free_lib | final | 4/4 | 48/48 |
| todos | contracts | plan | first | 4/4 | 48/48 |
| todos | contracts | plan | final | 4/4 | 48/48 |
| todos | contracts | free_lib | first | 4/4 | 48/48 |
| todos | contracts | free_lib | final | 4/4 | 48/48 |
| rows | none | free | first | 0/2 | 2/24 |
| rows | none | free | final | 1/2 | 14/24 |
| rows | direct | plan | first | 4/4 | 48/48 |
| rows | direct | plan | final | 4/4 | 48/48 |
| rows | direct | free_lib | first | 4/4 | 48/48 |
| rows | direct | free_lib | final | 4/4 | 48/48 |
| rows | contracts | plan | first | 4/4 | 48/48 |
| rows | contracts | plan | final | 4/4 | 48/48 |
| rows | contracts | free_lib | first | 4/4 | 48/48 |
| rows | contracts | free_lib | final | 4/4 | 48/48 |

固定控制：

- todos/openai/gpt-5/direct: 三例合并 12/12；有限子集合并存在完整见证=True。
- todos/openai/gpt-5/contracts: 三例合并 12/12；有限子集合并存在完整见证=True。
- todos/anthropic/claude-sonnet-4.5/direct: 三例合并 0/12；有限子集合并存在完整见证=False。
- todos/anthropic/claude-sonnet-4.5/contracts: 三例合并 0/12；有限子集合并存在完整见证=False。
- rows/openai/gpt-5/direct: 三例合并 12/12；有限子集合并存在完整见证=True。
- rows/openai/gpt-5/contracts: 三例合并 12/12；有限子集合并存在完整见证=True。
- rows/anthropic/claude-sonnet-4.5/direct: 三例合并 12/12；有限子集合并存在完整见证=True。
- rows/anthropic/claude-sonnet-4.5/contracts: 三例合并 12/12；有限子集合并存在完整见证=True。

- Two familiar source applications, one seed per builder/planner; no independent-project significance claim.
- Construction comparison is a prompt-level process contrast, not a new learned abstraction algorithm.
- Development exposes primitive semantics and UI selectors; heldout trajectories are unseen, not all semantic information.
- Full-merge is a deterministic deployable control; success of any subset merge is only a finite-set reachable witness.
- Extra unrequested working features were allowed; fixed development examples may already implement the full target.
