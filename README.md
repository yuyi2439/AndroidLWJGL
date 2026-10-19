# AndroidLWJGL

为 NotaLauncher 构建 **LWJGL 3.4.3 / Android arm64-v8a / API 29+** 原生依赖。
这是独立的源码构建项目：发布到自己的 GitHub 仓库后，clone 即可用 NDK 本地构建；
GitHub Actions 调用同一个入口，打 tag 后将制品发布到 Release。
NotaLauncher 只消费 Release 制品，不在启动器构建过程中编译这些依赖。

## 产物

| 文件 | 源码 |
|---|---|
| `liblwjgl.so` | LWJGL 3.4.3 core；静态包含 libffi 3.8.0 |
| `liblwjgl_opengl.so` | LWJGL 3.4.3 OpenGL JNI；排除 Windows WGL |
| `liblwjgl_stb.so` | LWJGL 3.4.3 生成代码和随附 STB |
| `liblwjgl_vma.so` | LWJGL 3.4.3 生成代码、随附 VMA 3.4.0 / Vulkan headers |
| `libfreetype.so` | FreeType 2.14.3；关闭可选外部压缩库和 HarfBuzz |
| `libopenal.so` | OpenAL Soft 1.25.2；Android OpenSL ES 后端，内嵌 HRTF |
| `libshaderc.so` | shaderc 2026.3；静态包含 DEPS 锁定的 glslang 和 SPIRV-Tools |
| `libspirv-cross-c-shared.so` | SPIRV-Cross C API 0.68.0，vulkan-sdk-1.4.341.0 |

还会复制同一 NDK 的 `libc++_shared.so`，作为这些库的运行时依赖。
这不属于上面 8 个主库；没有额外的动态 `libffi.so`。

不构建 SDL：从 [SDL 官方 Release](https://github.com/libsdl-org/SDL/releases)
单独引用 Android 制品。也不构建 jemalloc / jtracy / GLFW。
游戏侧使用 `-Dorg.lwjgl.system.allocator=system`，不开启 `--tracy`。
原版 26.3 会在启动引导中初始化 OpenGL 绑定，因此保留该 JNI 库；
这不代表提供桌面 OpenGL 渲染后端。

本项目只产出原生依赖，**不替换/重建 Java JAR，不接入 SDL Activity，不修改启动器，
不决定 APK 打包和运行时加载路径**。这些 SO 与游戏的 LWJGL 3.4.3 Java JAR 配套。
OpenAL / SPIRV-Cross 保留上游 Android/CMake 的库名，消费方需要配置实际文件名。

## 本地构建

需要 Python **3.12+**、CMake **3.22.1+**、Ninja、Android NDK。
本项目的 CI 工具链固定为 NDK **30.0.16248370**、CMake **3.22.1**。
首次构建需要联网下载源码；不需要 Ant、Gradle、Kotlin、Autotools 或宿主 JDK。

```sh
python build.py --ndk /path/to/android-sdk/ndk/30.0.16248370 --sdk /path/to/android-sdk
```

Windows PowerShell（Python 可执行文件也可以写成完整路径）：

```powershell
python build.py --ndk "$env:LOCALAPPDATA/Android/Sdk/ndk/30.0.16248370" --sdk "$env:LOCALAPPDATA/Android/Sdk"
```

也可以设置 `ANDROID_NDK_HOME` 和 `ANDROID_HOME`，然后直接运行 `python build.py`。
若 CMake / Ninja 在 PATH 中，`--sdk` 可以省略。内存不足时使用 `--jobs 2`。
下载使用系统代理，也支持 `HTTPS_PROXY` / `HTTP_PROXY`。

```sh
python build.py --fetch-only  # 下载并验证固定源码
python build.py --offline --ndk /path/to/ndk --sdk /path/to/sdk
```

`sources.lock.json` 记录每项上游仓库、版本、完整 commit 和源码包 SHA-256。
缓存进入 `.cache/`，编译进入 `build/`，发布产物进入 `dist/`，三者都不提交。
改锁文件后重新执行正常构建，下载器会更新对应源码。`--offline` 不下载，检查缓存 commit。
少量源码适配由 `patches.json` 记录并严格匹配原文，重复构建可安全复用。

也可手动调用 CMake：先 `python build.py --fetch-only`，再使用 `build.py`
所打印的 CMake 配置和构建命令。建议使用脚本，以同时执行补丁、检查和打包。

## 发布

把**本目录内容作为独立仓库的根目录**上传，工作流路径为 `.github/workflows/build.yml`。
推送 main / PR / 手动运行只构建并上传 Actions artifact。
推送标签（例如 `3.4.3-android.1`）在构建检查通过后自动创建 GitHub Release。
发布步骤使用仓库自带 `GITHUB_TOKEN`，不需要个人访问令牌。

Release 附件：

- `lwjgl-3.4.3-android-arm64.zip`：8 个主 SO、C++ 运行时、许可证、构建清单与锁文件，
  以及 `sources/` 中完整的对应源码包和 `build-recipe/` 中的构建脚本。
- `manifest.json`：源码提交、NDK、API、各文件大小/哈希/动态依赖/导出符号检查。
- `SHA256SUMS`：ZIP 的 SHA-256。

脚本自动检查 AArch64 ELF、至少 16 KiB 的 LOAD 段对齐、动态依赖白名单及关键导出符号；
链接使用 `--no-undefined`。这证明交叉编译和静态检查通过，**不等于已在 Android
OpenJDK 中完成加载、回调或游戏启动测试**。

离线重建 Release：进入解包后的 `build-recipe/`，把 `../sources/*.tar.gz`
复制到该目录下新建的 `.cache/`，然后按本地构建命令运行；脚本验证哈希后直接使用缓存。

## 构建适配与来源

参考 [AngelAuraMC/lwjgl3](https://github.com/AngelAuraMC/lwjgl3) 的
`wip/rebase_3.4.1` 分支（阅读时 commit `702c2102a2876cdf67d1d57f6819fa2d458217d9`）：
采用 NDK 编译 Linux/POSIX 原生层和静态 libffi 的思路。本项目构建脚本独立实现，
直接使用官方 3.4.3 已生成的 JNI 源码，不采用其预编译 SO、Java 补丁或下载 latest 的方式。

libffi 的 CMake 适配专用于 Android AArch64 LP64，对应上游该目标的源码集合；
`fficonfig.h` 明确记录目标能力，避免 Windows 上引入 Autotools。
不启用静态 trampoline 表，沿用 libffi 动态 closure 分配机制；回调仍须真机验证。
LWJGL liburing 的桌面兼容头改用 NDK 的 `linux/time_types.h`，避免重复定义。
shaderc 的安装选项修正为配置期布尔值，只安装本项目选定的运行时库。

第三方源码仍适用各自许可证，见 [THIRD-PARTY.md](THIRD-PARTY.md)。
