#include "FloatTetwildWrapper.h"

#include <tbb/global_control.h>
#include <thread>
#include <memory>
#include <iostream>
#include <numeric>

#include <floattetwild/AABBWrapper.h>
#include <floattetwild/FloatTetDelaunay.h>
#include <floattetwild/LocalOperations.h>
#include <floattetwild/MeshImprovement.h>
#include <floattetwild/Simplification.h>
#include <floattetwild/Statistics.h>
#include <floattetwild/TriangleInsertion.h>
#include <floattetwild/CSGTreeParser.hpp>
#include <floattetwild/Mesh.hpp>
#include <floattetwild/MeshIO.hpp>
#include <floattetwild/Logger.hpp>
#include <floattetwild/MshLoader.h>
#include <floattetwild/Predicates.hpp>

#include <igl/remove_unreferenced.h>
#include <igl/write_triangle_mesh.h>

#include <geogram/basic/command_line.h>
#include <geogram/basic/command_line_args.h>
#include <geogram/basic/common.h>
#include <geogram/mesh/mesh.h>


void get_boundary_surface_indices(floatTetWild::Mesh& mesh, Eigen::MatrixXi& F) {
    using namespace floatTetWild;

    auto &tets = mesh.tets;
    auto &tet_vertices = mesh.tet_vertices;

    std::vector<std::array<int, 5>> faces;
    for (int i=0;i<tets.size();i++) {
        auto &t = tets[i];
        if (t.is_removed)
            continue;
        for (int j = 0; j < 4; j++) {
            std::array<int, 3> f = {{t[(j + 1) % 4], t[(j + 2) % 4], t[(j + 3) % 4]}};
            std::sort(f.begin(), f.end());
            faces.push_back({{f[0], f[1], f[2], i, j}});
        }
    }
    std::sort(faces.begin(), faces.end(), [](const std::array<int, 5>& a, const std::array<int, 5>& b){
        return std::make_tuple(a[0], a[1], a[2]) < std::make_tuple(b[0], b[1], b[2]);
    });
    if (faces.empty())
        return;
    //
    std::vector<std::array<int, 3>> b_faces;
    bool is_boundary = true;
    for (int i = 0; i < faces.size() - 1; i++) {
        if (std::make_tuple(faces[i][0], faces[i][1], faces[i][2])
            == std::make_tuple(faces[i + 1][0], faces[i + 1][1], faces[i + 1][2])) {
            is_boundary = false;
            } else {
                if (is_boundary) {
                    b_faces.push_back({{faces[i][0], faces[i][1], faces[i][2]}});
                    bool is_inv = is_inverted(tet_vertices[tets[faces[i][3]][faces[i][4]]],
                                              tet_vertices[faces[i][0]],
                                              tet_vertices[faces[i][1]],
                                              tet_vertices[faces[i][2]]);
                    if (!is_inv)
                        std::swap(b_faces.back()[1], b_faces.back()[2]);
                }
                is_boundary = true;
            }
    }
    if (is_boundary) {
        b_faces.push_back({{faces.back()[0], faces.back()[1], faces.back()[2]}});
        bool is_inv = is_inverted(tet_vertices[tets[faces.back()[3]][faces.back()[4]]],
                                  tet_vertices[faces.back()[0]],
                                  tet_vertices[faces.back()[1]],
                                  tet_vertices[faces.back()[2]]);
        if(!is_inv)
            std::swap(b_faces.back()[1], b_faces.back()[2]);
    }

    std::vector<int> b_v_ids;
    for (int i = 0; i < b_faces.size(); i++) {
        for (int j = 0; j < 3; j++) {
            b_v_ids.push_back(b_faces[i][j]);
        }
    }
    vector_unique(b_v_ids);

    //V.resize(b_v_ids.size(), 3);
    F.resize(b_faces.size(), 3);
    /*
     *   std::map<int, int> map_v_ids;
     *   for (int i = 0; i < b_v_ids.size(); i++) {
     *       map_v_ids[b_v_ids[i]] = i;
     *       V.row(i) = tet_vertices[b_v_ids[i]].pos;
}
*/
    for (int i = 0; i < b_faces.size(); i++) {
        F.row(i) << b_faces[i][0], b_faces[i][1], b_faces[i][2];
    }
}

