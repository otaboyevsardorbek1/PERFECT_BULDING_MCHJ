#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import hashlib
import logging
import argparse
import subprocess
import fnmatch
import platform
import shutil
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any, Union
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORMA ANIQLASH VA KUTUBXONALARNI BOSHQARISH
# ═══════════════════════════════════════════════════════════════════════════════

def detect_platform() -> Dict[str, Any]:
    """Ishlayotgan platformani aniqlash"""
    system = platform.system().lower()
    is_android = False
    
    # Android (PyDroid3) ni aniqlash
    if hasattr(sys, 'getandroidapilevel'):
        is_android = True
        system = 'android'
    elif 'ANDROID_STORAGE' in os.environ or 'ANDROID_ROOT' in os.environ:
        is_android = True
        system = 'android'
    
    return {
        'system': system,
        'is_windows': system == 'windows',
        'is_linux': system == 'linux',
        'is_mac': system == 'darwin',
        'is_android': is_android,
        'is_pydroid': is_android,
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': sys.version,
        'python_implementation': platform.python_implementation(),
    }

PLATFORM_INFO = detect_platform()

# Kutubxonalar ro'yxati va ularning minimal versiyalari
REQUIRED_PACKAGES = {
    'pyfiglet': {'min_version': '0.8', 'install_name': 'pyfiglet'},
    'termcolor': {'min_version': '1.0', 'install_name': 'termcolor'},
    'chardet': {'min_version': '4.0', 'install_name': 'chardet'},
}

OPTIONAL_PACKAGES = {
    'psutil': {'min_version': '5.0', 'install_name': 'psutil', 'purpose': 'Tizim statistikasi'},
    'colorama': {'min_version': '0.4', 'install_name': 'colorama', 'purpose': 'Windows rangli chiqish'},
}

def check_package(package_name: str) -> Tuple[bool, Optional[str]]:
    """Paket o'rnatilganligini tekshirish"""
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            return False, None
        
        module = importlib.import_module(package_name)
        version = getattr(module, '__version__', 'unknown')
        return True, version
    except ImportError:
        return False, None

def install_package(package_name: str, install_name: str) -> bool:
    """Paketni o'rnatish"""
    try:
        print(f"  📦 {package_name} o'rnatilmoqda...")
        
        # PyDroid3 uchun maxsus pip
        if PLATFORM_INFO['is_pydroid']:
            import pip
            pip.main(['install', install_name])
        else:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', '-q', install_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        return True
    except Exception as e:
        print(f"  ❌ {package_name} o'rnatishda xato: {e}")
        return False

def check_and_install_dependencies(auto_install: bool = True) -> Tuple[bool, Dict[str, Any]]:
    """Barcha kerakli kutubxonalarni tekshirish va o'rnatish"""
    
    print("\n🔧 KUTUBXONALAR TEKSHIRILMOQDA...")
    print("═" * 50)
    
    missing_packages = []
    installed_packages = {}
    optional_installed = {}
    
    # Asosiy kutubxonalarni tekshirish
    for pkg_name, pkg_info in REQUIRED_PACKAGES.items():
        installed, version = check_package(pkg_name)
        if installed:
            installed_packages[pkg_name] = version
            print(f"  ✅ {pkg_name} v{version}")
        else:
            missing_packages.append((pkg_name, pkg_info['install_name']))
            print(f"  ❌ {pkg_name} topilmadi")
    
    # Qo'shimcha kutubxonalarni tekshirish
    for pkg_name, pkg_info in OPTIONAL_PACKAGES.items():
        installed, version = check_package(pkg_name)
        if installed:
            optional_installed[pkg_name] = version
            print(f"  🔵 {pkg_name} v{version} ({pkg_info['purpose']})")
    
    # O'rnatilmagan kutubxonalarni o'rnatish
    if missing_packages and auto_install:
        print("\n📦 O'RNATILMAGAN KUTUBXONALAR O'RNATILMOQDA...")
        
        for pkg_name, install_name in missing_packages:
            if install_package(pkg_name, install_name):
                installed_packages[pkg_name] = 'just_installed'
                print(f"  ✅ {pkg_name} muvaffaqiyatli o'rnatildi")
            else:
                print(f"\n❌ {pkg_name} ni o'rnatib bo'lmadi!")
                return False, {}
        
        print("\n🔄 Kutubxonalar qayta yuklanmoqda...")
    
    return len(missing_packages) == 0 or (auto_install and missing_packages), installed_packages

# Kutubxonalarni tekshirish va o'rnatish
DEPS_OK, INSTALLED_DEPS = check_and_install_dependencies(auto_install=True)

if not DEPS_OK:
    print("\n" + "═" * 50)
    print("❌ XATOLIK: Kerakli kutubxonalarni o'rnatib bo'lmadi!")
    print("\nQo'lda o'rnatish uchun:")
    print("  pip3 install pyfiglet termcolor chardet")
    print("\nYoki internetga ulanganingizni tekshiring.")
    print("═" * 50)
    sys.exit(1)

# Kutubxonalarni import qilish
try:
    import pyfiglet
    from termcolor import colored
    import chardet
except ImportError as e:
    print(f"❌ Kutubxonalarni import qilishda xato: {e}")
    sys.exit(1)

# psutil ni ixtiyoriy import qilish (xatoliklarni to'liq bartaraf etish)
PSUTIL_AVAILABLE = False
try:
    import psutil
    # Android da psutil ishlashini tekshirish
    if PLATFORM_INFO['is_android']:
        try:
            # Test qilish
            test_cpu = psutil.cpu_count()
            PSUTIL_AVAILABLE = True
        except:
            PSUTIL_AVAILABLE = False
    else:
        PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Windows uchun colorama
if PLATFORM_INFO['is_windows']:
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# TIZIM STATISTIKASI FUNKSIYALARI (PSUTIL BILAN TO'LIQ MOSLASHTIRILGAN)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SystemStats:
    """Tizim statistikasi"""
    # OS ma'lumotlari
    os_name: str = ""
    os_version: str = ""
    os_arch: str = ""
    hostname: str = ""
    
    # CPU ma'lumotlari
    cpu_count_physical: int = 0
    cpu_count_logical: int = 0
    cpu_freq_current: float = 0.0
    cpu_freq_max: float = 0.0
    cpu_percent: float = 0.0
    cpu_percent_per_core: List[float] = field(default_factory=list)
    
    # RAM ma'lumotlari
    ram_total: int = 0
    ram_available: int = 0
    ram_used: int = 0
    ram_percent: float = 0.0
    swap_total: int = 0
    swap_used: int = 0
    swap_percent: float = 0.0
    
    # Disk ma'lumotlari
    disk_total: int = 0
    disk_used: int = 0
    disk_free: int = 0
    disk_percent: float = 0.0
    disk_partitions: List[Dict] = field(default_factory=list)
    
    # Tarmoq ma'lumotlari
    network_interfaces: List[str] = field(default_factory=list)
    
    # Python ma'lumotlari
    python_version: str = ""
    python_compiler: str = ""
    python_implementation: str = ""
    
    # Jarayon ma'lumotlari
    process_pid: int = 0
    process_memory: int = 0
    process_cpu_percent: float = 0.0
    
    # Platforma maxsus
    is_android: bool = False
    android_api_level: int = 0

