cmake_minimum_required(VERSION 3.14)
project(FloatTetwildWrapper)

find_package(Python REQUIRED COMPONENTS Interpreter Development)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

cmake_policy(SET CMP0174 NEW)
cmake_policy(SET CMP0079 NEW)
cmake_policy(SET CMP0169 OLD)

include(FetchContent)

if ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL 13.0)
    # fTetWild bundles older fmt/spdlog that trip newer gcc's stricter warnings.
    # Downgrade the fatal ones to plain warnings so the build survives.
    add_compile_options(
        -Wno-error=changes-meaning
        -Wno-error=array-bounds
        -Wno-error=stringop-overflow
        -Wno-error=restrict
        -Wno-error=dangling-reference
        -Wno-error=maybe-uninitialized
    )
endif()

# --- Eigen & pybind11 via FetchContent (small, common) ---
FetchContent_Declare(
    eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4
    INSTALL_COMMAND "echo \"eigen c++\""
    EXCLUDE_FROM_ALL
)
FetchContent_MakeAvailable(eigen)

FetchContent_Declare(
    pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG v2.13.6
    INSTALL_COMMAND "echo \"pybind11\""
    EXCLUDE_FROM_ALL
)
FetchContent_MakeAvailable(pybind11)

# --- fTetWild via git submodule (../fTetWild) ---
set(FTETWILD_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../fTetWild)
set(FTETWILD_BINARY_DIR ${CMAKE_CURRENT_BINARY_DIR}/fTetWild)
if(NOT EXISTS ${FTETWILD_SOURCE_DIR}/CMakeLists.txt)
    message(FATAL_ERROR
        "fTetWild submodule not initialized. Run: git submodule update --init --recursive")
endif()
# FindGMP.cmake for fTetWild's find_package(GMP) on Windows
list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)
add_subdirectory(${FTETWILD_SOURCE_DIR} ${FTETWILD_BINARY_DIR})
include_directories(${FTETWILD_SOURCE_DIR}/src)

# fTetWild links a `warnings::all` INTERFACE library that appends -Werror plus
# strict warning flags to every compile command, AFTER our own -Wno-error flags —
# so the later -Werror wins. warnings::all is an ALIAS target, so wipe the
# aliased real target's interface options.
if(TARGET warnings::all)
    get_target_property(_warnings_real warnings::all ALIASED_TARGET)
    if(_warnings_real)
        set_target_properties(${_warnings_real} PROPERTIES INTERFACE_COMPILE_OPTIONS "")
    endif()
endif()

# --- Python module: pyFloatTetwildWrapper ---
add_library(py${PROJECT_NAME} MODULE
    src/Utils.cpp
    src/Utils.hpp
    src/FloatTetwildWrapper.h
    src/FloatTetwildWrapper.cpp
    src/bindings.cpp
)

# Python extension naming for this interpreter/platform
# (e.g. .cpython-312-x86_64-linux-gnu.so / .cp312-win_amd64.pyd).
pybind11_extension(py${PROJECT_NAME})

# Find bundled shared libraries (TBB) next to the module on Linux; on Windows
# Python searches the module's own directory for dependent DLLs anyway.
set_target_properties(py${PROJECT_NAME} PROPERTIES
    INSTALL_RPATH "$ORIGIN"
    BUILD_WITH_INSTALL_RPATH ON
)

# pybind11::module links Python the way extension modules should (not against
# libpython on Linux, against pythonXY.lib on Windows).
target_link_libraries(py${PROJECT_NAME}
    PRIVATE
        Eigen3::Eigen
        pybind11::module
        FloatTetwild
)

target_include_directories(py${PROJECT_NAME} PRIVATE ${FTETWILD_BINARY_DIR}/include)

# Install directly under the install prefix so it's importable as
# `import pyFloatTetwildWrapper` when CMAKE_INSTALL_PREFIX points at site-packages.
# Use a dedicated component so we can install only our module without dragging
# in fTetWild's own install rules (geogram etc.) that would need root.
install(TARGETS py${PROJECT_NAME}
        LIBRARY DESTINATION .
        COMPONENT pyfloattetwildwrapper)

# Ship TBB (a shared library) next to the module: either the one fTetWild
# builds itself, or an already installed one it found (imported target).
get_target_property(_tbb_imported tbb::tbb IMPORTED)
get_target_property(_tbb_aliased tbb::tbb ALIASED_TARGET)
if(_tbb_imported)
    install(IMPORTED_RUNTIME_ARTIFACTS tbb::tbb
            LIBRARY DESTINATION . COMPONENT pyfloattetwildwrapper
            RUNTIME DESTINATION . COMPONENT pyfloattetwildwrapper)
elseif(_tbb_aliased)
    get_target_property(_tbb_type ${_tbb_aliased} TYPE)
    if(_tbb_type STREQUAL "SHARED_LIBRARY")
        # COMPONENT applies per artifact kind; NAMELINK_SKIP drops the dev-only libtbb.so
        install(TARGETS ${_tbb_aliased}
                LIBRARY DESTINATION . COMPONENT pyfloattetwildwrapper NAMELINK_SKIP
                RUNTIME DESTINATION . COMPONENT pyfloattetwildwrapper)
    endif()
endif()

# On Windows fTetWild builds geogram as a DLL and links GMP dynamically; those
# DLLs must sit next to the module as well.
if(TARGET geogram)
    get_target_property(_geo_type geogram TYPE)
    if(_geo_type STREQUAL "SHARED_LIBRARY")
        install(TARGETS geogram
                LIBRARY DESTINATION . COMPONENT pyfloattetwildwrapper NAMELINK_SKIP
                RUNTIME DESTINATION . COMPONENT pyfloattetwildwrapper)
    endif()
endif()
if(WIN32 AND GMP_RUNTIME)
    install(FILES ${GMP_RUNTIME} DESTINATION . COMPONENT pyfloattetwildwrapper)
endif()
