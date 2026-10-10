# Windows 本机评审包

评审包面向 Windows x64，内含 Python 运行时、后端依赖、构建后的前端、本地 BGE 模型和公开资料。评委无需预装 Python、Node.js 或 PostgreSQL，也无需填写模型密钥。

## 评委使用

1. 将整个压缩包解压到一个文件夹，不要在压缩包内直接运行。
2. 双击 `启动创享.exe`，等待首次初始化；浏览器会自动打开本机页面。
3. 在启动器查看专用演示账号；需要体验组队双方操作时，用两个浏览器分别登录。
4. 体验期间保持启动器运行，结束时通过启动器停止服务并退出。

数据库、首次生成的本机密钥、缓存、邮件和日志保存在 `%LOCALAPPDATA%\ChuangxiangReview\<package-id>`。该目录不可写时，启动器尝试包内 `user-data\<package-id>`。再次打开同一包会保留演示数据；这些操作不会写入开发或线上数据库。

资料浏览与本地检索可离线使用；AI 回答和访问官方链接需要网络。包制作者应提前通过启动器“AI 配置”或包根 `review.env` 配置评审专用 `DEEPSEEK_API_KEY`、接口地址和模型，并完成一次真实问答验证。未配置时仍可浏览资料和使用演示账号。

公开 ZIP 自动排除 `review.env`。只有用户明确授权分发该凭据后，才可将它放入私下交付的包；不得提交到 Git 仓库。配置只从本包读取，不继承开发机 `.env` 或环境中的模型密钥。

## 制作者构建

以下命令在仓库根目录的 PowerShell 执行。先准备 Windows x64 Python 3.13 运行环境（已安装后端和 BGE 检索依赖）、通过 `export_portable_demo` 导出的公开 fixture，以及固定版本的 `bge-small-zh-v1.5` 模型目录。fixture 使用默认演示作者 ID `1`，不包含真实用户、会话、组队或举报记录。

用独立虚拟环境构建启动器，避免把后端与模型依赖打入启动器 EXE：

```powershell
py -3.13 -m venv .local\portable-build\venv
$reviewBuildPython = '.\.local\portable-build\venv\Scripts\python.exe'
& $reviewBuildPython -m pip install PyInstaller==6.22.3
& $reviewBuildPython -m PyInstaller --clean --onefile --windowed --name 启动创享 --distpath .local\portable-build\launcher --workpath .local\portable-build\work --specpath .local\portable-build scripts\portable\launcher.py

Push-Location frontend
npm ci
npm run build
Pop-Location
```

将前三个路径替换为准备好的实际文件。构建脚本复制后端源码、`frontend/dist`、运行环境、模型、公开 fixture，以及 `scripts/portable/licenses` 中的第三方许可证；不会复制开发 `.env` 或工作数据库。

```powershell
$reviewRuntimePython = 'C:\已准备的运行环境\Scripts\python.exe'
$reviewFixture = 'C:\已导出的资料\public-fixture.json'
$reviewModel = 'C:\已准备的模型\bge-small-zh-v1.5'
$reviewPackage = Join-Path (Get-Location) '.local\portable-build\review-package'
& $reviewBuildPython scripts\portable\build_package.py --python $reviewRuntimePython --output $reviewPackage --fixture $reviewFixture --launcher .local\portable-build\launcher\启动创享.exe --model $reviewModel --package-id chuangxiang-review-20261010

$reviewIndexData = Join-Path $env:TEMP ('cx-review-index-' + [guid]::NewGuid().ToString('N'))
& $reviewBuildPython scripts\portable\prepare_indexes.py --package-root $reviewPackage --build-data $reviewIndexData
```

`prepare_indexes.py` 只接受全新空目录：用包内运行时迁移临时 SQLite、创建演示作者、导入公开 fixture，然后生成 `index/competitions.npz` 和 `index/unified.npz`，保证索引对应包内实际资料。模型仅从 `models/bge-small-zh-v1.5` 加载，运行时关闭自动下载。临时构建目录不加入交付包。

验收后生成不含密钥的公开 ZIP。ZIP 输出位置须在包目录外，避免压缩包把自己收录进去：

```powershell
& $reviewBuildPython -c 'import sys; from pathlib import Path; sys.path.insert(0, "scripts/portable"); from build_package import create_public_zip; create_public_zip(Path(sys.argv[1]), Path(sys.argv[2]))' $reviewPackage "$reviewPackage.zip"
```

## 功能范围与本轮验证

服务仅绑定 `127.0.0.1`，使用独立 SQLite 和单线程服务，不代表线上并发验证。AI 流式回答期间，其他请求可能需要等待。保留现有登录、组队、举报及 API 流程；科研公开入口按当前版本关闭，邮件写入本地 `mail` 目录而不真实发送，不运行自动采集。

2026-10-10 本机验证：控制器首次初始化用时 **30.317 秒**；实际运行构建后的 `启动创享.exe`，GUI 窗口和演示网页均已打开。公开 fixture 共 **4,083 个对象**，包含 **188 条赛事、322 条资源、500 条正文**，以及补齐的 **22 条招募字典**。其他电脑的首次启动耗时可能不同。

已完成的真实业务验收：

- DeepSeek 学习资料 API 分别回答蓝桥杯 Python 学习和 RoboMaster 开发板问题，两次均使用混合检索，`warnings` 为空。
- 网页中的 RoboMaster C 型开发板问答成功返回官方 `Development-Board-C-Examples` 资料。
- 两个演示账号完成完整组队 API 闭环；登录、邮箱验证状态和发布资格均正常。
- 重复启动复用同一已验证实例；关闭启动器后其子进程退出，原有 8000/5173 服务状态未改变。

业务与便携回归共 93 项，跳过 1 项 PostgreSQL 并发测试；启动器 9 项、公开导出 5 项测试通过。模型路径专项另有 4 项通过，与前述测试存在重叠，不累加为新的总数。当前公开 ZIP 约 **331 MiB**，以最终交付文件大小为准。

本轮同时产出不含密钥的公开包与经项目负责人明确授权、预配置 DeepSeek 测试密钥的私下评审包，均约 **330.6 MiB**，ZIP 完整性检查通过。私下包仅在仓库之外的本机输出目录交付，不提交 Git 或上传公开仓库。评委电脑之间使用独立演示数据，不互通组队记录。