def get_system_stats() -> SystemStats:
    """To'liq tizim statistikasini yig'ish (psutil bilan xavfsiz)"""
    stats = SystemStats()
    
    # OS ma'lumotlari
    stats.os_name = platform.system()
    stats.os_version = platform.version()
    stats.os_arch = platform.machine()
    stats.hostname = platform.node()
    
    # Android ma'lumotlari
    stats.is_android = PLATFORM_INFO['is_android']
    if stats.is_android:
        try:
            stats.android_api_level = sys.getandroidapilevel() if hasattr(sys, 'getandroidapilevel') else 0
        except:
            pass
    
    # Python ma'lumotlari
    stats.python_version = platform.python_version()
    stats.python_compiler = platform.python_compiler()
    stats.python_implementation = platform.python_implementation()
    
    # Jarayon ma'lumotlari
    stats.process_pid = os.getpid()
    
    if PSUTIL_AVAILABLE:
        try:
            # CPU - xavfsiz olish
            try:
                stats.cpu_count_physical = psutil.cpu_count(logical=False) or 0
            except:
                stats.cpu_count_physical = 0
            
            try:
                stats.cpu_count_logical = psutil.cpu_count(logical=True) or cpu_count()
            except:
                stats.cpu_count_logical = cpu_count()
            
            try:
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    stats.cpu_freq_current = cpu_freq.current or 0.0
                    stats.cpu_freq_max = cpu_freq.max or 0.0
            except:
                pass
            
            try:
                stats.cpu_percent = psutil.cpu_percent(interval=0.1) or 0.0
            except:
                pass
            
            # RAM - xavfsiz olish
            try:
                mem = psutil.virtual_memory()
                stats.ram_total = mem.total
                stats.ram_available = mem.available
                stats.ram_used = mem.used
                stats.ram_percent = mem.percent
            except:
                pass
            
            try:
                swap = psutil.swap_memory()
                stats.swap_total = swap.total
                stats.swap_used = swap.used
                stats.swap_percent = swap.percent
            except:
                pass
            
            # Disk - xavfsiz olish
            try:
                if stats.is_android:
                    # Android uchun disk ma'lumotlari
                    disk = os.statvfs(os.getcwd())
                    stats.disk_total = disk.f_frsize * disk.f_blocks
                    stats.disk_free = disk.f_frsize * disk.f_bavail
                    stats.disk_used = stats.disk_total - stats.disk_free
                    stats.disk_percent = (stats.disk_used / stats.disk_total) * 100 if stats.disk_total > 0 else 0
                else:
                    disk = psutil.disk_usage('/')
                    stats.disk_total = disk.total
                    stats.disk_used = disk.used
                    stats.disk_free = disk.free
                    stats.disk_percent = disk.percent
            except:
                # Fallback disk ma'lumoti
                try:
                    disk = os.statvfs(os.getcwd())
                    stats.disk_total = disk.f_frsize * disk.f_blocks
                    stats.disk_free = disk.f_frsize * disk.f_bavail
                    stats.disk_used = stats.disk_total - stats.disk_free
                    stats.disk_percent = (stats.disk_used / stats.disk_total) * 100 if stats.disk_total > 0 else 0
                except:
                    pass
            
            # Tarmoq - xavfsiz olish
            try:
                net_if = psutil.net_if_addrs()
                stats.network_interfaces = list(net_if.keys())
            except:
                pass
            
            # Jarayon - xavfsiz olish
            try:
                process = psutil.Process()
                stats.process_memory = process.memory_info().rss
                stats.process_cpu_percent = process.cpu_percent(interval=0.1)
            except:
                pass
            
        except Exception as e:
            logging.debug(f"Tizim statistikasini olishda xato: {e}")
    
    # psutil bo'lmasa yoki xato bo'lsa, fallback
    if stats.cpu_count_logical == 0:
        stats.cpu_count_logical = cpu_count()
    
    if stats.disk_total == 0:
        try:
            if PLATFORM_INFO['is_windows']:
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(os.getcwd()), 
                    None, 
                    ctypes.pointer(total_bytes), 
                    ctypes.pointer(free_bytes)
                )
                stats.disk_total = total_bytes.value
                stats.disk_free = free_bytes.value
                stats.disk_used = stats.disk_total - stats.disk_free
                stats.disk_percent = (stats.disk_used / stats.disk_total) * 100 if stats.disk_total > 0 else 0
            else:
                disk = os.statvfs(os.getcwd())
                stats.disk_total = disk.f_frsize * disk.f_blocks
                stats.disk_free = disk.f_frsize * disk.f_bavail
                stats.disk_used = stats.disk_total - stats.disk_free
                stats.disk_percent = (stats.disk_used / stats.disk_total) * 100 if stats.disk_total > 0 else 0
        except:
            pass
    
    return stats

def format_size(size_bytes: int) -> str:
    """Hajmni inson o'qiy oladigan formatga o'tkazish"""
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def print_system_stats(stats: SystemStats, verbose: bool = False):
    """Tizim statistikasini chiqarish"""
    
    print(colored("\n🖥️  TIZIM STATISTIKASI", 'cyan', attrs=['bold']))
    print(colored("═" * 60, 'white'))
    
    # OS ma'lumotlari
    print(colored("📋 OPERATSION TIZIM:", 'yellow'))
    print(f"  • Nom: {stats.os_name} {stats.os_version}")
    print(f"  • Arxitektura: {stats.os_arch}")
    print(f"  • Hostname: {stats.hostname}")
    
    if stats.is_android:
        print(colored(f"  • Android (PyDroid3) - API Level: {stats.android_api_level}", 'green'))
    
    # Python ma'lumotlari
    print(colored("\n🐍 PYTHON MUHITI:", 'yellow'))
    print(f"  • Versiya: {stats.python_version}")
    print(f"  • Implementatsiya: {stats.python_implementation}")
    if verbose:
        print(f"  • Kompilyator: {stats.python_compiler}")
    
    # CPU ma'lumotlari
    print(colored("\n⚡ PROTSESSOR (CPU):", 'yellow'))
    if stats.cpu_count_physical > 0:
        print(f"  • Fizik yadrolar: {stats.cpu_count_physical}")
    print(f"  • Mantiqiy yadrolar: {stats.cpu_count_logical}")
    if stats.cpu_freq_current > 0:
        print(f"  • Chastota: {stats.cpu_freq_current:.0f} MHz (Maks: {stats.cpu_freq_max:.0f} MHz)")
    if stats.cpu_percent > 0:
        print(f"  • Yuklanish: {stats.cpu_percent:.1f}%")
    
    # RAM ma'lumotlari
    print(colored("\n🧠 XOTIRA (RAM):", 'yellow'))
    if stats.ram_total > 0:
        print(f"  • Jami: {format_size(stats.ram_total)}")
        print(f"  • Band: {format_size(stats.ram_used)} ({stats.ram_percent:.1f}%)")
        print(f"  • Bo'sh: {format_size(stats.ram_available)}")
    else:
        print(f"  • RAM ma'lumoti mavjud emas")
    
    if stats.swap_total > 0:
        print(f"  • SWAP: {format_size(stats.swap_used)} / {format_size(stats.swap_total)} ({stats.swap_percent:.1f}%)")
    
    # Disk ma'lumotlari
    print(colored("\n💾 DISK:", 'yellow'))
    print(f"  • Jami: {format_size(stats.disk_total)}")
    print(f"  • Band: {format_size(stats.disk_used)} ({stats.disk_percent:.1f}%)")
    print(f"  • Bo'sh: {format_size(stats.disk_free)}")
    
    if verbose and stats.disk_partitions:
        print(colored("  • Bo'limlar:", 'white'))
        for part in stats.disk_partitions[:5]:
            print(f"    - {part['mountpoint']}: {format_size(part['total'])} "
                  f"(Band: {part['percent']:.1f}%)")
    
    # Tarmoq
    if verbose and stats.network_interfaces:
        print(colored("\n🌐 TARMOQ INTERFEYSLARI:", 'yellow'))
        for iface in stats.network_interfaces[:5]:
            print(f"  • {iface}")
    
    # Jarayon ma'lumotlari
    print(colored("\n📊 DASTUR JARAYONI:", 'yellow'))
    print(f"  • PID: {stats.process_pid}")
    if stats.process_memory > 0:
        print(f"  • Xotira: {format_size(stats.process_memory)}")
    
    print(colored("═" * 60, 'white'))

