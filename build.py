"""
build.py : Build a Windows EPControl agent package

This file is part of EPControl.

Copyright (C) 2016  Jean-Baptiste Galet & Timothe Aeberhardt

EPControl is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

EPControl is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with EPControl.  If not, see <http://www.gnu.org/licenses/>.
"""
import sys
import argparse
import os
import shutil
from io import BytesIO
from pathlib import Path
import urllib.request
import tarfile
from zipfile import ZipFile, ZIP_DEFLATED
import subprocess
import tempfile
import py_compile
import re


AGENTLIB_VERSION = '0.0.0.1'
PYTHON_VERSION = '3.5.2'
PYCRYPTO_VERSION = '2.7a1'
JOB_ID = 'win32'
VERSION = '0.0.1'

CWD = Path(os.path.dirname(os.path.realpath(__file__)))
BUILD_DIR = CWD / 'build'
DIST_DIR = CWD / 'dist'
TMP_DIR = BUILD_DIR / 'tmp'

PYTHONDIR = Path('C:\\DEV\\python')

TKTCL_RE = re.compile(r'^(_?tk|tcl).+\.(pyd|dll)', re.IGNORECASE)
DEBUG_RE = re.compile(r'_d\.(pyd|dll|exe)$', re.IGNORECASE)

EXCLUDE_FROM_LIBRARY = {
    '__pycache__',
    'ensurepip',
    'idlelib',
    'pydoc_data',
    'site-packages',
    'tkinter',
    'turtledemo',
    'venv',
    'pypiwin32_system32'
}
EXCLUDE_FILE_FROM_LIBRARY = {
    'bdist_wininst.py',
}


def is_not_debug(p):
    if DEBUG_RE.search(p.name):
        return False

    if TKTCL_RE.search(p.name):
        return False

    return p.name.lower() not in {
        '_ctypes_test.pyd',
        '_testbuffer.pyd',
        '_testcapi.pyd',
        '_testimportmultiple.pyd',
        '_testmultiphase.pyd',
        'xxlimited.pyd',
    }


def include_in_lib(p):
    name = p.name.lower()
    if p.is_dir():
        if name in EXCLUDE_FROM_LIBRARY:
            return False
        if name.startswith('plat-'):
            return False
        if name.endswith('.dist-info') or name.endswith('.egg-info'):
            return False
        if name == 'test' and p.parts[-2].lower() in ['pytool', 'lib']:
            return False
        if name in {'test', 'tests'} and p.parts[-3].lower() in ['pytool', 'lib']:
            return False
        return True

    if name in EXCLUDE_FILE_FROM_LIBRARY:
        return False

    suffix = p.suffix.lower()
    return suffix not in {'.pyc', '.pyo', '.exe'}


PKG_LAYOUT = [
    ('/', 'src:', 'settings.json', None),
    ('/', 'src:', 'trust.pem', None),
    ('/', 'epc:', 'EPControl.exe', None),
    ('/', 'epc:pytool/Lib/site-packages/pypiwin32_system32', '*.dll', None),
    ('pytool/', 'epc:', 'servicemanager.pyd', None),
    ('pytool/', 'epc:pytool/Lib/site-packages', '**/*', include_in_lib),
    ('/', 'py:PCBuild/$arch', 'python35.dll', is_not_debug),
    ('pylib/', 'py:Lib', '**/*', include_in_lib),
    ('pylib/lib-dynload/', 'py:PCBuild/$arch', '*.pyd', is_not_debug),
    ('pylib/lib-dynload/', 'py:PCBuild/$arch', 'sqlite3.dll', is_not_debug),
]


def copy_to_layout(target, rel_sources):
    count = 0

    if target.suffix.lower() == '.zip':
        if target.exists():
            target.unlink()

        with ZipFile(str(target), 'w', ZIP_DEFLATED) as f:
            with tempfile.TemporaryDirectory() as tmpdir:
                for s, rel in rel_sources:
                    if rel.suffix.lower() == '.py':
                        pyc = Path(tmpdir) / rel.with_suffix('.pyc').name
                        try:
                            py_compile.compile(str(s), str(pyc), str(rel), doraise=True, optimize=2)
                        except py_compile.PyCompileError:
                            f.write(str(s), str(rel))
                        else:
                            f.write(str(pyc), str(rel.with_suffix('.pyc')))
                    else:
                        f.write(str(s), str(rel))
                    count += 1

    else:
        for s, rel in rel_sources:
            dest = target / rel
            try:
                dest.parent.mkdir(parents=True)
            except FileExistsError:
                pass

            if rel.suffix.lower() == '.py':
                pyc = Path(target) / rel.with_suffix('.pyc')
                try:
                    py_compile.compile(str(s), str(pyc), str(rel), doraise=True, optimize=2)
                except py_compile.PyCompileError:
                    shutil.copy(str(s), str(dest))
            else:
                shutil.copy(str(s), str(dest))
            count += 1

    return count


