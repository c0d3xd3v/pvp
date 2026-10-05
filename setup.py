import os
import shutil
import subprocess
import sys
import sysconfig
from setuptools import setup
from setuptools.command.build_ext import build_ext
from setuptools.extension import Extension


class CMakeExtension(Extension):
    def __init__(self, name, cmake_source_dir, build_subdir=None,
                 install_subdir="", git_repo=None, git_dir=None,
                 install_component=None):
        super().__init__(name, sources=[])
        self.cmake_source_dir  = cmake_source_dir  # dir containing CMakeLists.txt (relative to repo root)
        self.build_subdir      = build_subdir or f"{cmake_source_dir}/build"
        self.install_subdir    = install_subdir  # subdir under site-packages ("" = directly there)
        self.git_repo          = git_repo        # if set + git_dir missing → clone before build
        self.git_dir           = git_dir
        self.install_component = install_component  # limit `cmake --install` to this component


class CMakeBuild(build_ext):
    def run(self):
        for ext in self.extensions:
            if ext.git_repo and ext.git_dir and not os.path.exists(ext.git_dir):
                subprocess.check_call(["git", "clone", ext.git_repo, ext.git_dir])
        super().run()

    def build_extension(self, ext):
        repo_root  = os.path.abspath(os.path.dirname(__file__))
        src_dir    = os.path.abspath(os.path.join(repo_root, ext.cmake_source_dir))
        build_dir  = os.path.abspath(os.path.join(repo_root, ext.build_subdir))
        purelib    = sysconfig.get_paths()["purelib"]
        install_prefix = os.path.join(purelib, ext.install_subdir) if ext.install_subdir else purelib

        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))

        cmake_args = [
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
        ]

        os.makedirs(build_dir, exist_ok=True)
        subprocess.check_call(["cmake", src_dir] + cmake_args, cwd=build_dir)
        subprocess.check_call(["cmake", "--build", ".",
                               "-j", str(os.cpu_count() or 1)], cwd=build_dir)
        install_cmd = ["cmake", "--install", "."]
        if ext.install_component:
            install_cmd += ["--component", ext.install_component]
        subprocess.check_call(install_cmd, cwd=build_dir)

        # cmake installs the module (already ABI-tagged, e.g.
        # pyFooBar.cpython-312-x86_64-linux-gnu.so) into install_prefix.
        # Setuptools' editable-install flow expects a copy in extdir, so stage
        # one there for its post-build check.
        ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
        src_so = os.path.join(install_prefix, f"{ext.name}{ext_suffix}")
        dst_so = os.path.join(extdir, f"{ext.name}{ext_suffix}")
        if os.path.exists(src_so) and os.path.abspath(src_so) != os.path.abspath(dst_so):
            os.makedirs(extdir, exist_ok=True)
            shutil.copy2(src_so, dst_so)


setup(
    name="pvp",
    version="0.1",
    author="K4!",
    ext_modules=[
        CMakeExtension(
            "pyFloatTetwildWrapper",
            cmake_source_dir="external/floattetwild-wrapper",
            install_component="pyfloattetwildwrapper",
        ),
    ],
    cmdclass={"build_ext": CMakeBuild},
    zip_safe=False,
)
