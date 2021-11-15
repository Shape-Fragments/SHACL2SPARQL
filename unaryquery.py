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
    propstr = ''
    for prop in properties:
        propstr += prop + ', '
    return _build_query(f'''
    ?s ?p ?o FILTER ?p NOT IN ( {propstr[:-2]} )
''')


def _build_disjoint_query(path1, path2):
    '''N_G minus v {p1} o . v {p2} o'''
    return _build_negate(
        _build_query(f'''
    ?v {path1} ?o .
    ?v {path2} ?o
'''))


def _build_equality_query(path1, path2):
    return _build_negate(
        _build_query(f'''
    {{
      ?v {path1} ?o 
      FILTER NOT EXISTS {{ ?v {path2} ?o }}
    }} UNION {{
      ?v {path2} ?o 
      FILTER NOT EXISTS {{ ?v {path1} ?o }}
    }}
'''))


def _build_forall_query(path, shape):
    return _build_negate(
        _build_query(f'''
        ?v {path} ?o.
        {{
          SELECT (?v AS ?o)
          WHERE {{ {_build_negate(shape)} }}
        }}'''))


def _build_forall_test_query(path, neg_filter_condition):
    return _build_negate(
        _build_query(f' ?v {path} ?o FILTER {neg_filter_condition} '))


def _build_geq_query(num, path, shape):
    return _build_query(f'''
    ?v {path} ?o .
    {{ SELECT (?v AS ?o) WHERE {{ {shape} }} }}
    ''') + f' GROUP BY ?v HAVING (COUNT(?o) >= {str(num)} )'


def _build_geq_top_query(num, path):
    return _build_query(f'?v {path} ?o') + f' GROUP BY ?v HAVING (COUNT(?o) >= {str(num)} )'


def _build_geq_test_query(num, path, filter_condition):
    return _build_query(f'?v {path} ?o FILTER {filter_condition}') + f' GROUP BY ?v HAVING (COUNT(?o) >= {str(num)} )'


def _build_leq_query(num, path, shape):
    return _build_query(f'''
?v {path} ?o .
{{ SELECT (?v AS ?o) WHERE {{ {shape} }} }}
''') + f' GROUP BY ?v HAVING (COUNT(?o) <= {str(num)} )'


def _build_leq_top_query(num, path):
    return _build_query(f'?v {path} ?o') + f' GROUP BY ?v HAVING (COUNT(?o) <= {str(num)} )'


def _build_leq_test_query(num, path, filter_condition):
    return _build_query(f'?v {path} ?o FILTER {filter_condition}') + f' GROUP BY ?v HAVING (COUNT(?o) <= {str(num)} )'


def _build_lt_query(path, prop):
    return _build_query(f'''
?v {path} ?e FILTER NOT EXISTS {{ ?v {prop} ?p FILTER ( ?p >= ?e )}}
''')


def _build_lte_query(path, prop):
    return _build_query(f'''
    ?v {path} ?e FILTER NOT EXISTS {{ ?v {prop} ?p FILTER ( ?p > ?e )}}''')


def _build_hasvalue_query(value):
    return _build_query(f'BIND ( <{str(value)}> AS ?v )')


def _build_uniquelang_query(path):
    return _build_negate(
        _build_query(f'''
        SELECT ?v
        WHERE {{
            ?v {path} ?o1 .
            ?v {path} ?o2 
            FILTER ( ?o1 != ?o2 && lang(?o1) = lang(?o2) && lang(?o1) != "" )
        }}
        '''))


def build_filter_condition(test_type, parameter, pattern_flags=[], negate=False, var='?v'):
    neg = '' if not negate else '!'

    if test_type == 'pattern':
        fmt_flags = ''
        for flag in pattern_flags:
            fmt_flags += str(flag)
        return f'({neg}regex({var}, "{str(parameter)}", "{fmt_flags}"))'

    if test_type == 'datatype':
        return f'({neg}(datatype({var}) = <{str(parameter)}>))'
    if test_type == 'nodekind':
        if parameter == SH.IRI:
            return f'({neg}isIRI({var}))'
        if parameter == SH.Literal:
            return f'({neg}isLiteral({var}))'
        if parameter == SH.BlankNode:
            return f'({neg}isBlank({var}))'
        if parameter == SH.BlankNodeOrIRI:
            return f'({neg}(isIRI({var}) || isBlank({var})))'
        if parameter == SH.BlankNodeOrLiteral:
            return f'({neg}(isBlank({var}) || isLiteral({var})))'
        if parameter == SH.IRIOrLiteral:
            return f'({neg}(isIRI({var}) || isLiteral({var})))'

    if test_type == 'min_exclusive':
        return f'({neg}( {var} > {str(parameter)} ))'
    if test_type == 'max_exclusive':
        return f'({neg}( {var} < {str(parameter)} ))'
    if test_type == 'min_inclusive':
        return f'({neg}( {var} >= {str(parameter)} ))'
    if test_type == 'max_inclusive':
        return f'({neg}( {var} <= {str(parameter)} ))'
    if test_type == 'min_length':
        return f'({neg}( strlen({var}) >= {str(parameter)} ))'
    if test_type == 'max_length':
        return f'({neg}( strlen({var}) <= {str(parameter)} ))'


