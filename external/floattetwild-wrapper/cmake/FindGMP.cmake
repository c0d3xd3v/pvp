# Minimal FindGMP for fTetWild's `find_package(GMP REQUIRED)` (only used on
# Windows). Looks in GMP_ROOT (e.g. a vcpkg installed/x64-windows dir) and the
# GMP_INC / GMP_LIB environment variables fTetWild documents.
# Sets GMP_FOUND, GMP_INCLUDE_DIRS, GMP_LIBRARIES and GMP_RUNTIME (the DLL).
find_path(GMP_INCLUDE_DIRS NAMES gmp.h
          HINTS ${GMP_ROOT}/include $ENV{GMP_INC})
find_library(GMP_LIBRARIES NAMES gmp libgmp mpir
             HINTS ${GMP_ROOT}/lib $ENV{GMP_LIB})
find_file(GMP_RUNTIME NAMES gmp-10.dll libgmp-10.dll gmp.dll
          HINTS ${GMP_ROOT}/bin $ENV{GMP_LIB} $ENV{GMP_LIB}/../bin)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(GMP DEFAULT_MSG GMP_INCLUDE_DIRS GMP_LIBRARIES)
set(GMP_INCLUDE_DIR ${GMP_INCLUDE_DIRS})
mark_as_advanced(GMP_INCLUDE_DIRS GMP_LIBRARIES GMP_RUNTIME)