# ═══════════════════════════════════════════════════════════════════════════════
# BARCHA DASTURLASH TILLARI VA MATN FORMATLARI
# ═══════════════════════════════════════════════════════════════════════════════

SUPPORTED_EXTENSIONS = {
    # ===== WEB DASTURLASH =====
    'html', 'htm', 'xhtml', 'dhtml', 'shtml',
    'css', 'scss', 'sass', 'less', 'styl', 'stylus',
    'js', 'mjs', 'cjs', 'jsx', 'ts', 'tsx', 'coffee', 'litcoffee',
    'vue', 'svelte', 'astro', 'solid', 'qwik',
    'php', 'phtml', 'php3', 'php4', 'php5', 'php7', 'php8', 'phps',
    'asp', 'aspx', 'ascx', 'asmx', 'ashx', 'axd', 'asax',
    'jsp', 'jspf', 'jspx', 'do', 'action', 'tag', 'tld',
    'ejs', 'pug', 'jade', 'haml', 'slim', 'twig', 'blade', 'mustache', 'handlebars', 'hbs',
    'liquid', 'njk', 'nunjucks',
    
    # ===== PYTHON ECOSYSTEM =====
    'py', 'pyw', 'pyi', 'pyx', 'pxd', 'pxi',
    'ipynb',
    'rpy', 'cpy', 'gyp', 'gypi',
    
    # ===== JAVA ECOSYSTEM =====
    'java', 'jav',
    'groovy', 'gvy', 'gy', 'gsh', 'gradle',
    'kt', 'kts', 'ktm',
    'scala', 'sc', 'sbt',
    'clj', 'cljs', 'cljc', 'edn',
    
    # ===== C/C++ ECOSYSTEM =====
    'c', 'h', 'cc', 'cpp', 'cxx', 'c++', 'hh', 'hpp', 'hxx', 'h++',
    'm', 'mm',
    'cs', 'csx', 'csproj',
    
    # ===== .NET ECOSYSTEM =====
    'vb', 'vbs', 'vba', 'bas', 'frm', 'cls',
    'fs', 'fsi', 'fsx', 'fsscript',
    'ps1', 'psm1', 'psd1', 'psc1',
    
    # ===== RUBY =====
    'rb', 'rbw', 'rake', 'gemspec', 'rbx', 'rhtml', 'ru',
    
    # ===== GO =====
    'go', 'mod', 'sum', 'tmpl',
    
    # ===== RUST =====
    'rs', 'rlib',
    
    # ===== SWIFT =====
    'swift', 'storyboard', 'xib', 'plist',
    
    # ===== DART/FLUTTER =====
    'dart',
    
    # ===== FUNCTIONAL =====
    'hs', 'lhs', 'erl', 'hrl', 'ex', 'exs', 'eex',
    'ml', 'mli', 'lisp', 'cl', 'rkt', 'scm',
    
    # ===== SHELL/SCRIPTING =====
    'sh', 'bash', 'zsh', 'fish', 'bat', 'cmd',
    'pl', 'pm', 'lua', 'tcl', 'r', 'R', 'Rmd', 'jl',
    
    # ===== DATABASE =====
    'sql', 'mysql', 'psql', 'plsql', 'tsql', 'sqlite',
    'prisma',
    
    # ===== CONFIGURATION =====
    'json', 'json5', 'jsonc',
    'xml', 'xsd', 'xsl', 'xslt', 'svg',
    'yml', 'yaml',
    'ini', 'cfg', 'conf', 'config',
    'properties', 'prop',
    'env', 'envrc',
    'toml',
    'htaccess', 'editorconfig', 'gitignore', 'dockerignore',
    
    # ===== MARKUP =====
    'md', 'markdown', 'rst', 'adoc', 'asciidoc',
    'tex', 'sty', 'bib', 'latex',
    'org', 'wiki',
    
    # ===== DATA FORMATS =====
    'csv', 'tsv',
    'proto', 'graphql', 'gql',
    
    # ===== BUILD SYSTEMS =====
    'make', 'mk', 'cmake',
    'dockerfile', 'vagrantfile',
    'tf', 'tfvars', 'hcl',
    
    # ===== CI/CD =====
    'travis.yml', 'gitlab-ci.yml', 'jenkinsfile',
    
    # ===== TEXT & LOGS =====
    'txt', 'text', 'log',
    
    # ===== GAME DEV =====
    'gd', 'shader', 'hlsl', 'glsl',
    
    # ===== ASSEMBLY =====
    'asm', 's', 'nasm',
    
    # ===== FORTRAN =====
    'f', 'for', 'f90', 'f95', 'f03', 'f08',
    
    # ===== COBOL =====
    'cob', 'cbl', 'cobol',
    
    # ===== PASCAL =====
    'pas', 'pp', 'dpr',
    
    # ===== ADA =====
    'adb', 'ads', 'ada',
    
    # ===== VERILOG/VHDL =====
    'v', 'vh', 'vhd', 'vhdl', 'sv',
    
    # ===== MATLAB =====
    'm', 'mat',
    
    # ===== OTHER =====
    'nim', 'cr', 'zig', 'hx', 'd', 'sol', 'vy',
    
    # ===== PACKAGE MANAGERS =====
    'lock', 'toml',
    'requirements.txt', 'pipfile', 'pyproject.toml',
    'cargo.toml', 'composer.json', 'package.json',
    'setup.py', 'setup.cfg',
    
    # ===== SECURITY =====
    'pem', 'crt', 'key', 'pub',
    
    # ===== MISCELLANEOUS =====
    'desktop', 'service', 'xaml', 'qml', 'vala',
}

# SKIP QILINADIGAN BINARY VA MEDIA FAYL FORMATLARI
BINARY_AND_MEDIA_EXTENSIONS = {
    # Rasmlar
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'webp', 'svgz',
    'ico', 'icns', 'heic', 'heif', 'avif', 'psd', 'ai', 'eps',
    'raw', 'cr2', 'nef', 'arw', 'dng',
    
    # Audio
    'mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a', 'opus', 'wma', 'mid', 'midi',
    
    # Video
    'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v', 'mpg', 'mpeg',
    
    # Arxivlar
    'zip', 'tar', 'gz', 'bz2', 'xz', '7z', 'rar', 'zst',
    
    # Executable/Binary
    'exe', 'dll', 'so', 'dylib', 'a', 'lib', 'obj', 'o', 'ko', 'sys',
    'bin', 'elf', 'macho', 'msi', 'app', 'deb', 'rpm', 'apk', 'ipa',
    
    # Ma'lumotlar bazasi
    'db', 'sqlite', 'sqlite3', 'mdb', 'accdb',
    
    # Fontlar
    'ttf', 'otf', 'woff', 'woff2', 'eot',
    
    # Boshqa binary
    'pyc', 'pyo', 'pyd', 'class', 'wasm', 'pdb', 'cache',
    
    # 3D Model
    'blend', 'max', '3ds', 'obj', 'fbx', 'dae', 'gltf', 'glb', 'stl',
    
    # Disk images
    'iso', 'img', 'dmg', 'vhd', 'vhdx', 'vmdk',
}

