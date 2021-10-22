#!/Users/maxime/Documents/programming/shaclsparql/.env/bin/python3

import sys
import os
import algebra

from rdflib import Graph, URIRef, Namespace
from sfquery import to_sfquery

'''
ssf stands for Sparql Shape Fragments

TODO: cleanup cmd argument parsing, it is very naive atm
'''


def _cmd_help():
    print('Help:')
    print(f'{sys.argv[0]} [--frag | --bvg shape | --parser [options] shape | --show shape | --latex shape | --info ] file')
    print('Note: shape should be a prefixed iri where the prefix should be defined in the')
    print('      shapes graph. File should be a filename of a Turtle file containing a')
    print('      shapes graph.')
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
    print('    --latex shape file')
    print('        (experimental) outputs the shape algebra as a LaTeX formula')
    print('    --info file')
    print('        prints general information about the shapes graph contained in file')
    exit(0)


def _resolve_prefixed_shapename(namespacemanager, shapename):
    qnames = [qname for qname in namespacemanager.namespaces()]

    try:
        split_name = shapename.split(':')
        prefix = split_name[0]
        rest = split_name[1]
    except:
        print(f'Could not parse prefixed shapename "{shapename}"')
        exit(1)

    for pre, uri in qnames:
        if pre == prefix:
            ns = Namespace(uri)
            return ns[rest]

    print(f'Prefix "{prefix}" not defined in graph')
    exit(1)


def _get_filename():
    filename = sys.argv[-1]
    if not os.path.exists(filename):
        print(f'Could not find file: {filename}')
        exit(1)
    return filename


def _get_shapesgraph(filename):
    shapesgraph = Graph()
    try:
        shapesgraph.parse(filename)
    except Exception as e:
        print(f'Could not parse file: {filename}')
        print(e)
        exit(1)
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
    exit(0)


def _cmd_bvg():
    filename = _get_filename()
    prefixed_shapename = sys.argv[-2]
    shapesgraph = _get_shapesgraph(filename)
    shapename = _resolve_prefixed_shapename(shapesgraph.namespace_manager,
                                            prefixed_shapename)

    definitions, targets = algebra.parse(shapesgraph)

    if shapename not in definitions:
        print(f'Shape {shapename} is not defined in {filename}')
        exit(1)


    print(to_sfquery(algebra.optimize_tree(algebra.negation_normal_form(
        algebra.expand_shape(definitions, definitions[shapename])))))
    exit(0)


def _cmd_parser():
    filename = sys.argv[-1]
    prefixed_shapename = URIRef(sys.argv[-2])
    shapesgraph = _get_shapesgraph(filename)
    shapename = _resolve_prefixed_shapename(shapesgraph.namespace_manager,
                                            prefixed_shapename)

    definitions, targets = algebra.parse(shapesgraph)

    option_n = False
    option_e = False
    if len(sys.argv) == 5:
        option_n = 'n' in sys.argv[-3]
        option_e = 'e' in sys.argv[-3]
        if not (option_e or option_n):
            print(f'No valid options found in {sys.argv[-3]}')
            exit(1)

    if shapename not in definitions:
        print(f'Shape {shapename} is not defined in {filename}')
        exit(1)

    out = definitions[shapename]
    if option_e:
        out = algebra.expand_shape(definitions, out)
    if option_n:
        out = algebra.negation_normal_form(out)

    print(algebra.optimize_tree(out))
    exit(0)


def _cmd_latex():
    filename = sys.argv[-1]
    prefixed_shapename = URIRef(sys.argv[-2])
    shapesgraph = _get_shapesgraph(filename)
    shapename = _resolve_prefixed_shapename(shapesgraph.namespace_manager,
                                            prefixed_shapename)

    definitions, targets = algebra.parse(shapesgraph)

    if shapename not in definitions:
        print(f'Shape {shapename} is not defined in {filename}')
        exit(1)

    out = algebra.optimize_tree(definitions[shapename])

    print(algebra.sa_as_latex(algebra.negation_normal_form(
        algebra.expand_shape(definitions, out))))
    exit(0)


def _cmd_info():
    filename = sys.argv[-1]
    shapesgraph = _get_shapesgraph(filename)

    definitions, targets = algebra.parse(shapesgraph)

    print('Defined prefixes:')
    for prefix, uri in shapesgraph.namespace_manager.namespaces():
        print(f'{prefix}{" "*(16-len(prefix))}{uri}')

    shapes_with_target = []
    shapes_rest = []
    for shapename in definitions:
        has_target = targets[shapename] != algebra.SANode(
            algebra.Op.NOT, [algebra.SANode(algebra.Op.TOP, [])])
        if has_target:
            shapes_with_target.append(shapename.n3(shapesgraph.namespace_manager))
        else:
            shapes_rest.append(shapename.n3(shapesgraph.namespace_manager))

    print('\nShapes with target(s):')
    for shape in shapes_with_target:
        print(shape)

    print('\nShapes without target:')
    for shape in shapes_rest:
        print(shape)

    exit(0)

if __name__ == '__main__':
    argc = len(sys.argv)

    # if only a file name or frag
    if argc == 2 or ('--frag' in sys.argv and argc == 3):
         _cmd_frag()
    elif '--bvg' in sys.argv and argc == 4:
        _cmd_bvg()
    elif '--parser' in sys.argv and 4 <= argc <= 5:
        _cmd_parser()
    elif '--latex' in sys.argv and argc == 4:
        _cmd_latex()
    elif '--info' in sys.argv and argc == 3:
        _cmd_info()

    _cmd_help()

    exit(0)
