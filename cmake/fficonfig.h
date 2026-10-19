/* Android AArch64 LP64 + NDK Clang configuration for the locked libffi 3.8.0.
 * Undefined platform capabilities are intentionally absent (Autoconf semantics).
 */
#pragma once
#define HAVE_ALLOCA 1
#define HAVE_ALLOCA_H 1
#define HAVE_AS_CFI_PSEUDO_OP 1
#define HAVE_AS_REGISTER_PSEUDO_OP 1
#define HAVE_AS_X86_PCREL 0
#define HAVE_DLFCN_H 1
#define HAVE_INTTYPES_H 1
#define HAVE_MEMORY_H 1
#define HAVE_MEMCPY 1
#define HAVE_MMAP 1
#define HAVE_MMAP_ANON 1
#define HAVE_MMAP_FILE 1
#define HAVE_MKOSTEMP 1
/* bionic's memfd_create wrapper is API 30; this project targets API 29. */
#define HAVE_STDINT_H 1
#define HAVE_STDLIB_H 1
#define HAVE_STRINGS_H 1
#define HAVE_STRING_H 1
#define HAVE_SYS_MMAN_H 1
#define HAVE_SYS_STAT_H 1
#define HAVE_SYS_TYPES_H 1
#define HAVE_UNISTD_H 1
#define HAVE_HIDDEN_VISIBILITY_ATTRIBUTE 1
#define STDC_HEADERS 1
#define SIZEOF_DOUBLE 8
#define SIZEOF_LONG_DOUBLE 16
#define SIZEOF_SIZE_T 8
#define SIZEOF_VOID_P 8
#define FFI_MMAP_EXEC_WRIT 1
#define FFI_EXEC_TRAMPOLINE_TABLE 0
#ifdef LIBFFI_ASM
#define FFI_HIDDEN(name) .hidden name
#else
#define FFI_HIDDEN __attribute__((visibility("hidden")))
#endif