# SKIP QILINADIGAN PAPKALAR
SKIP_FOLDERS = {
    # Virtual environments
    'venv', 'env', '.env', '.venv', 'virtualenv',
    
    # Node.js
    'node_modules', 'bower_components',
    
    # Version control
    '.git', '.svn', '.hg', '.github',
    
    # Python
    '__pycache__', '.pytest_cache', '.mypy_cache', '.tox', '.nox',
    'htmlcov', '.coverage', 'coverage', '.cache', '.eggs',
    'build', 'dist', 'develop-eggs', 'eggs',
    
    # Windows venv
    'Lib', 'Scripts', 'Include',
    
    # Linux venv
    'bin', 'lib', 'lib64', 'include',
    
    # Package directories
    'site-packages', 'dist-packages',
    
    # IDE
    '.idea', '.vscode', '.vs', '.eclipse', '.settings',
    '.android', '.gradle',
    
    # Build
    'target', 'out', 'output', 'bin', 'obj', 'Debug', 'Release',
    'build', 'dist', '.next', '.nuxt',
    
    # Temp
    'tmp', 'temp', '.tmp', 'cache', '.cache', 'logs',
    
    # Docker
    '.docker',
    
    # Package managers
    'vendor', 'packages',
    
    # Windows tizim papkalari (C: disk skanerlashda skip)
    'Windows', 'Program Files', 'Program Files (x86)', 'ProgramData',
    'System32', 'SysWOW64', 'WinSxS', 'Microsoft.NET',
    'Recovery', 'System Volume Information', '$Recycle.Bin',
    'Config.Msi', 'MSOCache', 'PerfLogs',
    
    # Linux tizim papkalari
    'proc', 'sys', 'dev', 'run', 'boot', 'etc', 'var', 'usr', 'sbin',
    'lost+found', 'mnt', 'media', 'srv', 'opt',
    
    # Mac tizim papkalari
    'System', 'Library', 'Applications',
}

# SKIP QILINADIGAN FAYL PATTERNLARI
SKIP_FILE_PATTERNS = [
    '*.pyc', '*.pyo', '*.pyd',
    '*.class', '*.jar', '*.war', '*.ear',
    '*.exe', '*.dll', '*.so', '*.dylib',
    '*.min.js', '*.min.css', '*.bundle.js', '*.chunk.js',
    '*.map', '*.js.map', '*.css.map',
    '*.lock', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    '*.log', '*.bak', '*.backup', '*.old',
    '*.tmp', '*.temp', '*.swp', '*.swo', '*~',
    '.DS_Store', 'Thumbs.db', 'desktop.ini',
    '*.zip', '*.tar', '*.gz', '*.bz2', '*.7z', '*.rar',
    '*.pdf', '*.doc', '*.docx', '*.xls', '*.xlsx', '*.ppt', '*.pptx',
    'CodeAnalyzer*.py',
    'respons_*.*',
]

# ═══════════════════════════════════════════════════════════════════════════════
# MA'LUMOT KLASSLARI
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FileInfo:
    """Fayl haqida to'liq ma'lumot"""
    path: str
    name: str
    extension: str
    size: int
    lines: int = 0
    content: str = ""
    hash: str = ""
    encoding: str = "utf-8"
    error: Optional[str] = None
    
@dataclass
class AnalysisStats:
    """Tahlil statistikasi"""
    total_files: int = 0
    total_lines: int = 0
    total_size: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    error_files: int = 0
    file_types: Dict[str, Dict[str, int]] = field(default_factory=dict)
    largest_files: List[Tuple[str, int, int]] = field(default_factory=list)
    encoding_stats: Dict[str, int] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

# ═══════════════════════════════════════════════════════════════════════════════
# MENYU TIZIMI
# ═══════════════════════════════════════════════════════════════════════════════

def get_system_root() -> str:
    """Tizimning asosiy diskini/qismini aniqlash"""
    if PLATFORM_INFO['is_windows']:
        return "C:\\"
    elif PLATFORM_INFO['is_android']:
        return "/storage/emulated/0"
    else:
        return "/"

def get_current_directory() -> str:
    """Joriy papkani aniqlash"""
    return os.getcwd()

def show_menu_and_get_path() -> Optional[str]:
    """
    Foydalanuvchiga menyu ko'rsatish va tanlangan yo'lni qaytarish
    
    Returns:
        Tanlangan yo'l yoki None (agar chiqish tanlansa)
    """
    print(colored("\n" + "═" * 60, 'yellow'))
    print(colored("📁 SKANERLASH MENYUSI", 'cyan', attrs=['bold']))
    print(colored("═" * 60, 'yellow'))
    print()
    print(colored("  1️⃣  Tizimning asosiy diskini skanerlash", 'white'))
    
    system_root = get_system_root()
    if PLATFORM_INFO['is_windows']:
        print(colored(f"      📍 Yo'l: {system_root} (C: disk)", 'blue'))
    elif PLATFORM_INFO['is_android']:
        print(colored(f"      📍 Yo'l: {system_root} (Ichki xotira)", 'blue'))
    else:
        print(colored(f"      📍 Yo'l: {system_root} (Root)", 'blue'))
    
    print()
    print(colored("  2️⃣  Joriy papkani skanerlash", 'white'))
    current_dir = get_current_directory()
    print(colored(f"      📍 Yo'l: {current_dir}", 'blue'))
    
    print()
    print(colored("  3️⃣  Boshqa yo'l kiritish", 'white'))
    print()
    print(colored("  0️⃣  Chiqish", 'red'))
    print()
    print(colored("═" * 60, 'yellow'))
    
    # Ogohlantirish
    print(colored("\n⚠️  OGOHLANTIRISH:", 'yellow', attrs=['bold']))
    print(colored("   Asosiy diskni skanerlash juda ko'p vaqt olishi mumkin!", 'yellow'))
    print(colored("   Tizim papkalari (Windows, Program Files, etc) avtomatik skip qilinadi.", 'yellow'))
    print()
    
    while True:
        try:
            choice = input(colored("➡️  Tanlang (1/2/3/0): ", 'green')).strip()
            
            if choice == '1':
                # Asosiy diskni skanerlash
                root_path = get_system_root()
                
                # Tasdiqlash
                print(colored(f"\n⚠️  {root_path} diskni skanerlash ko'p vaqt olishi mumkin!", 'yellow'))
                confirm = input(colored("Davom etishni xohlaysizmi? (ha/yo'q): ", 'green')).strip().lower()
                
                if confirm in ['ha', 'h', 'yes', 'y', '1']:
                    return root_path
                else:
                    print(colored("❌ Bekor qilindi.", 'red'))
                    continue
                
            elif choice == '2':
                # Joriy papkani skanerlash
                return get_current_directory()
                
            elif choice == '3':
                # Boshqa yo'l kiritish
                custom_path = input(colored("\n📁 Yo'lni kiriting: ", 'green')).strip()
                if custom_path:
                    if os.path.isdir(custom_path):
                        return custom_path
                    else:
                        print(colored(f"❌ '{custom_path}' papkasi mavjud emas!", 'red'))
                        continue
                else:
                    print(colored("❌ Yo'l kiritilmadi!", 'red'))
                    continue
                    
            elif choice == '0':
                return None
                
            else:
                print(colored("❌ Noto'g'ri tanlov! 1, 2, 3 yoki 0 kiriting.", 'red'))
                
        except KeyboardInterrupt:
            print(colored("\n\n⚠️  Bekor qilindi!", 'yellow'))
            return None

