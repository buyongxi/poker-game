# 贡献指南

感谢你愿意为 `poker-game` 做贡献！

## 开发方式

1. **Fork 本仓库**
   - 在 GitHub 上点击 Fork 按钮创建你的副本

2. **克隆仓库到本地**
   ```bash
   git clone https://github.com/your-username/poker-game.git
   cd poker-game
   ```

3. **创建新分支**
   ```bash
   git checkout -b feat/your-feature-name
   ```

   分支命名建议：
   - `feat/xxx` - 新功能
   - `fix/xxx` - Bug 修复
   - `docs/xxx` - 文档更新
   - `refactor/xxx` - 代码重构
   - `test/xxx` - 测试相关

4. **进行开发**
   - 按照 README.md 中的说明设置开发环境
   - 进行代码修改

5. **本地检查**
   ```bash
   # 后端检查
   cd backend
   python -m compileall app

   # 前端检查
   cd frontend
   npm ci && npm run build
   ```

6. **提交更改**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

7. **推送到远程**
   ```bash
   git push origin feat/your-feature-name
   ```

8. **创建 Pull Request**
   - 在 GitHub 上向主仓库提交 PR

## 提交信息规范

采用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>
```

### 类型说明

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响代码运行） |
| `refactor` | 代码重构 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具/配置相关 |

### 示例

```
feat(room): 添加房间密码功能
fix(auth): 修复 JWT 令牌过期判断错误
docs(readme): 更新快速开始指南
refactor(engine): 简化下注逻辑
```

## Pull Request 描述建议

在 PR 中请说明：

1. **改动目的与解决的问题**
   - 清晰描述这个 PR 要解决什么问题

2. **改动内容**
   - 列出主要修改的文件和改动点

3. **是否需要额外配置/迁移**
   - 如有新的环境变量、数据库迁移等需要说明

4. **测试情况**
   - 运行了哪些测试命令
   - 手动测试的步骤和结果
   - 如有必要，提供测试截图

## 代码风格

### Python (后端)
- 遵循 PEP 8 规范
- 使用类型注解
- 函数和变量使用 snake_case
- 类使用 PascalCase

### TypeScript/Vue (前端)
- 使用 ESLint + Prettier 格式化
- 组件使用 PascalCase
- 变量和函数使用 camelCase
- 优先使用组合式 API (Composition API)

## 问题反馈

遇到问题或有建议？请通过以下方式：
- 创建 [Issue](https://github.com/your-username/poker-game/issues)
- 发送邮件至 buyongxi@foxmail.com
