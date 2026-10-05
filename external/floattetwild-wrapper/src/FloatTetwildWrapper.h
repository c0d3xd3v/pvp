#ifndef FTETWILDWRAPPER_H
#define FTETWILDWRAPPER_H

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

    void loadMeshGeometry(Eigen::MatrixXf &nodes, Eigen::MatrixXi &tris);
    void tetrahedralize();
    void save(const std::string &path);
    void getSurfaceIndices(Eigen::MatrixXi &tris, Eigen::MatrixXi &tets, Eigen::MatrixXf &nodes);
};

#endif // FTETWILDWRAPPER_H