# ═══════════════════════════════════════════════════════════════════════════════
# UTILIT FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════════════════════

def clear_screen():
    """Ekran tozalash (platformaga qarab)"""
    if PLATFORM_INFO['is_windows']:
        os.system('cls')
    else:
        os.system('clear')

def print_banner():
    """Bannerni chiqarish"""
    clear_screen()
    
    # Windows da rangni yoqish
    if PLATFORM_INFO['is_windows']:
        os.system('color')
    
    banner = pyfiglet.figlet_format("CODE ANALYZER", font='slant')
    print(colored(banner, 'red'))
    
    platform_str = "WINDOWS" if PLATFORM_INFO['is_windows'] else \
                   "LINUX" if PLATFORM_INFO['is_linux'] else \
                   "MAC OS" if PLATFORM_INFO['is_mac'] else \
                   "ANDROID (PyDroid3)" if PLATFORM_INFO['is_android'] else "UNKNOWN"
    
    print(colored("╔" + "═" * 68 + "╗", 'yellow'))
    print(colored("║" + " PRO ULTIMATE EDITION - Cross-Platform Code Analyzer".center(68) + "║", 'cyan'))
    print(colored("║" + f" Platforma: {platform_str}".center(68) + "║", 'green'))
    print(colored("║" + " Barcha dasturlash tillari | Binary/media skip".center(68) + "║", 'green'))
    print(colored("║" + " Menyu tizimi | JSON asl tartibda".center(68) + "║", 'green'))
    print(colored("╠" + "═" * 68 + "╣", 'yellow'))
    print(colored("║  📧 Email: prodevuzoff@gmail.com".ljust(69) + "║", 'blue'))
    print(colored("║  📱 Telegram: @otaboyev_sardorbek_blog_dev".ljust(69) + "║", 'cyan'))
    print(colored("║  🐙 GitHub: github.com/otaboyevsardorbek1/CodeAnalyzer".ljust(69) + "║", 'yellow'))
    print(colored("╚" + "═" * 68 + "╝", 'yellow'))
    print()

def setup_logging(output_folder: str, verbose: bool = False) -> None:
    """Logging tizimini sozlash"""
    log_file = os.path.join(output_folder, 'code_analyzer.log')
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout) if verbose else logging.NullHandler()
        ]
    )

def should_skip_path(path: str, custom_skip_patterns: List[str] = None) -> Tuple[bool, str]:
    """Berilgan yo'lni skip qilish kerakmi?"""
    path_obj = Path(path)
    path_parts = path_obj.parts
    
    # Skip papkalarni tekshirish
    for part in path_parts:
        if part in SKIP_FOLDERS:
            return True, f"Skip papka: {part}"
    
    # Fayl nomini tekshirish
    if os.path.isfile(path):
        filename = path_obj.name
        extension = path_obj.suffix.lower()
        
        # Binary/media kengaytmalarni tekshirish
        if extension and extension[1:] in BINARY_AND_MEDIA_EXTENSIONS:
            return True, f"Binary/media fayl: {extension}"
        
        # Pattern bo'yicha tekshirish
        all_patterns = SKIP_FILE_PATTERNS.copy()
        if custom_skip_patterns:
            all_patterns.extend(custom_skip_patterns)
        
        for pattern in all_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True, f"Skip pattern: {pattern}"
    
    return False, ""

def detect_encoding(filepath: str) -> str:
    """Fayl kodirovkasini aniqlash"""
    try:
        with open(filepath, 'rb') as f:
            raw_data = f.read(100000)
            result = chardet.detect(raw_data)
            return result['encoding'] if result['encoding'] else 'utf-8'
    except:
        return 'utf-8'

def read_file_safely(filepath: str, max_size_mb: int = 50) -> FileInfo:
    """Faylni xavfsiz o'qish"""
    file_info = FileInfo(
        path=filepath,
        name=os.path.basename(filepath),
        extension=os.path.splitext(filepath)[1].lower(),
        size=os.path.getsize(filepath)
    )
    
    try:
        size_mb = file_info.size / (1024 * 1024)
        if size_mb > max_size_mb:
            file_info.error = f"Hajm limiti: {size_mb:.1f}MB > {max_size_mb}MB"
            return file_info
        
        file_info.encoding = detect_encoding(filepath)
        
        with open(filepath, 'r', encoding=file_info.encoding, errors='ignore') as f:
            file_info.content = f.read()
        
        file_info.lines = file_info.content.count('\n') + 1
        file_info.hash = hashlib.sha256(file_info.content.encode('utf-8')).hexdigest()[:16]
        
    except Exception as e:
        file_info.error = f"O'qish xatosi: {str(e)}"
    
    return file_info

def print_progress(current: int, total: int, bar_length: int = 40) -> None:
    """Progress barni chiqarish"""
    if total == 0:
        return
    
    percent = current / total
    filled = int(round(percent * bar_length))
    bar = '█' * filled + '░' * (bar_length - filled)
    
    sys.stdout.write(f"\r[{colored(bar, 'green')}] {current}/{total} ({percent:.1%})")
    sys.stdout.flush()

def get_git_info(root_folder: str) -> Dict[str, Any]:
    """Git repository ma'lumotlarini olish"""
    git_info = {
        'is_git_repo': False,
        'branch': None,
        'last_commit': None,
        'remote_url': None,
        'total_commits': None
    }
    
    if PLATFORM_INFO['is_android']:
        return git_info
    
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=root_folder, capture_output=True, text=True, timeout=5
        )
        
        if result.returncode == 0:
            git_info['is_git_repo'] = True
            
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=root_folder, capture_output=True, text=True, timeout=5
            )
            git_info['branch'] = result.stdout.strip()
            
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%H|%s|%an|%ad'],
                cwd=root_folder, capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                parts = result.stdout.strip().split('|')
                git_info['last_commit'] = {
                    'hash': parts[0][:8] if len(parts) > 0 else '',
                    'message': parts[1] if len(parts) > 1 else '',
                    'author': parts[2] if len(parts) > 2 else '',
                    'date': parts[3] if len(parts) > 3 else ''
                }
            
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=root_folder, capture_output=True, text=True, timeout=5
            )
            git_info['remote_url'] = result.stdout.strip()
            
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD'],
                cwd=root_folder, capture_output=True, text=True, timeout=10
            )
            if result.stdout.strip():
                git_info['total_commits'] = int(result.stdout.strip())
            
    except:
        pass
    
    return git_info

