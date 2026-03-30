# Contributing

感谢你愿意为 `poker-game` 做贡献。

## 开发方式
1. Fork 本仓库
2. 新建分支（建议）：`feat/xxx`、`fix/xxx`、`docs/xxx`
3. 在分支完成修改
4. 提交 Pull Request

## 提交规范（建议）
- 提交信息简洁说明改动意图，例如：`feat: add X`、`fix: handle Y`、`docs: update README`
- 尽量避免一次提交里包含无关改动

## 本地检查（尽量完成）
### 后端
- 运行依赖安装后可执行：
  - `python -m compileall backend/app`

### 前端
- 安装依赖并构建：
  - `cd frontend && npm ci && npm run build`

## Pull Request 描述建议
在 PR 中说明：
- 改动目的与解决的问题
- 是否需要额外配置/迁移
- 测试情况（例如运行了哪些命令/复现步骤）
