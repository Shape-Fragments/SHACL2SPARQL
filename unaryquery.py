from algebra import SANode, Op
from pathalg import PANode, POp
from rdflib.namespace import SH


def _build_query(body):
    return f'SELECT ?v WHERE {{ {body} }}'


def _build_all_query():
    return _build_query('{ ?v ?_a ?_b. } UNION { ?_c ?_d ?v }')


def _build_join(queries):
    out = ''
    for query in queries:
        out += f'{{ {query} }} . '
    return _build_query(out[:-2])


def _build_union(queries):
    out = ''
    for query in queries:
        out += f'{{ {query} }} UNION '
    return _build_query(out[:-6])


def _build_negate(shape):
    return _build_difference_query(_build_all_query(), shape)


def _build_difference_query(superquery, subquery):
    return _build_query(f'{{ {superquery} }} MINUS {{ {subquery} }}')


def _build_exists_query(path):
    return _build_query(f'?v {path} ?_o .')


def _build_closed_query(properties):
    exist_queries = []
    for prop in properties:
        exist_queries.append(_build_exists_query(prop))
    return _build_negate(_build_union(exist_queries))


def _build_disjoint_query(path1, path2):
    return _build_query(f'''
{{
  ?v {path1} ?o1
  FILTER NOT EXISTS {{ ?v {path1} ?o2 . ?v {path2} ?o2 }}
}} UNION {{
  ?v {path2} ?o3
  FILTER NOT EXISTS {{
    ?v {path1} ?o4 .
    ?v {path2} ?o4 }}
}} UNION {{
  ?s ?q1 ?v FILTER NOT EXISTS {{ ?v ?q4 ?o9 }}
}} UNION {{
  ?v ?q2 ?o5 FILTER NOT EXISTS {{ ?v {path1} ?o6 }}
}} UNION {{
  ?v ?q3 ?o7 FILTER NOT EXISTS {{ ?v  {path2}  ?o8 }}
}}''')


def _build_equality_query(path1, path2):
    return _build_query(f'''
{{?v {path1} ?o1
  FILTER NOT EXISTS {{ ?v {path1}  ?o2
    FILTER NOT EXISTS {{ ?v {path2}  ?o2 }} }} .
  {{?v {path2} ?o1
    FILTER NOT EXISTS {{ ?v {path2} ?o3
      FILTER NOT EXISTS {{ ?v {path1} ?o3 }} }} }}
}} UNION {{
  ?s ?q1 ?v FILTER NOT EXISTS {{ ?v ?q4 ?o8 }} .
}} UNION {{
  ?v ?q2 ?o4 FILTER NOT EXISTS {{ ?v {path1} ?o5 }} .
  ?v ?q3 ?o6 FILTER NOT EXISTS {{ ?v {path2} ?o7 }} }}
''')


def _build_forall_query(path, shape):
    return _build_negate(
        _build_query(f'''
?v {path} ?o.
{{
  SELECT (?v AS ?o)
  WHERE {{ {_build_negate(shape)} }}
}}
'''))


def _build_geq_query(num, path, shape):
    return _build_query(f'''
?v {path} ?o .
{{ SELECT (?v AS ?o) WHERE {{ {shape} }} }}
''') + f' GROUP BY ?v HAVING (COUNT(?o) >= {str(num)} )'


def _build_leq_query(num, path, shape):
    return _build_query(f'''
?v {path} ?o .
{{ SELECT (?v AS ?o) WHERE {{ {shape} }} }}
''') + f' GROUP BY ?v HAVING (COUNT(?o) <= {str(num)} )'


def _build_lt_query(path, prop):
    return _build_query(f'''
?v {path} ?e FILTER NOT EXISTS {{ ?v {prop} ?p FILTER ( ?p >= ?e )}}
''')


def _build_lte_query(path, prop):
    return _build_query(f'''
?v {path} ?e FILTER NOT EXISTS {{ ?v {prop} ?p FILTER ( ?p > ?e )}}
''')


def _build_hasvalue_query(value):
    return _build_query(f'BIND ( <{str(value)}> AS ?v )')


def _build_uniquelang_query(path):
    raise NotImplementedError()


