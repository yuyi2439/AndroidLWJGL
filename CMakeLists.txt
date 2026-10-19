cmake_minimum_required(VERSION 3.22)
project(AndroidLWJGL VERSION 3.4.3 LANGUAGES C CXX ASM)

if(NOT ANDROID OR NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "Use the Android NDK toolchain with ANDROID_ABI=arm64-v8a")
endif()
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,-z,max-page-size=16384 -Wl,--no-undefined")
set(SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/.cache/sources")
set(LWJGL "${SOURCES}/lwjgl/modules/lwjgl")
include(cmake/libffi.cmake)

# Use NDK JNI headers, not a desktop JDK's platform-specific jni_md.h.
# Android/bionic implements the POSIX subset used by these Linux bindings.
function(lwjgl_module target module)
    file(GLOB generated CONFIGURE_DEPENDS "${LWJGL}/${module}/src/generated/c/*.c" "${LWJGL}/${module}/src/generated/c/*.cpp")
    list(FILTER generated EXCLUDE REGEX "/org_lwjgl_opengl_WGL[^/]*[.]c$")
    add_library(${target} SHARED ${generated} ${ARGN})
    target_compile_definitions(${target} PRIVATE LWJGL_LINUX LWJGL_arm64 _GNU_SOURCE)
    target_include_directories(${target} PRIVATE
        "${LWJGL}/core/src/main/c" "${LWJGL}/core/src/main/c/linux"
        "${LWJGL}/${module}/src/main/c")
    target_compile_options(${target} PRIVATE -Wno-nullability-completeness)
    target_link_libraries(${target} PRIVATE dl m)
endfunction()

file(GLOB core_main CONFIGURE_DEPENDS "${LWJGL}/core/src/main/c/*.c")
file(GLOB core_linux CONFIGURE_DEPENDS "${LWJGL}/core/src/generated/c/linux/*.c")
file(GLOB uring CONFIGURE_DEPENDS "${LWJGL}/core/src/main/c/linux/liburing/*.c")
lwjgl_module(lwjgl core ${core_main} ${core_linux} ${uring})
target_compile_definitions(lwjgl PRIVATE CONFIG_HAVE_MEMFD_CREATE)
target_include_directories(lwjgl PRIVATE "${LWJGL}/core/src/main/c/linux/liburing"
    "${LWJGL}/core/src/main/c/linux/liburing/include")
target_link_libraries(lwjgl PRIVATE ffi)

lwjgl_module(lwjgl_opengl opengl)
lwjgl_module(lwjgl_stb stb)
lwjgl_module(lwjgl_vma vma)
target_include_directories(lwjgl_vma PRIVATE "${LWJGL}/vulkan/src/main/c")

# FreeType: self-contained font rasterizer; optional compression/shaping libraries
# are not required by Minecraft's FreeType calls.
set(BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)
foreach(dependency ZLIB BZIP2 PNG HARFBUZZ BROTLI)
    set(FT_DISABLE_${dependency} ON CACHE BOOL "" FORCE)
endforeach()
add_subdirectory("${SOURCES}/freetype" freetype EXCLUDE_FROM_ALL)
set_target_properties(freetype PROPERTIES VERSION "" SOVERSION "")

set(ALSOFT_UTILS OFF CACHE BOOL "" FORCE)
set(ALSOFT_EXAMPLES OFF CACHE BOOL "" FORCE)
set(ALSOFT_TESTS OFF CACHE BOOL "" FORCE)
set(ALSOFT_INSTALL OFF CACHE BOOL "" FORCE)
set(ALSOFT_BACKEND_OPENSL ON CACHE BOOL "" FORCE)
set(ALSOFT_BACKEND_OBOE OFF CACHE BOOL "" FORCE)
set(ALSOFT_EMBED_HRTF_DATA ON CACHE BOOL "" FORCE)
add_subdirectory("${SOURCES}/openal" openal EXCLUDE_FROM_ALL)
set_target_properties(OpenAL PROPERTIES OUTPUT_NAME openal VERSION "" SOVERSION "")

# Only the exported SPIRV-Cross C API is needed. Its GLSL/HLSL/MSL compilers
# remain enabled, matching upstream LWJGL's general-purpose spvc distribution.
set(SPIRV_CROSS_SHARED ON CACHE BOOL "" FORCE)
set(SPIRV_CROSS_STATIC OFF CACHE BOOL "" FORCE)
set(SPIRV_CROSS_CLI OFF CACHE BOOL "" FORCE)
set(SPIRV_CROSS_ENABLE_TESTS OFF CACHE BOOL "" FORCE)
set(SPIRV_CROSS_SKIP_INSTALL ON CACHE BOOL "" FORCE)
add_subdirectory("${SOURCES}/spvc" spvc EXCLUDE_FROM_ALL)
set_target_properties(spirv-cross-c-shared PROPERTIES VERSION "" SOVERSION "")

# glslang/SPIRV-Tools must be static inside shaderc, rather than unpublished
# DT_NEEDED dependencies in the resulting Android package.
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
foreach(setting SKIP_TESTS SKIP_EXAMPLES SKIP_EXECUTABLES SKIP_COPYRIGHT_CHECK SKIP_INSTALL)
    set(SHADERC_${setting} ON CACHE BOOL "" FORCE)
endforeach()
set(SHADERC_ENABLE_WERROR_COMPILE OFF CACHE BOOL "" FORCE)
set(SPIRV_SKIP_EXECUTABLES ON CACHE BOOL "" FORCE)
set(SPIRV_SKIP_TESTS ON CACHE BOOL "" FORCE)
set(ENABLE_GLSLANG_BINARIES OFF CACHE BOOL "" FORCE)
set(ENABLE_OPT ON CACHE BOOL "" FORCE)
add_subdirectory("${SOURCES}/shaderc" shaderc EXCLUDE_FROM_ALL)
set_target_properties(shaderc_shared PROPERTIES OUTPUT_NAME shaderc VERSION "" SOVERSION "")

install(TARGETS lwjgl lwjgl_opengl lwjgl_stb lwjgl_vma freetype OpenAL
    shaderc_shared spirv-cross-c-shared LIBRARY DESTINATION arm64-v8a COMPONENT natives)
