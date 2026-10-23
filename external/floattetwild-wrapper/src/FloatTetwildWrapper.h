#ifndef FTETWILDWRAPPER_H
#define FTETWILDWRAPPER_H

#include <functional>
#include <stdexcept>
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

    // Thrown out of tetrahedralize() when a cancel request is seen at the
    // next progress tick. fTetWild / TBB stacks are not exception-safe, so
    // some internal buffers may leak — acceptable for user-triggered abort,
    // and still vastly better than killing the thread mid-work.
    class Cancelled : public std::runtime_error {
    public:
        Cancelled() : std::runtime_error("fTetWild cancelled") {}
    };

    void loadMeshGeometry(Eigen::MatrixXf &nodes, Eigen::MatrixXi &tris);
    void tetrahedralize();
    void save(const std::string &path);
    void getSurfaceIndices(Eigen::MatrixXi &tris, Eigen::MatrixXi &tets, Eigen::MatrixXf &nodes);
    void setProgressCallback(ProgressCallback cb);
    // Thread-safe. Causes the next emit_progress inside tetrahedralize() to
    // throw Cancelled; harmless if nothing is running.
    void requestCancel();
};

#endif // FTETWILDWRAPPER_H