def _build_test_query(test_type, parameter):
    if test_type == 'datatype':
        return _build_query(
            f'{{ {_build_all_query()} }} FILTER (datatype(?v) = <{str(parameter)}>)')
    if test_type == 'nodekind':
        if parameter == SH.IRI:
            return _build_query(
                f'{{ {_build_all_query()} }} FILTER isIRI(?v)')
        if parameter == SH.Literal:
            return _build_query(
                f'{{ {_build_all_query()} }} FILTER isLiteral(?v)')
        if parameter == SH.BlankNode:
            return _build_query(
                f'{{ {_build_all_query()} }} FILTER isBlank(?v)')
        if parameter == SH.BlankNodeOrIRI:
            return _build_query(
                f'{{ {_build_all_query()} }} FILTER (isIRI(?v) || isBlank(?v))')
        if parameter == SH.BlankNodeOrLiteral:
            return _build_query(
                f'{{ {_build_all_query()} }} FILTER (isBlank(?v) || isLiteral(?v))')
        if parameter == SH.IRIOrLiteral:
            return _build_query(
                f'{{ {_build_all_query()} }} FILTER (isIRI(?v) || isLiteral(?v))')

    if test_type == 'min_exclusive':
        return _build_query(
            f'{{ {_build_all_query()} }} FILTER ( ?v > {str(parameter)} )')
    if test_type == 'max_exclusive':
        return _build_query(
            f'{{ {_build_all_query()} }} FILTER ( ?v < {str(parameter)} )')
    if test_type == 'min_inclusive':
        return _build_query(
            f'{{ {_build_all_query()} }} FILTER ( ?v >= {str(parameter)} )')
    if test_type == 'max_inclusive':
        return _build_query(
            f'{{ {_build_all_query()} }} FILTER ( ?v <= {str(parameter)} )')
    if test_type == 'min_length':
        return _build_query(
            f'{{ {_build_all_query()} }} FILTER ( strlen(?v) >= {str(parameter)} )')
    if test_type == 'max_length':
        return _build_query(
            f'{{ {_build_all_query()} }} FILTER ( strlen(?v) <= {str(parameter)} )')


def _build_pattern_query(pattern, flags):
    fmt_flags = ''
    for flag in flags:
        fmt_flags += str(flag)
    return _build_query(
        f'{{ {_build_all_query()} }} FILTER regex(?v, "{str(pattern)}", "{fmt_flags}")')


def to_path(node: PANode) -> str:
    """to sparql path"""
    if node.pop == POp.PROP:
        return '<' + str(node.children[0]) + '>'

    if node.pop == POp.INV:
        return '^(' + to_path(node.children[0]) + ')'

    if node.pop == POp.ALT:
        out = ''
        for child in node.children:
            out += to_path(child) + '|'
        return out[:-1]

    if node.pop == POp.COMP:
        out = ''
        for child in node.children:
            out += to_path(child) + '/'
        return out[:-1]

    if node.pop == POp.KLEENE:
        return '(' + to_path(node.children[0]) + ')*'

    if node.pop == POp.ZEROORONE:
        return '(' + to_path(node.children[0]) + ')+'


def to_uq(node: SANode) -> str:
    """to unary query; assumes shape is expanded"""
    if node.op == Op.HASSHAPE:
        raise ValueError('node must be expanded')

    if node.op == Op.TOP:
        return _build_all_query()

    if node.op == Op.AND:
        subqueries = []
        for child in node.children:
            subqueries.append(to_uq(child))
        return _build_join(subqueries)

    if node.op == Op.OR:
        subqueries = []
        for child in node.children:
            subqueries.append(to_uq(child))
        return _build_union(subqueries)

    if node.op == Op.NOT:
        return _build_difference_query(_build_all_query(),
                                       to_uq(node.children[0]))

    if node.op == Op.CLOSED:
        properties = []
        for child in node.children:
            properties.append(to_path(child))
        return _build_closed_query(properties)

    if node.op == Op.DISJ:
        return _build_disjoint_query(to_path(node.children[0]),
                                     to_path(node.children[1]))

    if node.op == Op.EQ:
        return _build_equality_query(to_path(node.children[0]),
                                     to_path(node.children[1]))

    if node.op == Op.FORALL:
        return _build_forall_query(to_path(node.children[0]),
                                   to_uq(node.children[1]))

    if node.op == Op.GEQ:
        return _build_geq_query(node.children[0],
                                to_path(node.children[1]),
                                to_uq(node.children[2]))

    if node.op == Op.LEQ:
        return _build_leq_query(node.children[0],
                                to_path(node.children[1]),
                                to_uq(node.children[2]))

    if node.op == Op.LESSTHAN:
        return _build_lt_query(to_path(node.children[0]),
                               to_path(node.children[1]))

    if node.op == Op.LESSTHANEQ:
        return _build_lte_query(to_path(node.children[0]),
                                to_path(node.children[1]))

    if node.op == Op.HASVALUE:
        return _build_hasvalue_query(node.children[0])

    if node.op == Op.UNIQUELANG:
        return _build_uniquelang_query(to_path(node.children[0]))

    if node.op == Op.TEST:
        if node.children[0] == 'pattern':
            return _build_pattern_query(node.children[1], node.children[2])
        return _build_test_query(node.children[0], node.children[1])