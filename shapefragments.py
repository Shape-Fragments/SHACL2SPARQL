from rdflib import Graph

from algebra import parse, SANode, Op, negation_normal_form, expand_shape, optimize_tree
from sfquery import to_sfquery


def from_shapes_graph(graph: Graph):
    definitions, targets = parse(graph)

    # expand every shape that is defined in the schema
    # put the shape in negation normal form
    # add its target statement as a conjunction
    # optimize this expression (remove redundancies from algebra)
    prepared_shapes = []
    for shape_name in definitions:
        if shape_name not in targets:
            continue  # we ignore the shapes that do not have any targets

        prepared_shapes.append(
            optimize_tree(
                SANode(Op.AND, [
                    negation_normal_form(
                        expand_shape(definitions, definitions[shape_name])),
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

    return fragment_query[:-6] + '}'