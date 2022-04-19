from conans import ConanFile, tools
from conans.errors import ConanInvalidConfiguration
import os
import re
import shutil

required_conan_version = ">=1.33.0"


class AndroidNDKLocalConan(ConanFile):
    name = "android-ndk-local"
    description = "The Android NDK is a toolset that lets you implement parts of your app in native code, using languages such as C and C++"
    url = "https://developer.android.com/ndk/"
    homepage = "https://developer.android.com/ndk/"
    topics = ("android", "NDK", "toolchain", "compiler")
    license = "Apache-2.0"
    version = "1.0.0_rc1"
    
    settings = "os", "arch"
    
    short_paths = True
    exports_sources = "cmake-wrapper.cmd", "cmake-wrapper"

    @property
    def _ndk_version(self):
        if not os.getenv("ANDROID_NDK_HOME"):
            raise ConanInvalidConfiguration("envriroment 'ANDROID_NDK_HOME' not exist")

        with open(os.path.join(os.environ['ANDROID_NDK_HOME'], "source.properties")) as properties:
             for line in properties:
                self.output.info(f"line: {line}")
                match = re.search(r"Pkg\.Revision = (\d+)\.(\d+)\.(\d+)", line)
                if match:
                    major, minor, _ = match.groups()
                    assert major
                    return int(major), int(minor)
        raise ConanInvalidConfiguration(f"INVALID 'ANDROID_NDK_HOME:{os.environ['ANDROID_NDK_HOME']}' not exist")
    @property
    def _is_universal2(self):
        return self._ndk_version_major in [23, 24] and self.settings.os == "Macos" and self.settings.arch in ["x86_64", "armv8"]

    @property
    def _arch(self):
        return "x86_64" if self._is_universal2 else self.settings.arch

    def _settings_os_supported(self):
        return True

    def _settings_arch_supported(self):
        return True

    def validate(self):
        if not os.getenv("ANDROID_NDK_HOME"):
            raise ConanInvalidConfiguration("envriroment 'ANDROID_NDK_HOME' not exist")
        if not self._settings_os_supported():
            raise ConanInvalidConfiguration(f"os={self.settings.os} is not supported by {self.name} (no binaries are available)")
        if not self._settings_arch_supported():
            raise ConanInvalidConfiguration(f"os,arch={self.settings.os},{self.settings.arch} is not supported by {self.name} (no binaries are available)")

    def build(self):
        pass

    def package_id(self):
        if self._is_universal2:
            self.info.settings.arch = "universal:armv8/x86_64"

    def package(self):
        self.copy("cmake-wrapper.cmd")
        self.copy("cmake-wrapper")

    # from here on, everything is assumed to run in 2 profile mode, using this android-ndk recipe as a build requirement

    @property
    def _platform(self):
        return {
            "Linux": "linux",
            "Macos": "darwin",
            "Windows": "windows",
        }.get(str(self.settings_build.os))

    @property
    def _android_abi(self):
        return {
            "armv7": "armeabi-v7a",
            "armv8": "arm64-v8a",
            "x86": "x86",
            "x86_64": "x86_64",
        }.get(str(self.settings_target.arch))

    @property
    def _llvm_triplet(self):
        arch = {
            "armv7": "arm",
            "armv8": "aarch64",
            "x86": "i686",
            "x86_64": "x86_64",
        }.get(str(self.settings_target.arch))
        abi = "androideabi" if self.settings_target.arch == "armv7" else "android"
        return f"{arch}-linux-{abi}"

    @property
    def _clang_triplet(self):
        arch = {
            "armv7": "armv7a",
            "armv8": "aarch64",
            "x86": "i686",
            "x86_64": "x86_64",
        }.get(str(self.settings_target.arch))
        abi = "androideabi" if self.settings_target.arch == "armv7" else "android"
        return f"{arch}-linux-{abi}"

    @property
    def _ndk_major_minor(self):
        return self._ndk_version

    @property
    def _ndk_version_major(self):
        return self._ndk_major_minor[0]

    @property
    def _host(self):
        return f"{self._platform}-{self.settings.arch}"

    @property
    def _ndk_root(self):
        return os.path.join(os.environ['ANDROID_NDK_HOME'], "toolchains", "llvm", "prebuilt", self._host)

    def _wrap_executable(self, tool):
        suffix = ".exe" if self.settings_build.os == "Windows" else ""
        return f"{tool}{suffix}"

    def _tool_name(self, tool, bare=False):
        prefix = ""
        if "clang" in tool:
            suffix = ".cmd" if self.settings_build.os == "Windows" else ""
            prefix = "llvm" if bare else f"{self._clang_triplet}{self.settings_target.os.api_level}"
            return f"{prefix}-{tool}{suffix}"
        else:
            prefix = "llvm" if bare else f"{self._llvm_triplet}"
            executable = f"{prefix}-{tool}"
            return self._wrap_executable(executable)

    @property
    def _cmake_system_processor(self):
        cmake_system_processor = {
            "x86_64": "x86_64",
            "x86": "i686",
            "mips": "mips",
            "mips64": "mips64",
        }.get(str(self.settings.arch))
        if self.settings_target.arch == "armv8":
            cmake_system_processor = "aarch64"
        elif "armv7" in str(self.settings.arch):
            cmake_system_processor = "armv7-a"
        elif "armv6" in str(self.settings.arch):
            cmake_system_processor = "armv6"
        elif "armv5" in str(self.settings.arch):
            cmake_system_processor = "armv5te"
        return cmake_system_processor

    def _define_tool_var(self, name, value, bare = False):
        ndk_bin = os.path.join(self._ndk_root, "bin")
        path = os.path.join(ndk_bin, self._tool_name(value, bare))
        if not os.path.isfile(path):
            self.output.error(f"'Environment variable {name} could not be created: '{path}'")
            return "UNKNOWN"
        self.output.info(f"Creating {name} environment variable: {path}")
        return path

    def _define_tool_var_naked(self, name, value):
        ndk_bin = os.path.join(self._ndk_root, "bin")
        path = os.path.join(ndk_bin, self._wrap_executable(value))
        if not os.path.isfile(path):
            self.output.error(f"'Environment variable {name} could not be created: '{path}'")
            return "UNKNOWN"
        self.output.info(f"Creating {name} environment variable: {path}")
        return path

    @staticmethod
    def _chmod_plus_x(filename):
        if os.name == "posix":
            os.chmod(filename, os.stat(filename).st_mode | 0o111)

    def package_info(self):
        # test shall pass, so this runs also in the build as build requirement context
        # ndk-build: https://developer.android.com/ndk/guides/ndk-build
        self.env_info.PATH.append(self.package_folder)
        self.env_info.PATH.append(os.environ['ANDROID_NDK_HOME'])

        # You should use the ANDROID_NDK_ROOT environment variable to indicate where the NDK is located.
        # That's what most NDK-related scripts use (inside the NDK, and outside of it).
        # https://groups.google.com/g/android-ndk/c/qZjhOaynHXc
        self.output.info(f"Creating ANDROID_NDK_ROOT environment variable: {os.environ['ANDROID_NDK_HOME']}")
        self.env_info.ANDROID_NDK_ROOT = os.environ['ANDROID_NDK_HOME']

        self.output.info(f"Creating ANDROID_NDK_HOME environment variable: {os.environ['ANDROID_NDK_HOME']}")
        self.env_info.ANDROID_NDK_HOME = os.environ['ANDROID_NDK_HOME']

        #  this is not enough, I can kill that .....
        if not hasattr(self, "settings_target"):
            return

        # interestingly I can reach that with
        # conan test --profile:build nsdk-default --profile:host default /Users/a4z/elux/conan/myrecipes/android-ndk/all/test_package android-ndk/r21d@
        if self.settings_target is None:
            return

        # And if we are not building for Android, why bother at all
        if not self.settings_target.os == "Android":
            self.output.warn(f"You've added {self.name}/{self.version} as a build requirement, while os={self.settings_target.os} != Android")
            return

        cmake_system_processor = self._cmake_system_processor
        if cmake_system_processor:
            self.output.info(f"Creating CONAN_CMAKE_SYSTEM_PROCESSOR environment variable: {cmake_system_processor}")
            self.env_info.CONAN_CMAKE_SYSTEM_PROCESSOR = cmake_system_processor
        else:
            self.output.warn("Could not find a valid CMAKE_SYSTEM_PROCESSOR variable, supported by CMake")

        self.output.info(f"Creating NDK_ROOT environment variable: {self._ndk_root}")
        self.env_info.NDK_ROOT = self._ndk_root

        self.output.info(f"Creating CHOST environment variable: {self._llvm_triplet}")
        self.env_info.CHOST = self._llvm_triplet

        ndk_sysroot = os.path.join(self._ndk_root, "sysroot")
        self.output.info(f"Creating CONAN_CMAKE_FIND_ROOT_PATH environment variable: {ndk_sysroot}")
        self.env_info.CONAN_CMAKE_FIND_ROOT_PATH = ndk_sysroot

        self.output.info(f"Creating SYSROOT environment variable: {ndk_sysroot}")
        self.env_info.SYSROOT = ndk_sysroot

        self.output.info(f"Creating self.cpp_info.sysroot: {ndk_sysroot}")
        self.cpp_info.sysroot = ndk_sysroot

        self.output.info(f"Creating ANDROID_NATIVE_API_LEVEL environment variable: {self.settings_target.os.api_level}")
        self.env_info.ANDROID_NATIVE_API_LEVEL = str(self.settings_target.os.api_level)

        self._chmod_plus_x(os.path.join(self.package_folder, "cmake-wrapper"))
        cmake_wrapper = "cmake-wrapper.cmd" if self.settings.os == "Windows" else "cmake-wrapper"
        cmake_wrapper = os.path.join(self.package_folder, cmake_wrapper)
        self.output.info(f"Creating CONAN_CMAKE_PROGRAM environment variable: {cmake_wrapper}")
        self.env_info.CONAN_CMAKE_PROGRAM = cmake_wrapper

        toolchain = os.path.join(os.environ['ANDROID_NDK_HOME'], "build", "cmake", "android.toolchain.cmake")
        self.output.info(f"Creating CONAN_CMAKE_TOOLCHAIN_FILE environment variable: {toolchain}")
        self.env_info.CONAN_CMAKE_TOOLCHAIN_FILE = toolchain

        self.env_info.CC = self._define_tool_var("CC", "clang")
        self.env_info.CXX = self._define_tool_var("CXX", "clang++")
        if self._ndk_version_major >= 23:
            # Versions greater than 23 had the naming convention
            # changed to no longer include the triplet.
            self.env_info.AR = self._define_tool_var("AR", "ar", True)
            self.env_info.AS = self._define_tool_var("AS", "as", True)
            self.env_info.RANLIB = self._define_tool_var("RANLIB", "ranlib", True)
            self.env_info.STRIP = self._define_tool_var("STRIP", "strip", True)
            self.env_info.ADDR2LINE = self._define_tool_var("ADDR2LINE", "addr2line", True)
            self.env_info.NM = self._define_tool_var("NM", "nm", True)
            self.env_info.OBJCOPY = self._define_tool_var("OBJCOPY", "objcopy", True)
            self.env_info.OBJDUMP = self._define_tool_var("OBJDUMP", "objdump", True)
            self.env_info.READELF = self._define_tool_var("READELF", "readelf", True)
            # there doesn't seem to be an 'elfedit' included anymore.
        else:
            self.env_info.AR = self._define_tool_var("AR", "ar")
            self.env_info.AS = self._define_tool_var("AS", "as")
            self.env_info.RANLIB = self._define_tool_var("RANLIB", "ranlib")
            self.env_info.STRIP = self._define_tool_var("STRIP", "strip")
            self.env_info.ADDR2LINE = self._define_tool_var("ADDR2LINE", "addr2line")
            self.env_info.NM = self._define_tool_var("NM", "nm")
            self.env_info.OBJCOPY = self._define_tool_var("OBJCOPY", "objcopy")
            self.env_info.OBJDUMP = self._define_tool_var("OBJDUMP", "objdump")
            self.env_info.READELF = self._define_tool_var("READELF", "readelf")
            self.env_info.ELFEDIT = self._define_tool_var("ELFEDIT", "elfedit")
        
        # The `ld` tool changed naming conventions earlier than others
        if self._ndk_version_major >= 22:
            self.env_info.LD = self._define_tool_var_naked("LD", "ld")
        else:
            self.env_info.LD = self._define_tool_var("LD", "ld")

        self.env_info.ANDROID_PLATFORM = f"android-{self.settings_target.os.api_level}"
        self.env_info.ANDROID_TOOLCHAIN = "clang"
        self.env_info.ANDROID_ABI = self._android_abi
        libcxx_str = str(self.settings_target.compiler.libcxx)
        self.env_info.ANDROID_STL = libcxx_str if libcxx_str.startswith("c++_") else "c++_shared"

        self.env_info.CMAKE_FIND_ROOT_PATH_MODE_PROGRAM = "BOTH"
        self.env_info.CMAKE_FIND_ROOT_PATH_MODE_LIBRARY = "BOTH"
        self.env_info.CMAKE_FIND_ROOT_PATH_MODE_INCLUDE = "BOTH"
        self.env_info.CMAKE_FIND_ROOT_PATH_MODE_PACKAGE = "BOTH"
