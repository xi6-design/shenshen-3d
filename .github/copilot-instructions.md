# GitHub Copilot 项目指令（shenshen 3D 模型）

本仓库是桌宠角色 shenshen 的**风格化低多边形 3D 重建**：纯 Python + numpy，无 Blender / OpenGL 依赖。

## 回答语言

- 用简体中文回答；代码、命令、报错、文件路径、变量名保持英文原样。
- 代码注释用中文，提交信息用中文。

## 这个项目怎么跑

```powershell
python -m pip install numpy   # 唯一依赖
python build.py               # 生成 shenshen.obj / .mtl / .stl / .glb
python preview.py             # 生成 preview.png 四视图
python animate.py             # 渲染 24 帧到 frames/（之后用 ffmpeg 合成 turntable.gif）
```

## 改代码时的约定

- **不要引入 Blender、trimesh、OpenGL、PyTorch 之类的重依赖**：这台机器上没有，渲染器是
  `render.py` 里的纯 numpy z-buffer 光栅器。新功能要能在「只有 numpy」的环境里跑通。
- 几何体一律通过 `mesh.py` 的基元构造（球 / 椭球 / 锥台 / 环 / 扫掠管 / 弧形板），再加进
  `build.py` 的拼装流程；不要绕开这两个文件手写 OBJ 文本。
- 颜色走材质（flat 色），没有 UV 贴图；不要给模型加 `vt` 行或贴图路径，否则 GLB 会缺贴图。
- 比例基准：总高 2.276 单位，1 单位 = 1 cm。改动身体比例时会连带影响各部件坐标，
  改完必须跑 `python preview.py` 看四视图再下结论。
- 导出格式（OBJ / STL / GLB）由 `mesh.py` 统一处理，不要单独写导出逻辑。

## 产物与仓库卫生

- 生成物 `shenshen.glb` / `.obj` / `.mtl` / `.stl` / `hero.png` / `preview.png` / `turntable.gif`
  是**要提交的**（README 里直接引用）。
- `frames/`、`palette.png`、`tmp/`、`__pycache__/` 是中间产物，已在 `.gitignore` 里忽略，
  不要提交。
- 模型是独立闭合壳互相穿插，**没有布尔合并**，也没有骨骼和 UV：改结构时不要声称"水密"或"已绑定"。