# ═══════════════════════════════════════════════════════════════════════════════
# ASOSIY ANALIZ FUNKSIYALARI
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_folder(root_folder: str, max_workers: int = None, 
                   max_size_mb: int = 50, custom_skip_patterns: List[str] = None,
                   verbose: bool = False) -> Tuple[Dict, AnalysisStats, Set[str]]:
    """Papkani tahlil qilish"""
    
    if max_workers is None:
        if PLATFORM_INFO['is_android']:
            max_workers = 2
        else:
            max_workers = min(cpu_count(), 8)
    
    stats = AnalysisStats()
    stats.start_time = datetime.now()
    
    structure = {}
    existing_extensions = set()
    
    print(colored("\n📂 Fayllar skanerlanmoqda...", 'cyan'))
    
    file_list = []
    skipped_reasons = defaultdict(int)
    
    # Asosiy disk skanerlanayotgan bo'lsa, ogohlantirish
    is_system_root = root_folder in ['C:\\', 'C:', '/', '/storage/emulated/0']
    if is_system_root:
        print(colored("⚠️  Asosiy disk skanerlanmoqda - bu ko'p vaqt olishi mumkin!", 'yellow'))
    
    for root, dirs, files in os.walk(root_folder):
        # Skip papkalarni filtrash
        dirs[:] = [d for d in dirs if not should_skip_path(os.path.join(root, d))[0]]
        
        for file in files:
            full_path = os.path.join(root, file)
            skip, reason = should_skip_path(full_path, custom_skip_patterns)
            
            if skip:
                stats.skipped_files += 1
                skipped_reasons[reason] += 1
                continue
            
            ext = os.path.splitext(file)[1].lower()
            if ext and ext[1:] in SUPPORTED_EXTENSIONS:
                file_list.append(full_path)
                existing_extensions.add(ext[1:])
            elif not ext:
                if file.upper() in ['DOCKERFILE', 'MAKEFILE', 'JENKINSFILE', 'VAGRANTFILE']:
                    file_list.append(full_path)
                    existing_extensions.add(file.lower())
    
    stats.total_files = len(file_list)
    
    if stats.total_files == 0:
        print(colored("\n⚠️  Tahlil qilinadigan fayllar topilmadi!", 'yellow'))
        return structure, stats, existing_extensions
    
    print(colored(f"\n📊 {stats.total_files} ta fayl topildi", 'green'))
    if stats.skipped_files > 0:
        print(colored(f"⏭️  {stats.skipped_files} ta fayl skip qilindi", 'yellow'))
        if verbose:
            for reason, count in skipped_reasons.items():
                print(colored(f"   - {reason}: {count} ta", 'white'))
    
    print(colored(f"\n🚀 Tahlil boshlandi ({max_workers} ta ishchi)...", 'cyan'))
    
    processed = 0
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(read_file_safely, fp, max_size_mb): fp 
            for fp in file_list
        }
        
        for future in as_completed(future_to_file):
            filepath = future_to_file[future]
            processed += 1
            
            try:
                file_info = future.result()
                
                if file_info.error:
                    stats.error_files += 1
                    results[filepath] = f"// ERROR: {file_info.error}"
                else:
                    stats.processed_files += 1
                    stats.total_lines += file_info.lines
                    stats.total_size += file_info.size
                    
                    ext = file_info.extension[1:] if file_info.extension else 'no_ext'
                    if ext not in stats.file_types:
                        stats.file_types[ext] = {'count': 0, 'lines': 0, 'size': 0}
                    stats.file_types[ext]['count'] += 1
                    stats.file_types[ext]['lines'] += file_info.lines
                    stats.file_types[ext]['size'] += file_info.size
                    
                    stats.encoding_stats[file_info.encoding] = stats.encoding_stats.get(file_info.encoding, 0) + 1
                    
                    stats.largest_files.append((filepath, file_info.size, file_info.lines))
                    stats.largest_files.sort(key=lambda x: x[1], reverse=True)
                    stats.largest_files = stats.largest_files[:20]
                    
                    results[filepath] = file_info.content
                
                print_progress(processed, stats.total_files)
                
            except Exception as e:
                stats.error_files += 1
                results[filepath] = f"// ERROR: {str(e)}"
    
    print()
    
    print(colored("\n📁 JSON struktura qurilmoqda...", 'cyan'))
    
    for filepath, content in results.items():
        rel_path = os.path.relpath(filepath, root_folder)
        folder = os.path.dirname(rel_path)
        filename = os.path.basename(filepath)
        
        if folder not in structure:
            structure[folder] = {}
        structure[folder][filename] = content
    
    stats.end_time = datetime.now()
    
    return structure, stats, existing_extensions

def generate_html_report(stats: AnalysisStats, git_info: Dict, 
                         output_folder: str, structure: Dict,
                         system_stats: SystemStats) -> str:
    """HTML hisobot generatsiya qilish"""
    
    report_file = os.path.join(output_folder, 'analysis_report.html')
    duration = stats.duration_seconds()
    
    html = f'''<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Analyzer Pro - Analysis Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', 'Roboto', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
        }}
        .stat-card .number {{
            font-size: 3em;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .section {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.8em;
            border-bottom: 2px solid rgba(102,126,234,0.3);
            padding-bottom: 10px;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        th {{ background: rgba(102,126,234,0.2); color: #fff; }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .footer {{ text-align: center; padding: 20px; color: #666; }}
        .success {{ color: #51cf66; }}
        .error {{ color: #ff6b6b; }}
        .warning {{ color: #ffd43b; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Code Analysis Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Duration: {duration:.2f} seconds | Platform: {system_stats.os_name}</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="number">{stats.processed_files:,}</div>
                <div class="label">Processed Files</div>
            </div>
            <div class="stat-card">
                <div class="number">{stats.total_lines:,}</div>
                <div class="label">Total Lines</div>
            </div>
            <div class="stat-card">
                <div class="number">{stats.total_size / (1024*1024):.2f}</div>
                <div class="label">Total Size (MB)</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(stats.file_types)}</div>
                <div class="label">File Types</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🖥️ System Information</h2>
            <table>
                <tr><td>OS:</td><td>{system_stats.os_name} {system_stats.os_version}</td></tr>
                <tr><td>Architecture:</td><td>{system_stats.os_arch}</td></tr>
                <tr><td>CPU Cores:</td><td>{system_stats.cpu_count_logical} logical</td></tr>
                <tr><td>RAM Total:</td><td>{format_size(system_stats.ram_total)}</td></tr>
                <tr><td>Disk Total:</td><td>{format_size(system_stats.disk_total)}</td></tr>
                <tr><td>Disk Free:</td><td>{format_size(system_stats.disk_free)}</td></tr>
                <tr><td>Python:</td><td>{system_stats.python_version}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>📈 Analysis Statistics</h2>
            <table>
                <tr><td>Total Files Found:</td><td>{stats.total_files:,}</td></tr>
                <tr><td>Successfully Processed:</td><td class="success">{stats.processed_files:,}</td></tr>
                <tr><td>Skipped Files:</td><td class="warning">{stats.skipped_files:,}</td></tr>
                <tr><td>Files with Errors:</td><td class="error">{stats.error_files:,}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>📁 File Types Distribution</h2>
            <table>
                <tr><th>Extension</th><th>Count</th><th>Lines</th><th>Size (KB)</th></tr>
    '''
    
    for ext, data in sorted(stats.file_types.items(), key=lambda x: x[1]['count'], reverse=True)[:20]:
        html += f'''
                <tr>
                    <td>.{ext}</td>
                    <td>{data['count']}</td>
                    <td>{data['lines']:,}</td>
                    <td>{data['size'] / 1024:.2f}</td>
                </tr>
        '''
    
    html += '''
            </table>
        </div>
        
        <div class="footer">
            <p>Code Analyzer Pro Ultimate Edition | Cross-Platform</p>
            <p>Created by Otaboyev Sardorbek | 📧 prodevuzoff@gmail.com</p>
        </div>
    </div>
</body>
</html>
'''
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return report_file

# ═══════════════════════════════════════════════════════════════════════════════
# JSON VA CHIQISH FAYLLARINI ASL TARTIBDA SAQLASH FUNKSIYALARI
# ═══════════════════════════════════════════════════════════════════════════════

