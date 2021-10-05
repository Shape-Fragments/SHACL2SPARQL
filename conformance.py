import mypy
import rdflib

from algebra import parse, expand_shape
from unaryquery import to_uq


def conforms(data_graph: rdflib.Graph, shapes_graph: rdflib.graph):
    not_conforms = []
    conforms = []

    schema = parse(shapes_graph)
    shape_defs = schema[0]
    target_defs = schema[1]
    # Reminder: a schema consists out of two dicts
    # Both dicts: IRI (shape name) -> SANode
    # In the first dict, the range is the shape definitions
    # In the second dict, the range is the target definitions if present

    for shape_name in list(shape_defs):
        if shape_name not in list(target_defs):
            continue  # if there is no target definition, skip
        expanded = expand_shape(shape_defs, shape_defs[shape_name])
        shapedef_uq = to_uq(expanded)
        targetdef_uq = to_uq(target_defs[shape_name])

        rhs = _result_to_set(data_graph.query(shapedef_uq))
        lhs = _result_to_set(data_graph.query(targetdef_uq))

        if not lhs.issubset(rhs):
            not_conforms.append(lhs.difference(rhs))
        else:
            conforms.append(lhs)

    return conforms, not_conforms


def _result_to_set(result: rdflib.query.Result) -> set:
    out = set()
    for row in result:
        out.add(row.v)  # v is the SELECT variable
    return out


