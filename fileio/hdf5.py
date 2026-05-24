import h5py
import numpy as np

#import torch
#from torch_geometric.data import Data
#from torch_geometric.loader import DataLoader


def read_pde_dataset_from_hdf5(pde_file_name):
    train_data = []
    vertices, triangles = None, None
    
    with h5py.File(pde_file_name, 'r') as h5file:
        # Trainingsdaten lesen
        for key in h5file.keys():
            if key.startswith("data_"):
                group = h5file[key]
                data = {
                    'x': np.array(group['x']),
                    'edge_index': np.array(group['edge_index']),
                    'edge_attr': np.array(group['edge_attr']),
                    'y': np.array(group['y']),
                    'coeff': np.array(group['coeff'])
                }
                train_data.append(data)
        
        # Dreiecksnetz lesen
        if 'triangle_mesh' in h5file:
            mesh_group = h5file['triangle_mesh']
            vertices = np.array(mesh_group['vertices'])
            triangles = np.array(mesh_group['triangles'])
    
    print("Die Data-Objekte und das Dreiecksnetz wurden erfolgreich aus der HDF5-Datei gelesen.")
    return train_data, vertices, triangles
