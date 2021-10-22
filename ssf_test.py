import os
from rdflib import Graph, URIRef, Namespace
from ssf import from_shapes_graph
from algebra import parse, optimize_tree, expand_shape, negation_normal_form

def test_build_fragment():
    folders = ['tyrol']

    files = []
    for folder in folders:
        folder_path = f'./real_shacl_testfiles/{folder}'
        for file in os.listdir(folder_path):  # there may be no folders in folder_pat# h
            files.append(f'{folder_path}/{file}')

    out = []
    for file in files:
        file = './real_shacl_testfiles/tyrol/wineryshape.ttl'
        #print('========= FILE =========')
        print(file)
        shapes_graph = Graph()
        shapes_graph.parse(file)
        query = from_shapes_graph(shapes_graph)
        #print('========= QUERY =========')
        #print(query)
        out.append(query)
        # with open(f'{file}.txt', 'w') as f:
        #    f.write(query)
        definitions, targets = parse(shapes_graph)
        for definition in definitions:
            definitions[definition] = optimize_tree(definitions[definition])
        for definition in definitions:
            definitions[definition] = negation_normal_form(expand_shape(definitions, definitions[definition]))
            with open(f'{file}_{definition[25:]}.txt', 'w') as f:
                f.write(str(definitions[definition]))
        break

    return out

test_build_fragment()