def save_json_ordered(data: Dict, output_file: str) -> None:
    """
    JSON faylni maxsus sozlamalar bilan saqlash
    - indent=4 (4 ta bo'shliq)
    - ensure_ascii=False (Unicode saqlanadi)
    - sort_keys=False (tartib saqlanadi)
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(
            data,
            f,
            indent=4,           # 4 ta bo'shliq bilan chiroyli format
            ensure_ascii=False, # Unicode belgilarni o'zgartirmaslik
            sort_keys=False,    # Kalitlarni alfavit tartibida saralamaslik
            default=str         # datetime va boshqa maxsus tiplar uchun
        )

def write_output_files_ordered(structure: Dict, output_folder: str) -> List[str]:
    """
    Fayllarni turlar bo'yicha javob fayllariga yozish
    Asl tartibni saqlagan holda (qatorma-qator)
    """
    saved_files = []
    categorized = defaultdict(lambda: defaultdict(dict))
    
    # Fayllarni kengaytmalar bo'yicha guruhlash (asl tartibda)
    for folder, files in structure.items():
        for filename, content in files.items():
            ext = os.path.splitext(filename)[1].lower()
            if ext:
                ext = ext[1:]  # Nuqtani olib tashlash
            else:
                ext = filename.lower()
            categorized[ext][folder][filename] = content
    
    # Har bir kengaytma uchun alohida fayl (asl tartibda)
    for ext, data in categorized.items():
        if data:
            output_file = os.path.join(output_folder, f'respons_{ext}.{ext}')
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"{'='*80}\n")
                    f.write(f"CODE ANALYZER PRO - ULTIMATE EDITION\n")
                    f.write(f"Extension: .{ext}\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"{'='*80}\n\n")
                    
                    # Papkalar va fayllar asl tartibda (qanday bo'lsa shunday)
                    for folder, files in data.items():
                        for filename, content in files.items():
                            rel_path = os.path.join(folder, filename) if folder else filename
                            f.write(f"\n{'─'*80}\n")
                            f.write(f"📄 FILE: {rel_path}\n")
                            f.write(f"{'─'*80}\n\n")
                            f.write(content)
                            f.write("\n\n")
                
                saved_files.append(output_file)
            except Exception as e:
                logging.error(f"Fayl yozishda xato {output_file}: {e}")
    
    # Barcha fayllar - ASL TARTIBDA (qatorma-qator)
    all_files_output = os.path.join(output_folder, 'respons_ALL_FILES.txt')
    try:
        with open(all_files_output, 'w', encoding='utf-8') as f:
            f.write(f"{'═'*80}\n")
            f.write(f"CODE ANALYZER PRO - ULTIMATE EDITION\n")
            f.write(f"ALL FILES - COMPLETE PROJECT ANALYSIS\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Platform: {PLATFORM_INFO['system']}\n")
            f.write(f"{'═'*80}\n\n")
            
            # Papkalar va fayllar ASL TARTIBDA (sorted ishlatilmaydi!)
            for folder, files in structure.items():
                f.write(f"\n{'█'*80}\n")
                f.write(f"📁 FOLDER: {folder if folder else '(ROOT)'}\n")
                f.write(f"{'█'*80}\n\n")
                
                # Fayllar asl tartibda (qanday kelsa shunday)
                for filename, content in files.items():
                    f.write(f"\n{'─'*80}\n")
                    f.write(f"📄 FILE: {filename}\n")
                    f.write(f"{'─'*80}\n\n")
                    f.write(content)
                    f.write("\n\n")
        
        saved_files.append(all_files_output)
    except Exception as e:
        logging.error(f"Barcha fayllarni yozishda xato: {e}")
    
    return saved_files

def build_json_structure_ordered(root_folder: str, structure: Dict, 
                                  stats: AnalysisStats, 
                                  system_stats: SystemStats, 
                                  git_info: Dict,
                                  no_system_stats: bool = False) -> Dict:
    """
    JSON strukturani ASL TARTIBDA qurish
    Fayllar qanday bo'lsa, shunday tartibda saqlanadi
    """
    # Metadata qismi
    ordered_json = {
        'metadata': {
            'generated': datetime.now().isoformat(),
            'root_folder': root_folder,
            'platform': PLATFORM_INFO,
            'system_stats': asdict(system_stats) if not no_system_stats else {},
            'stats': asdict(stats),
            'git_info': git_info
        },
        'structure': {}
    }
    
    # Structure qismini ASL TARTIBDA qo'shish
    # sorted() ishlatilmaydi - qanday kelsa shunday!
    for folder, files in structure.items():
        ordered_json['structure'][folder] = {}
        # Fayllarni ham asl tartibda saqlash
        for filename, content in files.items():
            ordered_json['structure'][folder][filename] = content
    
    return ordered_json

# ═══════════════════════════════════════════════════════════════════════════════
# CLI VA ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════════════════════

def parse_arguments():
    """CLI argumentlarni pars qilish"""
    parser = argparse.ArgumentParser(
        description='Code Analyzer Pro Ultimate - Cross-Platform Code Analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
📌 MISOL:
  python code_analyzer.py
  python code_analyzer.py /path/to/project
  python code_analyzer.py /path/to/project -o ./analysis -v
  python code_analyzer.py /path/to/project --max-size 100 --workers 4

📋 PLATFORMALAR:
  ✅ Windows 7/8/10/11
  ✅ Linux (Ubuntu, Debian, Fedora, Arch, etc)
  ✅ macOS
  ✅ Android (PyDroid3)
        """
    )
    
    parser.add_argument('path', nargs='?', help='Tahlil qilinadigan loyiha papkasi')
    parser.add_argument('-o', '--output', default='CodeAnalyzer_Results', 
                        help='Chiqish papkasi')
    parser.add_argument('--exclude', help='Exclude patternlar (vergul bilan)')
    parser.add_argument('--max-size', type=int, default=50, 
                        help='Maksimal fayl hajmi MB da (default: 50)')
    parser.add_argument('--workers', type=int, default=None, 
                        help='Paralel ishchilar soni')
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help='Batafsil ma\'lumot')
    parser.add_argument('--no-color', action='store_true', 
                        help='Rangli chiqishni o\'chirish')
    parser.add_argument('--no-html', action='store_true', 
                        help='HTML hisobot yaratmaslik')
    parser.add_argument('--no-system-stats', action='store_true',
                        help='Tizim statistikasini ko\'rsatmaslik')
    parser.add_argument('--no-txt', action='store_true',
                        help='TXT fayllarni yaratmaslik')
    parser.add_argument('--no-menu', action='store_true',
                        help='Menyuni ko\'rsatmaslik (to\'g\'ridan-to\'g\'ri yo\'l so\'rash)')
    
    return parser.parse_args()

