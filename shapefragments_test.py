import os
from rdflib import Graph
from shapefragments import from_shapes_graph


def test_build_fragment():
    folders = ['tyrol']

    files = []
    for folder in folders:
        folder_path = f'./real_shacl_testfiles/{folder}'
        for file in os.listdir(folder_path):  # there may be no folders in folder_pat# h
            files.append(f'{folder_path}/{file}')

    out = []
    for file in files:
        #print('========= FILE =========')
        print(file)
        shapes_graph = Graph()
        shapes_graph.parse(file)
        query = from_shapes_graph(shapes_graph)
        #print('========= QUERY =========')
        #print(query)
        out.append(query)

    return out