class FTetWildWrapperImpl {
public:
    GEO::Mesh* input_mesh = nullptr;
    floatTetWild::Mesh* mesh = nullptr;
    floatTetWild::AABBWrapper* tree = nullptr;
    std::vector<Eigen::Matrix<Scalar, 3, 1>> points;
    std::vector<Eigen::Matrix<int, 3, 1>> faces;
    std::vector<int> input_tags;

    bool skip_simplify = false;
    bool nobinary = false;
    bool nocolor = false;
    bool export_raw = false;

    double stop_energy;
    double ideal_edge_length_rel;
    double eps_rel;

    static bool is_initialized;
    std::unique_ptr<tbb::global_control> scheduler;

    FTetWildWrapperImpl(double stop_energy, double ideal_edge_length_rel, double eps_rel)
    : stop_energy(stop_energy), ideal_edge_length_rel(ideal_edge_length_rel), eps_rel(eps_rel) {
        init();
    }

    ~FTetWildWrapperImpl() {
        delete mesh;
        delete tree;
        delete input_mesh;
    }

    void init() {
        if (!is_initialized) {
            GEO::initialize();
            GEO::CmdLine::import_arg_group("standard");
            GEO::CmdLine::import_arg_group("pre");
            GEO::CmdLine::import_arg_group("algo");
            is_initialized = true;
        }

        #ifndef WIN32
        setenv("GEO_NO_SIGNAL_HANDLER", "1", 1);
        #endif

        unsigned int num_threads = std::max(1u, std::thread::hardware_concurrency());
        scheduler = std::make_unique<tbb::global_control>(
            tbb::global_control::max_allowed_parallelism, num_threads);
    }

    void loadMeshGeometry(Eigen::MatrixXf &nodes, Eigen::MatrixXi &tris) {
        delete mesh;
        mesh = new floatTetWild::Mesh();
        mesh->params.stop_energy = stop_energy;
        mesh->params.ideal_edge_length_rel = ideal_edge_length_rel;
        mesh->params.eps_rel = eps_rel;

        points.clear();
        faces.clear();

        for(int i = 0; i < nodes.rows(); i++)
            points.emplace_back(nodes.row(i).cast<Scalar>());

        for(int i = 0; i < tris.rows(); i++)
            faces.emplace_back(tris.row(i));

        delete input_mesh;
        input_mesh = new GEO::Mesh();
        std::vector<int> flags;
        floatTetWild::MeshIO::load_mesh(points, faces, *input_mesh, flags);

        delete tree;
        tree = new floatTetWild::AABBWrapper(*input_mesh);

        auto& params = mesh->params;
        if (!params.init(tree->get_sf_diag()))
            std::cout << "Initialization failed" << std::endl;

        input_tags.resize(faces.size(), 0);
        floatTetWild::simplify(points, faces, input_tags, *tree, params, skip_simplify);
        tree->init_b_mesh_and_tree(points, faces, *mesh);
    }

    void tetrahedralize() {
        std::vector<bool> is_face_inserted(faces.size(), false);
        floatTetWild::FloatTetDelaunay::tetrahedralize(points, faces, *tree, *mesh, is_face_inserted);
        floatTetWild::insert_triangles(points, faces, input_tags, *mesh, is_face_inserted, *tree, false);
        floatTetWild::optimization(points, faces, input_tags, is_face_inserted, *mesh, *tree, {{1,1,1,1}});
        floatTetWild::correct_tracked_surface_orientation(*mesh, *tree);

        auto& params = mesh->params;
        if (params.smooth_open_boundary) {
            floatTetWild::smooth_open_boundary(*mesh, *tree);
            for (auto& t : mesh->tets)
                if (t.is_outside) t.is_removed = true;
        } else {
            if (!params.disable_filtering) {
                if (params.use_floodfill) {
                    floatTetWild::filter_outside_floodfill(*mesh);
                } else if (params.use_input_for_wn) {
                    floatTetWild::filter_outside(*mesh, points, faces);
                } else {
                    floatTetWild::filter_outside(*mesh);
                }
            }
        }
    }

