#!/usr/bin/env python3
"""Fetch locked sources, cross-compile, audit and package Android LWJGL natives."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache'
SOURCES = CACHE / 'sources'
LIBRARIES = ['liblwjgl.so', 'liblwjgl_opengl.so', 'liblwjgl_stb.so',
             'liblwjgl_vma.so', 'libfreetype.so', 'libopenal.so',
             'libshaderc.so', 'libspirv-cross-c-shared.so']


def run(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def remove_cached_tree(path):
    resolved = path.resolve()
    if resolved == CACHE.resolve() or not resolved.is_relative_to(CACHE.resolve()):
        raise RuntimeError('Refusing to remove path outside source cache: ' + str(path))
    shutil.rmtree(path)


def fetch(lock):
    SOURCES.mkdir(parents=True, exist_ok=True)
    for name, item in lock['sources'].items():
        archive = CACHE / (name + '-' + item['commit'] + '.tar.gz')
        if not archive.exists() or digest(archive) != item['sha256']:
            temporary = archive.with_suffix('.download')
            url = f"https://codeload.github.com/{item['repo']}/tar.gz/{item['commit']}"
            print('Downloading', name, flush=True)
            # urllib honors HTTPS_PROXY and the Windows system proxy.
            with urllib.request.urlopen(url, timeout=180) as response, temporary.open('wb') as out:
                shutil.copyfileobj(response, out)
            if digest(temporary) != item['sha256']:
                raise RuntimeError('SHA-256 mismatch: ' + name)
            temporary.replace(archive)
        destination = SOURCES / name
        marker = destination / '.source-commit'
        if marker.exists() and marker.read_text().strip() == item['commit']:
            continue
        if destination.exists():
            remove_cached_tree(destination)
        staging = CACHE / ('extract-' + name)
        if staging.exists():
            remove_cached_tree(staging)
        staging.mkdir()
        with tarfile.open(archive) as source:
            source.extractall(staging, filter='data')
        children = list(staging.iterdir())
        if len(children) != 1 or not children[0].is_dir():
            raise RuntimeError('Unexpected archive layout: ' + name)
        children[0].rename(destination)
        staging.rmdir()
        marker.write_text(item['commit'] + '\n')
    # shaderc expects its fixed DEPS sources at these paths; never runs git-sync-deps.
    shader_third_party = SOURCES / 'shaderc' / 'third_party'
    for name in ('glslang', 'spirv-tools', 'spirv-headers'):
        target = shader_third_party / name
        if target.exists():
            if target.is_symlink():
                target.unlink()
            else:
                remove_cached_tree(target)
        shutil.copytree(SOURCES / name, target, ignore=shutil.ignore_patterns('.source-commit'))


def executable(name, sdk):
    suffix = '.exe' if os.name == 'nt' else ''
    pinned = sdk / 'cmake/3.22.1/bin' / (name + suffix)
    if pinned.is_file():
        return pinned
    located = shutil.which(name)
    if located:
        return Path(located)
    installations = sorted((sdk / 'cmake').glob('*/bin/' + name + suffix))
    if installations:
        return installations[-1]
    raise RuntimeError(f'{name} not found; install CMake/Ninja or add them to PATH')


def patch_sources():
    for patch in json.loads((ROOT / 'patches.json').read_text()):
        path = SOURCES / patch['file']
        content = path.read_text(encoding='utf-8')
        if patch['before'] in content:
            if content.count(patch['before']) != 1:
                raise RuntimeError('Ambiguous patch: ' + patch['file'])
            path.write_text(content.replace(patch['before'], patch['after']), encoding='utf-8')
            print('Applied:', patch['reason'], flush=True)
        elif patch['after'] not in content:
            raise RuntimeError('Source patch does not match: ' + patch['file'])


def audit_and_package(ndk, lock, api):
    output = ROOT / 'dist' / 'arm64-v8a'
    host = 'windows-x86_64' if os.name == 'nt' else ('darwin-x86_64' if platform.system() == 'Darwin' else 'linux-x86_64')
    tools = ndk / 'toolchains/llvm/prebuilt' / host / 'bin'
    suffix = '.exe' if os.name == 'nt' else ''
    readelf = tools / ('llvm-readelf' + suffix)
    nm = tools / ('llvm-nm' + suffix)
    allowed = {'libc.so', 'libm.so', 'libdl.so', 'liblog.so', 'libandroid.so',
               'libOpenSLES.so', 'libaaudio.so', 'libc++_shared.so'} | set(LIBRARIES)
    reports = {}
    for name in LIBRARIES:
        file = output / name
        if not file.is_file():
            raise RuntimeError('Missing build output: ' + name)
        run([tools / ('llvm-strip' + suffix), '--strip-unneeded', file])
        elf = subprocess.check_output([str(readelf), '-h', '-d', '-l', str(file)], text=True)
        if 'AArch64' not in elf:
            raise RuntimeError('Incorrect ELF architecture: ' + name)
        needed = re.findall(r'\(NEEDED\).*\[(.*?)\]', elf)
        if set(needed) - allowed:
            raise RuntimeError(f'{name}: unexpected dependencies {set(needed) - allowed}')
        for line in elf.splitlines():
            if line.strip().startswith('LOAD') and int(line.split()[-1], 16) < 16384:
                raise RuntimeError('ELF segment alignment below 16 KiB: ' + name)
        exports = subprocess.check_output([str(nm), '-D', '--defined-only', str(file)], text=True)
        expected = lock['exports'][name]
        missing = [symbol for symbol in expected if not re.search(r'\b' + re.escape(symbol) + r'$', exports, re.M)]
        if missing:
            raise RuntimeError(f'{name}: missing exports {missing}')
        jni_modules = {'liblwjgl.so': 'core', 'liblwjgl_opengl.so': 'opengl',
                       'liblwjgl_stb.so': 'stb', 'liblwjgl_vma.so': 'vma'}
        jni_count = 0
        if name in jni_modules:
            module = jni_modules[name]
            source_root = SOURCES / 'lwjgl/modules/lwjgl' / module / 'src'
            source_files = list((source_root / 'generated/c').glob('*.c')) + list((source_root / 'generated/c').glob('*.cpp'))
            if module == 'core':
                source_files += list((source_root / 'main/c').glob('*.c'))
                source_files += list((source_root / 'generated/c/linux').glob('*.c'))
            declared = set()
            for source in source_files:
                if source.name.startswith('org_lwjgl_opengl_WGL'):
                    continue
                declared.update(re.findall(r'\bJNIEXPORT\s+\w+\s+JNICALL\s+(Java_\w+)\s*\(', source.read_text(encoding='utf-8')))
            exported = set(line.split()[-1] for line in exports.splitlines() if line.strip())
            declared.difference_update(lock.get('platform_excluded_jni_exports', {}).get(name, []))
            if declared - exported:
                raise RuntimeError(f'{name}: missing generated JNI exports {sorted(declared - exported)}')
            jni_count = len(declared)
        reports[name] = {'sha256': digest(file), 'bytes': file.stat().st_size,
                         'needed': needed, 'checked_exports': expected,
                         'checked_jni_exports': jni_count}
    if any('libc++_shared.so' in item['needed'] for item in reports.values()):
        runtime = tools.parent / 'sysroot/usr/lib/aarch64-linux-android/libc++_shared.so'
        runtime_output = output / runtime.name
        shutil.copy2(runtime, runtime_output)
        run([tools / ('llvm-strip' + suffix), '--strip-unneeded', runtime_output])
        runtime_elf = subprocess.check_output([str(readelf), '-h', '-d', '-l', str(runtime_output)], text=True)
        if 'AArch64' not in runtime_elf:
            raise RuntimeError('Incorrect libc++ architecture')
        for line in runtime_elf.splitlines():
            if line.strip().startswith('LOAD') and int(line.split()[-1], 16) < 16384:
                raise RuntimeError('libc++ segment alignment below 16 KiB')
        reports[runtime.name] = {'sha256': digest(runtime_output), 'bytes': runtime_output.stat().st_size,
                                'needed': re.findall(r'\(NEEDED\).*\[(.*?)\]', runtime_elf)}
    manifest = {'lwjgl': lock['lwjgl_version'], 'abi': 'arm64-v8a', 'api': api,
                'ndk': (ndk / 'source.properties').read_text(), 'sources': lock['sources'], 'files': reports}
    dist = ROOT / 'dist'
    (dist / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    licenses = dist / 'licenses'
    licenses.mkdir(exist_ok=True)
    for notice in ('NOTICE', 'NOTICE.toolchain'):
        ndk_notice = ndk / notice
        if ndk_notice.is_file():
            shutil.copy2(ndk_notice, licenses / ('Android-NDK-' + notice))
    for name in lock['sources']:
        source = SOURCES / name
        for path in source.rglob('*'):
            if not path.is_file() or not any(word in path.name.lower() for word in ('license', 'copying', 'notice', 'copyright')):
                continue
            relative = path.relative_to(source)
            # Dependencies copied into shaderc have their own entries in the archive.
            if name == 'shaderc' and relative.parts[0] == 'third_party' and len(relative.parts) > 2 and relative.parts[1] in ('glslang', 'spirv-tools', 'spirv-headers'):
                continue
            target = licenses / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    shutil.copy2(ROOT / 'sources.lock.json', dist / 'sources.lock.json')
    shutil.copy2(ROOT / 'README.md', dist / 'README.md')
    recipe = dist / 'build-recipe'
    recipe.mkdir(exist_ok=True)
    for name in ('build.py', 'CMakeLists.txt', 'patches.json', 'sources.lock.json', 'README.md', 'THIRD-PARTY.md'):
        shutil.copy2(ROOT / name, recipe / name)
    shutil.copytree(ROOT / 'cmake', recipe / 'cmake', dirs_exist_ok=True)
    bundled_sources = dist / 'sources'
    bundled_sources.mkdir(exist_ok=True)
    # Include corresponding source archives, including LGPL OpenAL Soft.
    for name, item in lock['sources'].items():
        archive = CACHE / (name + '-' + item['commit'] + '.tar.gz')
        shutil.copy2(archive, bundled_sources / archive.name)
    package = dist / f"lwjgl-{lock['lwjgl_version']}-android-arm64.zip"
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('arm64-v8a', 'licenses', 'build-recipe', 'sources'):
            for path in sorted((dist / name).rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(dist))
        for name in ('manifest.json', 'sources.lock.json', 'README.md'):
            archive.write(dist / name, name)
    (dist / 'SHA256SUMS').write_text(digest(package) + '  ' + package.name + '\n')
    print('Package:', package, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', default=os.getenv('ANDROID_NDK_HOME') or os.getenv('ANDROID_NDK_ROOT'))
    parser.add_argument('--sdk', default=os.getenv('ANDROID_HOME') or os.getenv('ANDROID_SDK_ROOT') or '')
    parser.add_argument('--api', type=int, default=29)
    parser.add_argument('--jobs', type=int, default=min(os.cpu_count() or 2, 8))
    parser.add_argument('--fetch-only', action='store_true')
    parser.add_argument('--offline', action='store_true', help='Use previously fetched, locked source trees')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'sources.lock.json').read_text())
    if not args.offline:
        fetch(lock)
    else:
        for name, item in lock['sources'].items():
            if (SOURCES / name / '.source-commit').read_text().strip() != item['commit']:
                raise RuntimeError('Source cache does not match lock: ' + name)
    if args.fetch_only:
        return
    patch_sources()
    if not args.ndk:
        parser.error('Pass --ndk or set ANDROID_NDK_HOME')
    ndk = Path(args.ndk).resolve()
    toolchain = ndk / 'build/cmake/android.toolchain.cmake'
    if not toolchain.is_file():
        parser.error('Invalid NDK: ' + str(ndk))
    if args.api < 29:
        parser.error('This build targets Android API 29 or newer')
    sdk = Path(args.sdk).resolve()
    cmake = executable('cmake', sdk)
    ninja = executable('ninja', sdk)
    build = ROOT / 'build' / f'arm64-v8a-api{args.api}'
    temporary = build / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    for variable in ('TEMP', 'TMP', 'TMPDIR'):
        os.environ[variable] = str(temporary)
    run([cmake, '-S', ROOT, '-B', build, '-G', 'Ninja',
         f'-DCMAKE_MAKE_PROGRAM={ninja.as_posix()}', f'-DCMAKE_TOOLCHAIN_FILE={toolchain.as_posix()}',
         '-DANDROID_ABI=arm64-v8a', f'-DANDROID_PLATFORM=android-{args.api}',
         '-DANDROID_STL=c++_shared', '-DCMAKE_BUILD_TYPE=Release',
         f'-DPYTHON_EXECUTABLE={Path(sys.executable).as_posix()}',
         f'-DPython3_EXECUTABLE={Path(sys.executable).as_posix()}',
         f'-DPython_EXECUTABLE={Path(sys.executable).as_posix()}',
         '-DCMAKE_POLICY_VERSION_MINIMUM=3.5'])
    run([cmake, '--build', build, '--parallel', args.jobs, '--target',
         'lwjgl', 'lwjgl_opengl', 'lwjgl_stb', 'lwjgl_vma', 'freetype',
         'OpenAL', 'shaderc_shared', 'spirv-cross-c-shared'])
    run([cmake, '--install', build, '--prefix', ROOT / 'dist', '--component', 'natives'])
    audit_and_package(ndk, lock, args.api)


if __name__ == '__main__':
    main()
