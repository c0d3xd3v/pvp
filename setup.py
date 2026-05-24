import os
import subprocess
import sys
from setuptools import setup
from setuptools.command.build_ext import build_ext
from setuptools.extension import Extension
import sysconfig


# Dein Git-Repository mit dem C++-Code
GIT_REPO = "https://gitlab.com/c0d3xd3v/manifold-harmonic-neural-operator.git"
GIT_DIR = "mhno"

class CMakeBuild(build_ext):
    def run(self):        
        # Klone das Repository, falls es nicht existiert
        if not os.path.exists(GIT_DIR):
            subprocess.check_call(["git", "clone", GIT_REPO, GIT_DIR])
        super().run()

    def build_extension(self, ext):
        build_temp = GIT_DIR + "/build" # self.build_temp
        sourcedir = os.path.abspath(os.path.dirname(__file__))
        
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))

        install_dir = sysconfig.get_paths()["purelib"]
        print(f"Standard-Installationspfad: {install_dir}")

        cmake_args = [
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            f"-DCMAKE_INSTALL_PREFIX={install_dir+"/"+GIT_DIR}"
        ]

        os.makedirs(build_temp, exist_ok=True)

        # CMake ausführen
        subprocess.check_call(["cmake", sourcedir + "/" + GIT_DIR + "/src/point_cloud_tools/" ] + cmake_args, cwd=build_temp)
        subprocess.check_call(["cmake", "--build", ".", "--target", "install" ], cwd=build_temp)

setup(
    name="mhno",
    version="0.1",
    author="K4!",
    ext_modules=[Extension("mhno", [])],  # Keine direkte C++-Datei, CMake baut es
    cmdclass={"build_ext": CMakeBuild},
    zip_safe=False,
)