    void getSurfaceIndices(Eigen::MatrixXi &tris, Eigen::MatrixXi &tets, Eigen::MatrixXf &nodes) {
        using namespace floatTetWild;

        std::map<int, int> old2new;
        int cnt_v = 0;
        for (size_t i = 0; i < mesh->tet_vertices.size(); ++i)
            if (!mesh->tet_vertices[i].is_removed)
                old2new[i] = cnt_v++;

        Eigen::MatrixXd V(cnt_v, 3);
        int vi = 0;
        for (size_t i = 0; i < mesh->tet_vertices.size(); ++i)
            if (!mesh->tet_vertices[i].is_removed)
                V.row(vi++) = mesh->tet_vertices[i].pos.cast<double>();

        int cnt_t = 0;
        for (const auto& t : mesh->tets)
            if (!t.is_removed) cnt_t++;

            Eigen::MatrixXi T(cnt_t, 4);
        int ti = 0;
        std::array<int, 4> order = {0, 1, 3, 2};
        for (const auto& t : mesh->tets) {
            if (t.is_removed) continue;
            for (int j = 0; j < 4; ++j)
                T(ti, j) = old2new.at(t[order[j]]);
            ++ti;
        }

        Eigen::MatrixXd Vs;
        Eigen::MatrixXi Ts, I;
        igl::remove_unreferenced(V, T, Vs, Ts, I);

        Mesh temp_mesh;
        for (int i = 0; i < Vs.rows(); i++)
            temp_mesh.tet_vertices.emplace_back(Vs.row(i));
        for (int i = 0; i < Ts.rows(); i++)
            temp_mesh.tets.emplace_back(Ts.row(i));

        nodes.resize(Vs.rows(), 3);
        for (int i = 0; i < Vs.rows(); i++)
            nodes.row(i) = Vs.row(i).cast<float>();

        tets = Ts;

        ::get_boundary_surface_indices(temp_mesh, tris);
    }

    void save(const std::string& path) {
        Eigen::MatrixXi F, T;
        Eigen::MatrixXf V;
        getSurfaceIndices(F, T, V);

        floatTetWild::Mesh m;
        for(int i = 0; i < V.rows(); i++)
            m.tet_vertices.emplace_back(V.row(i).cast<double>());
        for(int i = 0; i < T.rows(); i++)
            m.tets.emplace_back(T.row(i));

        auto& params = mesh->params;
        igl::write_triangle_mesh(path + "_" + params.postfix + ".obj", V.cast<double>(), F);
        floatTetWild::MeshIO::write_mesh(path + "_" + params.postfix + ".msh", m, false, {}, false);
    }
};

bool FTetWildWrapperImpl::is_initialized = false;

// ====== Delegierende API-Methoden ======
FTetWildWrapper::FTetWildWrapper(double stop_energy, double ideal_edge_length_rel, double eps_rel)
: impl(new FTetWildWrapperImpl(stop_energy, ideal_edge_length_rel, eps_rel)) {}

FTetWildWrapper::~FTetWildWrapper() { delete impl; }

void FTetWildWrapper::loadMeshGeometry(Eigen::MatrixXf &nodes, Eigen::MatrixXi &tris) {
    impl->loadMeshGeometry(nodes, tris);
}

void FTetWildWrapper::tetrahedralize() {
    impl->tetrahedralize();
}

void FTetWildWrapper::save(const std::string &path) {
    impl->save(path);
}

void FTetWildWrapper::getSurfaceIndices(Eigen::MatrixXi &tris, Eigen::MatrixXi &tets, Eigen::MatrixXf &nodes) {
    impl->getSurfaceIndices(tris, tets, nodes);
}
