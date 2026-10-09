#include "Utils.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/pybind11.h>
#include <pybind11/eigen.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>
#include <pybind11/iostream.h>

namespace py = pybind11;

#include "FloatTetwildWrapper.h"

PYBIND11_MODULE(pyFloatTetwildWrapper, m)
{
    py::class_<FTetWildWrapper>(m, "FTetWildWrapper")
            .def(py::init<
                     double, double, double>(),
                     py::arg("stop_energy") = 10,
                     py::arg("ideal_edge_length_rel") = 0.05,
                     py::arg("eps_rel") = 0.001
                )
            .def(
                "loadMeshGeometry", [](FTetWildWrapper &t, Eigen::MatrixXf &V, Eigen::MatrixXi &F)
                {
                    t.loadMeshGeometry(V, F);
                },
                "set mesh",  py::arg("V"), py::arg("F"),
                py::call_guard<py::gil_scoped_release>())
            .def(
                "tetrahedralize", [](FTetWildWrapper &t)
                {
                    t.tetrahedralize();
                },
                "create tet mesh",
                py::call_guard<py::gil_scoped_release>())
            .def(
                "getSurfaceIndices", [](FTetWildWrapper &t)
                {
                    Eigen::MatrixXf nodes;
                    Eigen::MatrixXi tris;
                    Eigen::MatrixXi tets;
                    {
                        py::gil_scoped_release release;
                        t.getSurfaceIndices(tris, tets, nodes);
                    }
                    return py::make_tuple(tris, tets, nodes);
                },
                "get mesh")
                .def(
                    "save", [](FTetWildWrapper &t, const std::string &path)
                    {
                        t.save(path);
                    },
                    "save mesh", py::arg("path"),
                    py::call_guard<py::gil_scoped_release>())
                .def(
                    "setProgressCallback", [](FTetWildWrapper &t, py::object cb)
                    {
                        if (cb.is_none()) {
                            t.setProgressCallback(nullptr);
                            return;
                        }
                        // shared_ptr so the Python callable survives until
                        // the C++ std::function is destroyed; its destructor
                        // runs under the GIL via py::gil_scoped_acquire below.
                        auto holder = std::shared_ptr<py::object>(
                            new py::object(cb),
                            [](py::object* p) {
                                py::gil_scoped_acquire gil;
                                delete p;
                            });
                        t.setProgressCallback(
                            [holder](const std::string& stage, int it, int total)
                            {
                                // Called from a TBB worker without GIL.
                                py::gil_scoped_acquire gil;
                                try {
                                    (*holder)(stage, it, total);
                                } catch (const py::error_already_set&) {
                                    PyErr_Clear();
                                }
                            });
                    },
                    "progress callback fn(stage: str, it: int, total: int)",
                    py::arg("callback"))
            ;
}