def rglob(root, pattern, condition):
    dirs = [root]
    recurse = pattern[:3] in {'**/', '**\\'}
    while dirs:
        d = dirs.pop(0)
        for f in d.glob(pattern[3:] if recurse else pattern):
            if recurse and f.is_dir() and (not condition or condition(f)):
                dirs.append(f)
            elif f.is_file() and (not condition or condition(f)):
                yield f, f.relative_to(root)


def run_cmd(args):
    """Run a command"""
    with subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1) as proc:
        stdout, stderr = proc.communicate()
        print(stdout)
        return proc.returncode == 0


class WinPkgBuilder(object):
    def __init__(self, arch):
        self.arch = arch
        self.pyarch = 'win32' if arch == 'x86' else 'amd64'

        global TMP_DIR
        TMP_DIR /= self.arch

        os.makedirs(str(BUILD_DIR), exist_ok=True)
        os.makedirs(str(TMP_DIR), exist_ok=True)
        os.makedirs(str(DIST_DIR / self.arch), exist_ok=True)

        global PYTHONDIR
        PYTHONDIR /= 'Python-{}-{}'.format(PYTHON_VERSION, self.arch)
        os.makedirs(str(PYTHONDIR), exist_ok=True)

    def build_python(self):
        """Build python"""
        print("Building Python {} for {}".format(PYTHON_VERSION, self.arch))
        os.chdir(str(PYTHONDIR))

        # Download Python
        with urllib.request.urlopen(
                'https://www.python.org/ftp/python/{0}/Python-{0}.tar.xz'.format(PYTHON_VERSION)) as conn:
            data = BytesIO(conn.read())

        # Extract
        tar = tarfile.open(mode='r:xz', fileobj=data)
        tar.extractall()

        # Build
        os.chdir(str(PYTHONDIR / "Python-{}".format(PYTHON_VERSION) / 'PCbuild'))
        if not run_cmd([
            'build.bat',
            '-c', 'Release',
            '-p', 'Win32' if self.arch == 'x86' else 'x64',
            '-e'
        ]):
            raise RuntimeError("Cannot build python")

        os.chdir(str(PYTHONDIR / "Python-{}".format(PYTHON_VERSION)))
        # Install pip
        if not run_cmd([
            'python.bat',
            '-m',
            'ensurepip'
        ]):
            raise RuntimeError("Cannot install pip")

    def build_requirements(self):
        """Build the python requirements"""
        print("Build requirements")
        os.chdir(str(BUILD_DIR))

        # Create venv
        if not run_cmd([
            str(PYTHONDIR / "Python-{}".format(PYTHON_VERSION) / 'python.bat'),
            '-m', 'venv',
            '--copies',
            '--clear',
            str(TMP_DIR / 'pytool')
        ]):
            raise RuntimeError("Cannot create venv")
        venv_py = str(TMP_DIR / 'pytool' / 'Scripts' / 'python.exe')

        # Download and build pycrypto
        with urllib.request.urlopen(
                "https://github.com/dlitz/pycrypto/archive/v{}.zip".format(PYCRYPTO_VERSION)) as conn:
            with open(str(BUILD_DIR / 'pycrypto-{}.zip'.format(PYCRYPTO_VERSION)), 'wb') as ofile:
                ofile.write(conn.read())
        with ZipFile(str(BUILD_DIR / 'pycrypto-{}.zip'.format(PYCRYPTO_VERSION)), 'r') as zfile:
            zfile.extractall(str(BUILD_DIR))
            if not run_cmd([
                venv_py,
                '-m', 'pip',
                'install',
                str(BUILD_DIR / 'pycrypto-{}'.format(PYCRYPTO_VERSION)),
            ]):
                raise RuntimeError("Cannot install pycrypto")

        os.chdir(str(BUILD_DIR))
        # Download agentlib wheel
        with urllib.request.urlopen(
            "https://github.com/PokeSec/agentlib/releases/download/{0}/agentlib-{0}-py3-none-win32.whl".format(AGENTLIB_VERSION)) as conn:
            with open(str(BUILD_DIR / 'agentlib-{}-py3-none-win32.whl'.format(AGENTLIB_VERSION)), 'wb') as ofile:
                ofile.write(conn.read())

                # Install agentlib wheel
                if not run_cmd([
                    venv_py,
                    '-m', 'pip',
                    'install',
                    str(BUILD_DIR / 'agentlib-{}-py3-none-win32.whl'.format(AGENTLIB_VERSION)),
                ]):
                    raise RuntimeError("Cannot install agentlib")

    def build_epcontrol(self):
        """Build the executable"""
        os.chdir(str(CWD))

        print("Build EPControl")
        if not run_cmd([
            'msbuild',
            '/p:Configuration=Release',
            '/p:Platform={}'.format(self.arch),
            '/p:PYTHON_PATH={}'.format(str(PYTHONDIR / "Python-{}".format(PYTHON_VERSION))),
            '/p:EXTRA_LIBS={}'.format(str(TMP_DIR / 'pytool' / 'Lib' / 'site-packages' / 'win32' / 'libs')),
            '/p:OutDir={}'.format(str(TMP_DIR)),
            str(CWD / 'EPControl.sln')
        ]):
            raise RuntimeError("Cannot build EPControl")

    def prepare_package(self):
        """Prepare the dist directory"""
        os.chdir(str(DIST_DIR / self.arch))
        os.makedirs(str(DIST_DIR / self.arch / 'logs'), exist_ok=True)
        for t, s, p, c in PKG_LAYOUT:
            tmp = s.split(':')
            if tmp[0] == 'epc':
                s = TMP_DIR / tmp[1].replace("$arch", self.arch)
            elif tmp[0] == 'py':
                s = PYTHONDIR / "Python-{}".format(PYTHON_VERSION) / tmp[1].replace("$arch", self.pyarch)
            elif tmp[0] == 'src':
                s = CWD / tmp[1].replace("$arch", self.arch)
            else:
                continue
            copied = copy_to_layout(DIST_DIR / self.arch / t.rstrip('/'), rglob(s, p, c))
            print('Copied {} files'.format(copied))

    def assemble_package(self):
        """Create the final format"""
        os.chdir(str(DIST_DIR))

        # Create the MSI file list with WIX
        if not run_cmd([
            r'C:\Program Files (x86)\WiX Toolset v3.10\bin\heat.exe',
            'dir', str(DIST_DIR / self.arch),
            '-nologo',
            '-gg',
            '-sfrag',
            '-cg', 'EPControlComponent',
            '-t', str(CWD / 'setup' / 'msisetup' / 'service.xslt'),
            '-template', 'fragment',
            '-srd',
            '-var', 'var.builddir',
            '-dr', 'INSTALLFOLDER',
            '-out', str(CWD / 'setup' / 'msisetup' / 'epcontrolcomponent.wxs')
        ]):
            raise RuntimeError("Cannot prepare msi (heat)")

        # Compile the MSI
        if not run_cmd([
            'msbuild',
            '/p:Configuration=Release',
            '/p:Platform={}'.format(self.arch),
            '/p:BUILDDIR={}'.format(str(DIST_DIR / self.arch)),
            '/p:VERSION={}'.format(str(VERSION)),
            '/p:OUTNAME=EPControl-{}-{}'.format(VERSION, self.arch),
            '/p:OutDir={}/'.format(str(DIST_DIR)),
            str(CWD / 'setup' / 'msisetup' / 'msisetup.sln')
        ]):
            raise RuntimeError("Cannot build msi")

    def symlink_agentlib(self, agentlib):
        os.chdir(str(DIST_DIR / self.arch))
        shutil.rmtree('pytool/epc', True)
        print('{}\\epc'.format(agentlib))
        if not run_cmd([
            'cmd', '/c', 'mklink',
            '/D',
            'pytool\\epc',
            '{}\\epc'.format(agentlib)
        ]):
            raise RuntimeError("Cannot create link")


def main():
    """Entry Point"""
    parser = argparse.ArgumentParser(description="Build a Windows EPControl agent package")
    parser.add_argument('arch', choices=['x86', 'x64'], help="The arch for which to build the package")
    parser.add_argument('--nomsi', action='store_true')
    parser.add_argument('--nobuild', action='store_true')
    parser.add_argument('--skippython', action='store_true')
    parser.add_argument('--agentlib', help='Path to agentlib (dev only)')
    args = parser.parse_args()

    try:
        pkg_builder = WinPkgBuilder(args.arch)

        if not args.nobuild:
            if not args.skippython:
                pkg_builder.build_python()
            pkg_builder.build_requirements()
            pkg_builder.build_epcontrol()

        pkg_builder.prepare_package()
        if not args.nomsi:
            pkg_builder.assemble_package()

        if args.agentlib:
            pkg_builder.symlink_agentlib(args.agentlib)
    except RuntimeError as exc:
        sys.exit("BUILD ERROR : {}".format(exc))

if __name__ == '__main__':
    main()
