#!/Users/maxime/Documents/programming/shaclsparql/.env/bin/python3

import sys
import os
import algebra
from algebra import SANode, Op

from rdflib import Graph, URIRef, Namespace
from sfquery import to_sfquery

'''
ssf stands for Sparql Shape Fragments

TODO: cleanup cmd argument parsing, it is very naive atm
'''


def _cmd_help():
    print('Help:')
    print(
        f'{sys.argv[0]} [--frag [-i] | --bvg shape | --parser [-neo] shape | --show shape | --latex shape | --info ] file')
    print('Note: shape should be a prefixed iri where the prefix should be defined in the')
    print('      shapes graph. File should be a filename of a Turtle file containing a')
    print('      shapes graph.')
    print('Description:')
    print('Only one mode can be used at a time.')
    print('    --frag [-i] file')
    print('        shows the SPARQL query representing the Shape Fragment of the')
    print('        shape schema given by file')
    print('        -i    ignore all test constraints')
    print('    --bvg shape file')
    print('        be default shows the SPARQL query representing the neighborhood')
    print('        of shape')
    print('    --parser [-neo] shape file')
    print('        by default parses the shape to an S-expression. Options -ne can')
    print('        be used simultaneously')
    print('        -n    puts the S-expression in negation normal form')
    print('        -e    expands the shape references of the S-expression')
    print('        -o    optimizes the S-expression')
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
        shapesgraph.parse(filename, format="ttl")
    except Exception as e:
        print(f'Could not parse file: {filename}')
        print(e)
        exit(1)
    return shapesgraph


def _replace_tests_with_top(tree: SANode) -> SANode:
    new_children = []
    for child in tree.children:
        if type(child) == SANode and child.op == Op.TEST:
            new_children.append(SANode(Op.TOP, []))
        elif type(child) == SANode:  # and not child.op == Op.TEST
            new_children.append(_replace_tests_with_top(child))
        else:
            new_children.append(child)
    return SANode(tree.op, new_children)


def _optimize_ignoring_tests(tree: SANode) -> SANode:
    new_children = []
    for child in tree.children:
        if type(child) == SANode:
            new_children.append(
                _optimize_ignoring_tests(child))
        else:
            new_children.append(child)

    tree = SANode(tree.op, new_children)

    if tree.op == Op.AND:
        # handle TOP children
        if any(map(lambda c: c.op == Op.TOP, tree.children)):
            new_children = list(filter(lambda c: c.op != Op.TOP, tree.children))
            if len(new_children) == 0:
                return SANode(Op.TOP, [])
            elif len(new_children) == 1:
                return new_children[0]
            return SANode(Op.AND, new_children)

        # handle NOT TOP children
        if any(map(lambda c: c.op == Op.NOT and c.children[0].op == Op.TOP, tree.children)):
            return SANode(Op.NOT, [SANode(Op.TOP, [])])

    if tree.op == Op.OR:
        # handle NOT TOP children
        if any(map(lambda c: c.op == Op.NOT and c.children[0].op == Op.TOP, tree.children)):
            new_children = list(filter(lambda c: not (c.op == Op.NOT and c.children[0].op == Op.TOP), tree.children))
            if len(new_children) == 0:
                return SANode(Op.NOT, [SANode(Op.TOP, [])])
            elif len(new_children) == 1:
                return new_children[0]
            return SANode(Op.OR, new_children)

        # handle multiple TOP
        if any(map(lambda c: c.op == Op.TOP, tree.children)):
            new_children = list(filter(lambda c: c.op != Op.TOP, tree.children))
            if len(new_children) == 0:  # they were all TOP
                return SANode(Op.TOP, [])
            # they were not all TOP, but we need one to keep conformance semantics
            new_children.append(SANode(Op.TOP, []))
            return SANode(Op.OR, new_children)

    if tree.op == Op.NOT:
        if tree.children[0].op == Op.NOT and \
                tree.children[0].children[0].op == Op.TOP:
            return SANode(Op.TOP, [])

    return tree


