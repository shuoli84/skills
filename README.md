# Skills

可复用的 Codex Skills，整理实际问题的排查结论、解决流程与辅助脚本。

| Skill | 用途 |
|---|---|
| [macos-pinyin-repair](skills/macos-pinyin-repair/SKILL.md) | 排查 macOS 系统拼音中英混输时的候选消失、英文截断和卡顿，提供学习数据的备份、对照修复与回滚流程。 |

每项 Skill 都放在独立的 `skills/<名称>/` 目录中，可单独复制和使用。

安装当前 Skill：

```bash
git clone https://github.com/shuoli84/skills.git
cd skills
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skills/macos-pinyin-repair "${CODEX_HOME:-$HOME/.codex}/skills/"
```

在 Codex 中使用 `$macos-pinyin-repair` 调用。具体适用条件、操作步骤和验证方法见对应的 `SKILL.md`。

词库处理脚本默认只预览。显式指定输出文件后，会生成供检查的修复副本与清理清单；实际替换和回滚按照 Skill 流程执行。
