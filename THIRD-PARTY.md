# Third-party sources

`sources.lock.json` 是具体版本、提交和下载校验值的唯一来源。
发布 ZIP 包含各锁定源码中的许可证 / NOTICE / COPYING / COPYRIGHT 文件。

| Component | Upstream | License |
|---|---|---|
| LWJGL | https://github.com/LWJGL/lwjgl3 | BSD-3-Clause；随附 STB、VMA、Vulkan headers、liburing 等保留其源码许可 |
| libffi | https://github.com/libffi/libffi | MIT-style |
| FreeType | https://gitlab.freedesktop.org/freetype/freetype | FreeType License 或 GPLv2；此制品按 FreeType License 分发 |
| OpenAL Soft | https://github.com/kcat/openal-soft | LGPL-2.0-or-later；另有随附依赖的许可 |
| shaderc | https://github.com/google/shaderc | Apache-2.0 |
| glslang | https://github.com/KhronosGroup/glslang | 各文件保留 BSD/MIT/Apache 等上游许可 |
| SPIRV-Tools | https://github.com/KhronosGroup/SPIRV-Tools | Apache-2.0 |
| SPIRV-Headers | https://github.com/KhronosGroup/SPIRV-Headers | MIT 等，见源码许可 |
| SPIRV-Cross | https://github.com/KhronosGroup/SPIRV-Cross | Apache-2.0 或 MIT |
| libc++ | Android NDK / LLVM | Apache-2.0 WITH LLVM-exception |

OpenAL Soft 单独作为共享库提供；分发方应保留 LGPL 通知、允许按许可替换/修改，
并提供对应源码。构建产物清单给出准确的上游源码 commit；源码修改记录见本仓库，
不得将整个二进制包笼统声明为单一 BSD/MIT 许可证。

本仓库提供构建与版本固定，不改变第三方许可。