def _optimize_exactly1(tree: SANode) -> SANode:
    new_children = []
    for child in tree.children:
        if type(child) == SANode:
            new_children.append(
                _optimize_exactly1(child))
        else:
            new_children.append(child)

    tree = SANode(tree.op, new_children)

    if tree.op == Op.AND:
        # Optimization: if there is a GEQ 1 E TOP and LEQ 1 E TOP in its children, replace both with EXACTLY 1
        is_geq_one_top = lambda c: c.op == Op.GEQ and \
                                int(c.children[0]) == 1 and \
                                c.children[2].op == Op.TOP
        is_leq_one_top = lambda c: c.op == Op.LEQ and \
                                int(c.children[0]) == 1 and \
                                c.children[2].op == Op.TOP
        if any(map(is_geq_one_top, tree.children)) and \
                any(map(is_leq_one_top, tree.children)):
            geq_one_tops = list(filter(is_geq_one_top, tree.children))
            leq_one_tops = list(filter(is_leq_one_top, tree.children))

            for geq_one in geq_one_tops:
                for leq_one in leq_one_tops:
                    if geq_one.children[1] == leq_one.children[1]:
                        tree.children.append(SANode(Op.EXACTLY1, [geq_one.children[1]]))
                        tree.children.remove(geq_one)
                        tree.children.remove(leq_one)
                        break

            return SANode(Op.AND, tree.children)

    return tree


def _cmd_frag():
    filename = _get_filename()
    shapesgraph = _get_shapesgraph(filename)

    ignore_tests = '-i' in sys.argv  # if -i is in the options, ignore tests

    # If you ignore tests at parse time, we get a non-intuitive definition of shape neighborhoods
    # if the parser encounters shapes like for example:
    # :exampleshape a sh:nodeshape;
    #   sh:propertyshape [
    #     sh:path :email ].
    # (this would occur if there would have been a test on all emails, but it is ignored by the
    #  parser so it effectively sees the shape above)
    # then it would translate it to: forall email. TOP
    # and at parse time, this is indistinguishable from a parsing artifact from the way
    # we translate from RDF shacl to the algebra. Therefore, it is removed from the parse tree.
    # There would be no neighborhood for emails, eventhough there would be one if forall email.TOP
    # is retained in the shape.
    # TODO: when you actually write a shape like the above, it would be removed at parse time.
    # The task is to not remove it and retain precisely what we want for the shape fragment
    definitions, targets = algebra.parse(shapesgraph, ignore_tests=False)

    # expand every shape that is defined in the schema
    # put the shape in negation normal form
    # add its target statement as a conjunction
    # optimize this expression (remove redundancies from algebra)
    prepared_shapes = []
    for shape_name in definitions:
        if shape_name not in targets or targets[shape_name] == SANode(Op.NOT, [SANode(Op.TOP, [])]):
            continue  # we ignore the shapes that do not have any targets

        prepared_shapes.append(
            algebra.optimize_tree(
                SANode(Op.AND, [
                    algebra.negation_normal_form(
                        algebra.expand_shape(definitions, definitions[shape_name])),
                    targets[shape_name]
                ])))

    # Until now, everything is processed nicely as usual.
    # However, when we know we want to ignore tests we can do some nice alterations
    # on the syntax tree:
    # 1. Replace every occurrence of a test-node to a top-node
    # 2. Apply optimizations:
    #    - remove tops from conjunction
    #    - remove tops from disjunction (shapefragment-semantically the same BUT not a good optimization!!
    #      because the tree must be correct wrt conformance at any time...)
    #    - replace disjunction with only TOPs with TOP
    #    - replace conjunctions with == 0 children with TOP
    #    - replace conjunctions with == 1 child with the child
    #    - search and replace "exactly one pattern"
    if ignore_tests:
        _eo_prepared_shapes = []
        for shape in prepared_shapes:
            _tt_shape = _replace_tests_with_top(shape)
            _it_shape = _optimize_ignoring_tests(_tt_shape)
            _eo_shape = _optimize_exactly1(_it_shape)
            _eo_prepared_shapes.append(_eo_shape)
        prepared_shapes = _eo_prepared_shapes

    # translate every shape to a shape fragment query
    shape_queries = []
    for shape in prepared_shapes:
        # here, the ignore_tests works only at translation time
        shape_queries.append(to_sfquery(shape, ignore_tests=False))

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
    option_o = False
    if len(sys.argv) == 5:
        option_n = 'n' in sys.argv[-3]
        option_e = 'e' in sys.argv[-3]
        option_o = 'o' in sys.argv[-3]
        if not (option_e or option_n or option_o):
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
    if option_o:
        out = algebra.optimize_tree(out)
    print(out)
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
        print(f'{prefix}{" " * (16 - len(prefix))}{uri}')

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
    if argc == 2 or ('--frag' in sys.argv and 3 <= argc <= 4):
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
