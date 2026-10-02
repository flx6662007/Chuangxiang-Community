# 仓库工作规则

- 完成代码修改与验证后停下，先向用户报告：修改文件及原因、测试命令与结果、`git status`、需要特别检查的事项，并给出简洁 diff 摘要。
- 未收到用户明确的提交指令，不执行 `git commit`。获得提交授权也不代表获得推送授权；未收到明确的推送指令，不执行 `git push`。
- 未收到用户明确要求，不使用 `git reset --hard`、`git clean -fd`、`git push --force`、`git rebase` 或其他可能丢失代码、改写 Git 历史的高风险操作。
- 用户人工审查前保留修改供检查。本项目的功能、启动方式和团队背景另见 `agent.md`、`README.md` 及 `docs/`。
