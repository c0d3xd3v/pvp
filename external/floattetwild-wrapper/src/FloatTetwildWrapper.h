#ifndef FTETWILDWRAPPER_H
#define FTETWILDWRAPPER_H

#include <functional>
#include <string>
#include <vector>
#include <Eigen/Dense>

#ifdef FLOAT_TETWILD_USE_FLOAT
typedef float Scalar;
#else
typedef double Scalar;
#endif

namespace GEO { class Mesh; }
namespace floatTetWild { class Mesh; class AABBWrapper; }

class FTetWildWrapperImpl; // Pimpl

class FTetWildWrapper {
private:
    FTetWildWrapperImpl* impl;

public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    FTetWildWrapper(double stop_energy = 10.0, double ideal_edge_length_rel = 0.05, double eps_rel = 0.001);
    ~FTetWildWrapper();

    // Progress reporting. During the optimization loop, max_energy carries the
    // current worst tet quality and v_num/t_num the current vertex / tet
    // counts; outside the loop they are NaN / -1.
    using ProgressCallback = std::function<void(const std::string& stage, int it, int total,
                                                double max_energy, int v_num, int t_num)>;

    void loadMeshGeometry(Eigen::MatrixXf &nodes, Eigen::MatrixXi &tris);
    void tetrahedralize();
    void save(const std::string &path);
    void getSurfaceIndices(Eigen::MatrixXi &tris, Eigen::MatrixXi &tets, Eigen::MatrixXf &nodes);
    void setProgressCallback(ProgressCallback cb);
};

#endif // FTETWILDWRAPPER_H
