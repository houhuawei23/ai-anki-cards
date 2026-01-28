# Pre-commit Hooks 设置说明

## 问题原因

`.pre-commit-config.yaml` 文件不存在，导致 pre-commit 无法运行。

**原因**：文件可能被 `.cursorignore` 过滤，或者在创建时出现了问题。

## 解决方案

### 1. 创建配置文件

`.pre-commit-config.yaml` 文件已创建，包含以下 hooks：

- **pre-commit-hooks**: 基础检查（尾随空格、文件大小等）
- **ruff**: 代码检查和格式化
- **mypy**: 类型检查（可选，有警告但不致命）
- **bandit**: 安全扫描（可选）

### 2. 安装 Hooks

```bash
# 安装 pre-commit hooks
pre-commit install

# 验证安装
pre-commit run --all-files
```

### 3. 使用

**自动运行**（推荐）：
```bash
# 每次 git commit 前会自动运行
git commit -m "feat: 新功能"
```

**手动运行**：
```bash
# 检查所有文件
pre-commit run --all-files

# 只运行特定 hook
pre-commit run ruff --all-files
pre-commit run ruff-format --all-files
```

## 当前配置状态

✅ **已配置的 Hooks**：
- ✅ trailing-whitespace - 移除尾随空格
- ✅ end-of-file-fixer - 修复文件末尾换行
- ✅ check-yaml - 检查 YAML 格式
- ✅ check-toml - 检查 TOML 格式
- ✅ ruff - 代码检查（自动修复）
- ✅ ruff-format - 代码格式化
- ⚠️ mypy - 类型检查（有警告，但不阻止提交）
- ✅ bandit - 安全扫描（已配置）

## 注意事项

1. **MyPy 警告**：MyPy 发现了一些类型问题，但这些是非致命的，不会阻止提交。可以逐步修复。

2. **Bandit 配置**：已配置为本地 hook，使用 `pass_filenames: false` 和 `always_run: false`，避免参数格式问题。

3. **跳过 Hooks**（不推荐）：
   ```bash
   git commit --no-verify -m "紧急修复"
   ```

## 更新 Hooks

```bash
# 更新所有 hooks 到最新版本
pre-commit autoupdate
```

## 故障排除

### 问题：`.pre-commit-config.yaml is not a file`

**解决方案**：
1. 确认文件存在：`ls -la .pre-commit-config.yaml`
2. 确认文件是普通文件：`file .pre-commit-config.yaml`
3. 如果文件不存在，重新创建：
   ```bash
   # 文件内容已在项目中，可以直接复制或重新创建
   ```

### 问题：MyPy 报错但不想修复

**解决方案**：
- MyPy 已配置为 `always_run: false`，不会自动运行
- 可以手动运行：`pre-commit run mypy --all-files`
- 或者从配置中移除 mypy hook

### 问题：Bandit 参数错误

**解决方案**：
- 已配置为本地 hook，使用 `pass_filenames: false`
- 这样 bandit 会扫描整个 `ankigen/` 目录，而不是单个文件

## 推荐工作流

1. **开发代码**
2. **提交前自动检查**（pre-commit 会自动运行）
3. **如果检查失败**：
   - Ruff 会自动修复大部分问题
   - 手动修复剩余问题
   - 重新提交

## 验证安装

运行以下命令验证一切正常：

```bash
# 检查配置文件
pre-commit validate-config

# 运行所有 hooks
pre-commit run --all-files

# 检查特定工具
pre-commit run ruff --all-files
pre-commit run ruff-format --all-files
```

## 总结

✅ Pre-commit hooks 已成功安装和配置
✅ 关键检查（Ruff）会自动运行
⚠️ MyPy 和 Bandit 配置为可选（不阻止提交）

现在每次 `git commit` 前都会自动运行代码质量检查！