def _build_test_query(test_type, parameter, negate=False):
    return _build_query(
        f'{{ {_build_all_query()} }} FILTER {build_filter_condition(test_type, parameter, negate=negate)}')


def _build_pattern_query(pattern, flags, negate=False):
    return _build_query(
        f'{{ {_build_all_query()} }} FILTER {build_filter_condition("pattern", pattern, pattern_flags=flags, negate=negate)}')


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
        others = [child for child in node.children if child.op != Op.TEST]
        subqueries = []
        for child in others:
            subqueries.append(to_uq(child))

        # Optimization: an and of tests is a test of ands
        tests = [child for child in node.children if child.op == Op.TEST]
        if tests:
            conj_tests = '( '
            for test in tests:
                if test.children[0] == 'pattern':
                    conj_tests += build_filter_condition('pattern', test.children[1], pattern_flags=test.children[2],
                                                         negate=False) + ' && '
                else:
                    conj_tests += build_filter_condition(test.children[0], test.children[1]) + ' && '
            conj_tests = conj_tests[:-4] + ' )'

            subqueries.append(_build_query(f'{{ {_build_all_query()} }} FILTER {conj_tests}'))

        return _build_join(subqueries)

    if node.op == Op.OR:
        others = [child for child in node.children if child.op != Op.TEST]
        subqueries = []
        for child in others:
            subqueries.append(to_uq(child))

        # Optimization: an or of tests is a test of ors
        tests = [child for child in node.children if child.op == Op.TEST]
        if tests:
            disj_tests = '( '
            for test in tests:
                if test.children[0] == 'pattern':
                    disj_tests += build_filter_condition('pattern', test.children[1], pattern_flags=test.children[2],
                                                         negate=False) + ' || '
                else:
                    disj_tests += build_filter_condition(test.children[0], test.children[1]) + ' || '
            disj_tests = disj_tests[:-4] + ' )'

            subqueries.append(_build_query(f'{{ {_build_all_query()} }} FILTER {disj_tests}'))

        return _build_union(subqueries)

    if node.op == Op.NOT:
        child = node.children[0]
        # Optimization: if the shape is of the form: NOT TEST,
        # then we alter the test itself instead of ALL minus TEST
        if child.op == Op.TEST:
            if child.children[0] == 'pattern':
                return _build_pattern_query(child.children[1], child.children[2])
            return _build_test_query(child.children[0], child.children[1])
        # For all other cases:
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
        child = node.children[1]
        if child.op == Op.TEST:
            cond = build_filter_condition(
                child.children[0], child.children[1], negate=True) if child.children[0] != 'pattern' \
                else build_filter_condition('pattern', child.children[1],
                                            pattern_flags=child.children[2], negate=True)
            return _build_forall_test_query(to_path(node.children[0]), cond)

        return _build_forall_query(to_path(node.children[0]),
                                   to_uq(child))

    if node.op == Op.GEQ:
        path = to_path(node.children[1])
        # Optimization
        if node.children[2].op == Op.TOP:
            return _build_geq_top_query(node.children[0], path)
        # Optimization
        if node.children[2].op == Op.TEST:
            child = node.children[1]
            cond = build_filter_condition(
                child.children[0], child.children[1]) if child.children[0] != 'pattern' \
                else build_filter_condition('pattern', child.children[1],
                                            pattern_flags=child.children[2])
            return _build_geq_test_query(node.children[0], path, cond)
        return _build_geq_query(node.children[0], path,
                                to_uq(node.children[2]))

    if node.op == Op.LEQ:
        path = to_path(node.children[1])
        # Optimization
        if node.children[2].op == Op.TOP:
            return _build_leq_top_query(node.children[0], path)
        # Optimization
        if node.children[2].op == Op.TEST:
            child = node.children[1]
            cond = build_filter_condition(
                child.children[0], child.children[1]) if child.children[0] != 'pattern' \
                else build_filter_condition('pattern', child.children[1],
                                            pattern_flags=child.children[2])
            return _build_leq_test_query(node.children[0], path, cond)
        return _build_leq_query(node.children[0], path,
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