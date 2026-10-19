# libffi has an Autotools build upstream. This adapter deliberately supports only
# Android AArch64 LP64 with NDK Clang, so Windows does not require MSYS/Autotools.
set(FFI "${SOURCES}/libffi")
set(FFI_CONFIG "${CMAKE_CURRENT_BINARY_DIR}/ffi-config")
file(MAKE_DIRECTORY "${FFI_CONFIG}")
set(VERSION 3.8.0)
set(TARGET AARCH64)
set(HAVE_LONG_DOUBLE 1)
set(FFI_EXEC_TRAMPOLINE_TABLE 0)
set(FFI_VERSION_STRING 3.8.0)
set(FFI_VERSION_NUMBER 30800)
configure_file("${FFI}/include/ffi.h.in" "${FFI_CONFIG}/ffi.h" @ONLY)
configure_file("${CMAKE_CURRENT_SOURCE_DIR}/cmake/fficonfig.h" "${FFI_CONFIG}/fficonfig.h" COPYONLY)
add_library(ffi STATIC
    "${FFI}/src/prep_cif.c" "${FFI}/src/types.c"
    "${FFI}/src/raw_api.c" "${FFI}/src/java_raw_api.c"
    "${FFI}/src/closures.c" "${FFI}/src/tramp.c"
    "${FFI}/src/aarch64/ffi.c" "${FFI}/src/aarch64/sysv.S")
target_include_directories(ffi PUBLIC "${FFI_CONFIG}" "${FFI}/src/aarch64"
    PRIVATE "${FFI}/include" "${FFI}/src")
target_compile_definitions(ffi PRIVATE FFI_BUILDING _GNU_SOURCE)
# Keep libffi an implementation detail of liblwjgl, not a process-wide ABI.
target_compile_options(ffi PRIVATE -fvisibility=hidden)