def main():
    """Asosiy funksiya"""
    args = parse_arguments()
    
    global colored
    if args.no_color:
        def no_color(text, *a, **k): return text
        colored = no_color
    
    print_banner()
    
    # Tizim statistikasini olish va chiqarish
    system_stats = get_system_stats()
    if not args.no_system_stats:
        print_system_stats(system_stats, args.verbose)
    
    # Kutubxonalar holatini ko'rsatish
    print(colored("\n📚 KUTUBXONALAR HOLATI:", 'cyan'))
    for pkg, ver in INSTALLED_DEPS.items():
        print(colored(f"  ✅ {pkg} v{ver}", 'green'))
    if PSUTIL_AVAILABLE:
        print(colored(f"  🔵 psutil (tizim statistikasi)", 'blue'))
    else:
        print(colored(f"  ⚠️  psutil o'rnatilmagan yoki ishlamayapti", 'yellow'))
    
    try:
        root_folder = args.path
        
        # Agar yo'l berilmagan bo'lsa
        if not root_folder:
            if args.no_menu:
                # Menyusiz, to'g'ridan-to'g'ri so'rash
                print(colored("\n📁 Loyiha papkasini kiriting:", 'cyan', attrs=['bold']))
                root_folder = input(colored("➡️  ", 'green')).strip()
            else:
                # Menyu ko'rsatish
                root_folder = show_menu_and_get_path()
                
                if root_folder is None:
                    print(colored("\n❌ Dastur to'xtatildi!", 'red'))
                    sys.exit(0)
        
        if not root_folder:
            print(colored("\n❌ Dastur to'xtatildi!", 'red'))
            sys.exit(0)
        
        root_folder = os.path.abspath(root_folder)
        
        if not os.path.isdir(root_folder):
            print(colored(f"\n❌ '{root_folder}' papkasi mavjud emas!", 'red'))
            sys.exit(1)
        
        output_folder = os.path.join(root_folder, args.output)
        os.makedirs(output_folder, exist_ok=True)
        
        setup_logging(output_folder, args.verbose)
        
        print(colored(f"\n🔍 Tahlil qilinmoqda: {root_folder}", 'cyan', attrs=['bold']))
        print(colored(f"📁 Chiqish papkasi: {output_folder}", 'cyan'))
        
        custom_skip_patterns = []
        if args.exclude:
            custom_skip_patterns = [p.strip() for p in args.exclude.split(',')]
        
        # Git ma'lumotlari
        if not PLATFORM_INFO['is_android']:
            print(colored("\n🔧 Git ma'lumotlari olinmoqda...", 'yellow'))
            git_info = get_git_info(root_folder)
            if git_info.get('is_git_repo'):
                print(colored(f"   ✅ Git repository topildi", 'green'))
                if git_info.get('branch'):
                    print(colored(f"   🌿 Branch: {git_info['branch']}", 'white'))
        else:
            git_info = {'is_git_repo': False}
        
        # Asosiy tahlil
        structure, stats, extensions = analyze_folder(
            root_folder,
            max_workers=args.workers,
            max_size_mb=args.max_size,
            custom_skip_patterns=custom_skip_patterns,
            verbose=args.verbose
        )
        
        if not structure:
            print(colored("\n⚠️  Tahlil qilinadigan fayllar topilmadi!", 'yellow'))
            return
        
        # Statistikani chiqarish
        print(colored("\n📊 TAHLIL NATIJALARI:", 'cyan', attrs=['bold']))
        print(colored("═" * 50, 'white'))
        print(colored(f"  ✅ Qayta ishlangan: {stats.processed_files}", 'green'))
        print(colored(f"  📝 Jami qatorlar: {stats.total_lines:,}", 'green'))
        print(colored(f"  💾 Jami hajm: {stats.total_size / (1024*1024):.2f} MB", 'green'))
        print(colored(f"  ⏱️  Vaqt: {stats.duration_seconds():.2f} sekund", 'green'))
        
        if stats.skipped_files > 0:
            print(colored(f"  ⏭️  Skip qilingan: {stats.skipped_files}", 'yellow'))
        if stats.error_files > 0:
            print(colored(f"  ❌ Xatoliklar: {stats.error_files}", 'red'))
        
        # Topilgan fayl turlari
        if extensions:
            print(colored(f"\n📌 TOPILGAN FAYL TURLARI ({len(extensions)} ta):", 'cyan'))
            top_exts = sorted(stats.file_types.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
            for ext, data in top_exts:
                print(colored(f"  • .{ext} - {data['count']} ta fayl", 'white'))
            if len(extensions) > 10 and not args.verbose:
                print(colored(f"  ... va yana {len(extensions)-10} ta boshqa tur", 'yellow'))
        
        # Natijalarni saqlash
        print(colored("\n💾 Natijalar saqlanmoqda...", 'yellow'))
        
        # ========== JSON - ASL TARTIBDA SAQLASH ==========
        json_file = os.path.join(output_folder, 'project_structure.json')
        
        # JSON strukturani asl tartibda qurish
        ordered_json = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'root_folder': root_folder,
                'platform': PLATFORM_INFO,
                'system_stats': asdict(system_stats) if not args.no_system_stats else {},
                'stats': asdict(stats),
                'git_info': git_info
            },
            'structure': {}
        }
        
        # Structure ni asl tartibda qo'shish (sorted ishlatilmaydi!)
        for folder, files in structure.items():
            ordered_json['structure'][folder] = {}
            for filename, content in files.items():
                ordered_json['structure'][folder][filename] = content
        
        # JSON ni maxsus sozlamalar bilan saqlash
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(
                ordered_json,
                f,
                indent=4,           # 4 ta bo'shliq
                ensure_ascii=False, # Unicode saqlansin
                sort_keys=False,    # Tartib saqlansin
                default=str
            )
        
        print(colored(f"  ✅ JSON: {os.path.basename(json_file)}", 'green'))
        
        # HTML hisobot
        if not args.no_html:
            html_file = generate_html_report(stats, git_info, output_folder, structure, system_stats)
            print(colored(f"  ✅ HTML Hisobot: {os.path.basename(html_file)}", 'green'))
        
        # ========== TXT fayllar - ASL TARTIBDA ==========
        if not args.no_txt:
            print(colored("\n✍️  Javob fayllari yozilmoqda...", 'yellow'))
            saved_files = write_output_files_ordered(structure, output_folder)
            
            print(colored(f"\n📄 YARATILGAN FAYLLAR ({len(saved_files)} ta):", 'green', attrs=['bold']))
            # Fayllarni asl tartibda ko'rsatish (sorted ishlatilmaydi)
            for i, filepath in enumerate(saved_files, 1):
                filename = os.path.basename(filepath)
                size = os.path.getsize(filepath) / 1024
                print(colored(f"  {i}. {filename} ({size:.1f} KB)", 'white'))
        
        # Yakuniy xabar
        print(colored("\n" + "═" * 60, 'white'))
        print(colored("✨ TAHLIL MUVOFFAQIYATLI YAKUNLANDI!", 'green', attrs=['bold']))
        print(colored(f"📂 Natijalar papkada: {output_folder}", 'cyan'))
        
        # Papkani ochish
        if PLATFORM_INFO['is_windows']:
            try:
                os.startfile(output_folder)
                print(colored("📁 Natijalar papkasi avtomatik ochildi!", 'blue'))
            except:
                pass
        elif PLATFORM_INFO['is_mac']:
            try:
                subprocess.run(['open', output_folder])
            except:
                pass
        elif PLATFORM_INFO['is_linux'] and not PLATFORM_INFO['is_android']:
            try:
                subprocess.run(['xdg-open', output_folder])
            except:
                pass
        
    except KeyboardInterrupt:
        print(colored("\n\n⚠️  Dastur foydalanuvchi tomonidan to'xtatildi!", 'yellow'))
    except Exception as e:
        print(colored(f"\n❌ Kutilmagan xato: {e}", 'red'))
        if args.verbose:
            import traceback
            traceback.print_exc()
    finally:
        print(colored("\n👨‍💻 Code Analyzer Pro Ultimate - Cross Platform", 'cyan'))
        print(colored(f"🖥️  Platforma: {PLATFORM_INFO['system'].upper()}", 'blue'))
        print(colored("📧 prodevuzoff@gmail.com | 📱 @otaboyev_sardorbek_blog_dev", 'blue'))
        print()

if __name__ == "__main__":
    main()