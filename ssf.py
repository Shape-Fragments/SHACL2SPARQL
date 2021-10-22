import sys
import os
import algebra

from rdflib import Graph
from sfquery import to_sfquery

'''
ssf stands for Sparql Shape Fragments
'''

# def from_shapes_graph(graph: Graph):
#     definitions, targets = parse(graph)
#
#     # expand every shape that is defined in the schema
#     # put the shape in negation normal form
#     # add its target statement as a conjunction
#     # optimize this expression (remove redundancies from algebra)
#     prepared_shapes = []
#     for shape_name in definitions:
#         if shape_name not in targets:
#             continue  # we ignore the shapes that do not have any targets
#
#         prepared_shapes.append(
#             optimize_tree(
#                 SANode(Op.AND, [
#                     negation_normal_form(
#                         expand_shape(definitions, definitions[shape_name])),
#                     targets[shape_name]
#                 ])))
#
#     # translate every shape to a shape fragment query
#     shape_queries = []
#     for shape in prepared_shapes:
#         shape_queries.append(to_sfquery(shape))
#
#     # take the union of every query as the total shape fragment query
#     fragment_query = 'SELECT ?v ?s ?p ?o WHERE { '
#     for query in shape_queries:
#         fragment_query += f'''
#         # new shape as query
#         {{ {query} }} UNION '''
#
#     return fragment_query[:-6] + '}'


def _cmd_help():
    print('Help:')
    print(f'{sys.argv[0]} [--frag | --bvg shape | --parser [options] shape] file')
    print('Note: shape should be a shape name (full IRI). File should be a filename')
    print('      of a Turtle file containing a shapes graph.')
    print('Description:')
    print('Only one mode can be used at a time.')
    print('    --frag file')
    print('        shows the SPARQL query representing the Shape Fragment of the')
    print('        shape schema given by file')
    print('    --bvg shape file')
    print('        be default shows the SPARQL query representing the neighborhood')
    print('        of shape')
    print('    --parser [-ne] shape file')
    print('        by default parses the shape to an S-expression. Options -ne can')
    print('        be used simultaneously')
    print('        -n    puts the S-expression in negation normal form')
    print('        -e    expands the shape references of the S-expression')


def _get_filename():
    filename = sys.argv[-1]
    if not os.path.exists(filename):
        print(f'Could not find file: {filename}')
        exit()
    return filename


def _get_shapesgraph(filename):
    shapesgraph = Graph()
    try:
        shapesgraph.parse(filename)
    except Exception as e:
        print(f'Could not parse file: {filename}')
        print(e)
        exit()
    return shapesgraph


def _cmd_frag():
    filename = _get_filename()
    shapesgraph = _get_shapesgraph(filename)

    definitions, targets = algebra.parse(shapesgraph)

    # expand every shape that is defined in the schema
    # put the shape in negation normal form
    # add its target statement as a conjunction
    # optimize this expression (remove redundancies from algebra)
    prepared_shapes = []
    for shape_name in definitions:
        if shape_name not in targets:
            continue  # we ignore the shapes that do not have any targets

        prepared_shapes.append(
                 algebra.optimize_tree(
                     algebra.SANode(algebra.Op.AND, [
                     algebra.negation_normal_form(
                             algebra.expand_shape(definitions, definitions[shape_name])),
                         targets[shape_name]
                     ])))

    # translate every shape to a shape fragment query
    shape_queries = []
    for shape in prepared_shapes:
        shape_queries.append(to_sfquery(shape))

    # take the union of every query as the total shape fragment query
    fragment_query = 'SELECT ?v ?s ?p ?o WHERE { '
    for query in shape_queries:
        fragment_query += f'''
        # new shape as query
        {{ {query} }} UNION '''

    print(fragment_query[:-6] + '}')


def _cmd_bvg():
    filename = _get_filename()
    shapename = sys.argv[-2]

    shapesgraph = _get_shapesgraph(filename)

    definitions, targets = algebra.parse(shapesgraph)

    if shapename not in definitions:
        print(f'Shape {shapename} is not defined in {filename}')
        exit()

    




def _cmd_parser():
    filename = sys.argv[-1]


if __name__ == '__main__':
    argc = len(sys.argv)
    # if only a file name or frag
    if argc == 2 or ('--frag' in sys.argv and argc == 3):
        _cmd_frag()
    elif '--bvg' in sys.argv and argc == 4:
        _cmd_bvg()
    elif '--parser' in sys.argv and argc >= 4:
        _cmd_parser()

    _cmd_help()