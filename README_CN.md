# InsideOut

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/logo-light.svg">
  <img alt="InsideOut" src="assets/logo-light.svg" width="520">
</picture>

**画出物体，使用本地视觉检索匹配 3D 模型，并直接探索其组成部分。**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?logo=windows)](#系统要求)
[![Retrieval](https://img.shields.io/badge/competition%20classes-Heart%20%7C%20Car%20%7C%20Earth-EFC57B)](#支持对象)
[![License](https://img.shields.io/badge/project%20license-not%20declared-lightgrey)](#许可证)

[English](README.md) · **简体中文**

InsideOut 是面向 AIO 2026 的原生 PySide6/VTK 计算机视觉原型。它可以拍摄实体画作或打开图片，在不强制要求纸张边界的情况下寻找视觉区域，再将 RGB 与线稿表示和本地 OpenCLIP 索引比较，最后打开可交互的多部件 3D 对象。竞赛识别范围严格限制为 **心脏、汽车和地球**。

## 演示流程

1. 使用 `start_insideout.bat` 启动原生窗口。
2. 选择摄像头，或点击 **Open drawing**。
3. 展示心形/心脏、侧视汽车，或带有大陆形状的地球。
4. 按 **Space**，或启用稳定画面自动捕获。
5. 使用手势、鼠标或按钮旋转、爆炸、隔离并重置模型。

低分或第一、第二名差距太小的输入会被拒绝，不会被强行判成某个类别。只有圆形而没有陆地结构时不会被识别为地球。

## 适用人群

- 评审和演示 AIO 2026 原生竞赛原型的人员。
- 学习本地计算机视觉、图像检索和交互式 3D 图形的学生。
- 需要复现 Windows 构建或扩展离线验证脚本的开发者。

## 功能

- PySide6 与 VTK 原生窗口，无需浏览器、Web 服务、账户或 API 密钥。
- 可选纸张的 ROI：页面、成组笔画、海报矩形和保守的中心回退。
- 主 ROI 使用 RGB、灰度、清理线稿和边缘四种表示。
- 本地 OpenCLIP ViT-B-32 图像向量；线稿库额外加入少量、经过实测校准的形状分数。
- 237 个竞赛参考向量：36 个渲染、165 个线稿/边缘、36 个真实草图原型。
- 保守接受条件：分数至少 `0.78`，Top-1 与 Top-2 差值至少 `0.04`。
- 心脏 14 个语义部件、CarConcept 汽车 11 个组合部件、地球 4 个教学层。
- MediaPipe 手部跟踪、最新帧处理、One Euro 滤波、捏合滞回、死区和锁定状态机。
- CPU、图片输入、直接模型库和鼠标操作等竞赛回退。
- CV 调试抽屉显示 ROI、查询图、排名、分数、耗时、手势状态与 FPS。

## 支持对象

只有前三个对象参加竞赛检索，其他对象只能从模型库直接打开。

| 对象 | 检索 | 运行时部件 | 来源 / 许可 |
|---|---:|---:|---|
| 人体心脏 | 是 | 14 个命名解剖部件 | HuBMAP HRA，CC BY 4.0 |
| 汽车 | 是 | 11 个来源支持的组合 | Khronos CarConcept，CC BY 4.0 |
| 地球 | 是 | 4 个教学层 | InsideOut 程序化回退，CC0 1.0 |
| 人体肺 | 仅模型库 | 67 个来源部件 | HuBMAP HRA，CC BY 4.0 |
| 古董相机 | 仅模型库 | 2 个来源组 | Khronos/UX3D，CC0 1.0 与标志声明 |
| 灯笼 | 仅模型库 | 3 个来源组 | Khronos，CC0 1.0 |
| 水瓶 | 仅模型库 | 6 个几何部件 | Khronos，CC0 1.0 |

作者、链接、校验值、修改、标志处理和完整声明见 [ATTRIBUTION.md](ATTRIBUTION.md)。

## 快速开始

在已准备好的竞赛电脑上：

```powershell
.\start_insideout.bat
```

无摄像头的安全 CPU 回退：

```powershell
.\start_insideout.bat --cpu --no-camera
```

## 安装

### 系统要求

- 64 位 Windows 10 或 11。
- 64 位 Python 3.12。
- 支持 VTK/OpenGL 的图形驱动。
- 摄像头仅在相机输入时需要。
- Python 包和模型缓存需要数 GB 空间。
- 首次设置需要网络；正常运行完全本地。

### 设置

在项目目录的 PowerShell 中执行：

```powershell
.\setup_insideout.ps1
```

设置脚本会创建 `.venv-desktop`、安装 [requirements-desktop.txt](requirements-desktop.txt)、下载注明来源的模型和约 605 MB 的 OpenCLIP 权重、生成运行时几何/预览以及竞赛索引，但不会自动启动程序。

可用选项：

```powershell
.\setup_insideout.ps1 -SkipAssets
.\setup_insideout.ps1 -Python 'C:\Path\To\python.exe'
.\setup_insideout.ps1 -UseSystemPackages
```

## 使用

### 摄像头

```powershell
.\start_insideout.bat
.\start_insideout.bat --camera 1
```

在点击 **Camera on** 前，从 **Input** 中选择 Camera 0–5。设备不可用时会显示错误，图片和模型库回退仍可使用。纸张可帮助透视校正，但不是识别的必要条件。

### 图片文件

正常启动或禁用摄像头，然后选择 **Open drawing**：

```powershell
.\start_insideout.bat --no-camera
```

支持 PNG、JPEG、BMP 与 WebP。摄像头和文件输入共用同一套 ROI 与检索引擎。

### CPU 回退

```powershell
.\start_insideout.bat --cpu
.\start_insideout.bat --cpu --no-camera
```

CUDA 不是必需条件；不可用时自动模式会回退到 CPU。在验证机器上，四个保留实体画面在编码器加载后的 CPU 检索平均耗时 470 ms，范围为 370–606 ms。

### 操作

| 输入 | 操作 |
|---|---|
| 指向并短暂停留 | 悬停/选择网格 |
| 捏合并移动 | 抓取并拉动部件 |
| 捏合时转动手腕 | 旋转部件或组合 |
| 在空白处捏合并移动 | 环绕整个模型 |
| 双手张开/靠近 | 连续爆炸/合拢 |
| 保持单手张开 | 重置/重组 |
| 鼠标左键拖动 / 滚轮 | 环绕 / 缩放 |
| Shift + 左键拖动 | 拉动部件 |
| `I`、`H`、`R` | 隔离、隐藏/显示、重置 |
| `N`、`D`、`F11` | 新画作、调试抽屉、全屏 |

竞赛模式禁用手势隔离，但按钮和键盘回退仍然可用。

## 检索与验证

每个 ROI 会独立比较三个类别，类别不能分别使用不同裁剪来获胜。检测到可靠页面、画作或海报后，该区域拥有最终决定权；若不确定则拒绝，不再让背景中心裁剪错误地选择汽车。

当前保留回归集包含一帧心脏、一帧汽车和两帧地球实体画面。CPU 文件/ROI 流程四项均正确。这只是很小的校准与防回归样本，不代表一般准确率；详细画作、海报和更多画法仍需要额外人工样本。

```powershell
.\.venv-desktop\Scripts\python.exe scripts\evaluate_retrieval.py evaluation\competition_frames --device cpu --output evaluation\frame_evaluation
.\.venv-desktop\Scripts\python.exe scripts\validate_negatives.py
.\.venv-desktop\Scripts\python.exe scripts\validate_runtime.py --device cpu --models human_heart toy_car earth
```

详细证据见 [docs/VALIDATION_REPORT.md](docs/VALIDATION_REPORT.md)、[docs/COMPETITION_BUILD_STATUS.md](docs/COMPETITION_BUILD_STATUS.md) 和 [docs/TECHNICAL_FACTS.md](docs/TECHNICAL_FACTS.md)。

## 架构

```text
摄像头 / 图片
      ├─ 页面、笔画、海报、中心 ROI
      │    └─ RGB / 灰度 / 线稿 / 边缘
      │         └─ OpenCLIP + 校准形状分数
      │              └─ 分数与差值门控 ──> 3D 模型
      └─ 最新摄像头帧 ──> MediaPipe ──> 滤波交互状态

GLB/源几何 ──> 离线 VTK 缓存与层级 ──> 可选择部件场景
```

| 路径 | 用途 |
|---|---|
| `insideout.py` | 原生启动器和命令行选项 |
| `desktop/query_regions.py` | 可选纸张的 ROI |
| `desktop/encoder.py` | 查询表示、检索库、评分和拒绝 |
| `desktop/camera.py` | 最新帧摄像头与手部工作线程 |
| `desktop/gestures.py`、`desktop/interactions.py` | 滤波和状态机 |
| `desktop/scene.py` | VTK 选择、移动、爆炸、隔离、重置 |
| `scripts/build_competition_index.py` | 重建三类索引 |
| `scripts/evaluate_retrieval.py` | 完整文件/ROI 回归评估 |

## 构建与打包

```powershell
.\scripts\build_release.ps1
```

ZIP 不包含虚拟环境、包缓存、日志、临时证据、模型权重或生成的几何缓存。解压后运行 `setup_insideout.ps1` 下载并生成机器相关依赖。未提供独立 EXE，因为 PyTorch、OpenCLIP、VTK、Qt、MediaPipe、权重和注明来源的资产会形成非常大且未经竞赛验证的脆弱安装包。

## 安全与隐私

- 摄像头帧、手部点位和查询保留在本机内存中；程序没有上传或遥测路径。
- 运行错误只写入本地 `data/logs/insideout.log`。
- 设置阶段会联网下载 Python 包、模型和权重。
- 导入的 3D/图片文件应视为不受信任输入，原生解析器不是沙箱。
- 不需要 API 密钥或凭据；不要提交本地秘密、虚拟环境、日志或下载令牌。

## 贡献

修改应保持在原生 Python 原型范围内。必须保留准确归属，并区分实体测试与软件重放。提交前运行编译、负例检索、保留画面评估和相关运行时验证。没有明确再分发许可和来源元数据时不要加入资产。

## 许可证

InsideOut 自有源代码尚未选择通用开源许可证，因此默认版权限制适用。第三方模型、包和权重保留各自许可，详见 [ATTRIBUTION.md](ATTRIBUTION.md)。仓库公开不代表授予这些声明之外的权利。
