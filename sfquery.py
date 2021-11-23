from algebra import SANode, Op, negation_normal_form
from pathalg import PANode, POp
import unaryquery


def _make_simple_comp(complist):
    if len(complist) == 1:
        return complist[0]
    return PANode(POp.COMP, [complist[0], _make_simple_comp(complist[1:])])


def graph_paths(node):
    if node.pop == POp.PROP:
        prop = str(node.children[0])
        return f'''
        # graph_paths POp.PROP
        SELECT (?s AS ?t) ?s (<{prop}> AS ?p) ?o (?o AS ?h)
        WHERE {{ ?s <{prop}> ?o }}'''
    if node.pop == POp.ZEROORONE:
        qe1 = graph_paths(node.children[0])
        return f'''
        # graph_paths POp.ZEROORONE
        SELECT *
        WHERE {{
        {{ {qe1} }}
        UNION
        {{
        SELECT (?h AS ?t) ?h
        WHERE {{ {{ ?h ?_p1 ?_o1 }} UNION {{ ?_s2 ?_p2 ?h }} }}
        }} }}'''

    if node.pop == POp.ALT:
        qes = ''
        for child in node.children:
            qes += f'{{ {graph_paths(child)} }} UNION '
        return f'''
        # graph_paths POp.ALT
        SELECT ?t ?s ?p ?o ?h WHERE {{ {qes[:-6]} }}'''

    if node.pop == POp.COMP:
        node = _make_simple_comp(node.children)
        qe1 = graph_paths(node.children[0])
        qe2 = graph_paths(node.children[1])
        return f'''
# graph_paths POp.COMP
SELECT ?t ?s ?p ?o ?h
WHERE {{
{{
  {{
    SELECT ?t ?s ?p ?o (?h AS ?h1)
    WHERE {{ {qe1} }}
  }} .
  {{
    SELECT (?t AS ?h1) (?s AS ?s1) (?p AS ?p1) (?o AS ?o1) ?h
    WHERE {{ {qe2} }}
  }}
}} UNION {{
  {{
    SELECT ?t (?s AS ?s2) (?p AS ?p2) (?o AS ?o2) (?h AS ?h1)
    WHERE {{ {qe1} }}
  }} .
  {{
    SELECT (?t AS ?h1) ?s ?p ?o ?h
    WHERE {{ {qe2} }}
  }}
}} }}
'''
    if node.pop == POp.INV:
        qe1 = graph_paths(node.children[0])
        return f'''
        SELECT (?h AS ?t) ?s ?p ?o (?t AS ?h)
        WHERE {{ {qe1} }}
'''

    if node.pop == POp.KLEENE:
        qe1 = graph_paths(node.children[0])
        path = unaryquery.to_path(node)
        return f'''
# graph_paths POp.KLEENE
SELECT ?t ?s ?p ?o ?h
WHERE {{
  ?t {path} ?x1 .
  ?x2 {path} ?h .
  {{
    SELECT (?t AS ?x1) ?s ?p ?o (?h AS ?x2)
    WHERE {{ {qe1} }}
  }} UNION {{
    SELECT (?h AS ?t) ?h
    WHERE {{ {{ ?h ?_p1 ?_o1 }} UNION {{ ?_s2 ?_p2 ?h }} }}
  }}
}}
'''


def to_sfquery(node, ignore_tests=False):
    # Optimization: OR does not need conformance
    if node.op == Op.OR:
        qps = ''
        for child in node.children:
            qps += f'{{ {to_sfquery(child)} }} UNION '
        return f'SELECT ?v ?s ?p ?o WHERE {{ {qps[:-6]} }}'

    cqp = unaryquery.to_uq(node, ignore_tests=ignore_tests)

    if node.op == Op.AND:
        qps = ''
        for child in node.children:
            qps += f'{{ {to_sfquery(child)} }} UNION '
        return f'''
        SELECT ?v ?s ?p ?o 
        WHERE {{ 
            {{ {cqp} }} . 
            {{
                SELECT ?v ?s ?p ?o 
                WHERE {{
                    {qps[:-6]} 
                }}
            }}
        }}'''

    if node.op == Op.GEQ:
        cqp1 = unaryquery.to_uq(node.children[2], ignore_tests=ignore_tests)
        path = unaryquery.to_path(node.children[1])
        qp1 = to_sfquery(node.children[2])
        # TODO Optimization (??): If node is of the form geq_n E.TEST we should incorporate the test
        # in the graph_paths query.
        # We do this by adding a filter on the head '?h' in the graph_paths construction

        qe = graph_paths(node.children[1])
        # Optimization: If node is of the form geq_n E.TOP, we do not need to retrieve psi
        # we also do not need to conformance check for psi
        if node.children[2].op == Op.TOP:
            return f'''
            SELECT (?t AS ?v) ?s ?p ?o
            WHERE {{
                {{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
                {{ {qe} }} 
            }}'''
        return f'''
        SELECT (?t AS ?v) ?s ?p ?o
        WHERE {{ {{
        {{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
        {{ {qe} }} .
        {{ SELECT (?v AS ?h) WHERE {{ {cqp1} }} }}
        }} UNION {{
        {{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
        ?t {path} ?h .
        {{ SELECT (?v AS ?h) ?s ?p ?o
           WHERE {{ {{ {qp1} }} .  {{ {cqp1} }} }} }} }} }} '''

    # Optimization: If the statement is of the form leq_n E.TOP, then nothing is returned
    if node.op == Op.LEQ and node.children[2].op != Op.TOP:
        qe = graph_paths(node.children[1])
        np1 = negation_normal_form(SANode(Op.NOT, [node.children[2]]))
        cqnp1 = unaryquery.to_uq(np1, ignore_tests=ignore_tests)
        qnp1 = to_sfquery(np1)
        path = unaryquery.to_path(node.children[1])

        return f'''
        SELECT (?t AS ?v) ?s ?p ?o
        WHERE {{
        {{
          {{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
          {{ {qe} }} .
          {{ SELECT (?v AS ?h) WHERE {{ {cqnp1 } }} }}
        }} UNION {{
          {{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
          ?t {path} ?h .
          {{
            SELECT (?v AS ?h) ?s ?p ?o
            WHERE {{ {{ {qnp1} }} . {{ {cqnp1} }} }}
        }} }} }}
        '''

    if node.op == Op.FORALL:
        qe = graph_paths(node.children[0])
        # This often occurs when we "ignore tests"
        # We do not need conformance because all nodes
        # conform to forall E.TOP and all nodes conform to TOP.
        if node.children[1].op == Op.TOP:
            return f'''
            SELECT (?t AS ?v) ?s ?p ?o
            WHERE {{ {{ {qe} }} }}
            '''

        path = unaryquery.to_path(node.children[0])
        qp1 = to_sfquery(node.children[1])

        return f'''
        SELECT (?t AS ?v) ?s ?p ?o
        WHERE {{
        {{
          {{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
          {{ {qe} }}
        }} UNION {{
          {{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
          ?t {path} ?h .
          {{
            SELECT (?v AS ?h) ?s ?p ?o
            WHERE {{ {qp1} }}
        }} }} }}
        '''

    if node.op == Op.EQ:
        qe = graph_paths(node.children[0])
        qp = graph_paths(node.children[1])

        return f'''
SELECT (?t AS ?v) ?s ?p ?o
WHERE {{
{{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
{{ {{ {qe} }} UNION {{ {qp} }} }} }}
'''

    # Optimization
    if node.op == Op.EXACTLY1:
        qe = graph_paths(node.children[0])
        return f'''
        SELECT (?t AS ?v) ?s ?p ?o
        WHERE {{
            {{ SELECT (?v AS ?t) WHERE {{ {cqp} }} }} .
            {{ {qe} }} 
        }}'''

    if node.op == Op.NOT:
        child = node.children[0]
        if child.op == Op.CLOSED:
            notinlist = ''
            for prop in child.children:
                notinlist += f'{str(prop)} ,'
            notinlist = f'( {notinlist[:-1]} )'
        # Optimization: we do not need conformance
            return f'''
SELECT ?v (?v AS ?s) ?p ?o
WHERE {{
?v ?p ?o .
FILTER (?p NOT IN {notinlist})
}}
'''
        if child.op == Op.UNIQUELANG:
            qe = graph_paths(child.children[0])
            path = unaryquery.to_path(child.children[0])

            return f'''
SELECT ( ?t AS ?v ) ?s ?p ?o
WHERE {{
{{ SELECT (?v AS ?t) WHERE {{ {cqp} }} .
{{ {qe} }} .
{{ ?t {path} ?h2 }}
FILTER (?h != ?h2 && lang(?h) = lang(?h2))
'''

        if child.op in [Op.EQ, Op.DISJ, Op.LESSTHAN, Op.LESSTHANEQ]:
            qe = graph_paths(child.children[0])
            qp = graph_paths(child.children[1])
            path = unaryquery.to_path(child.children[0])  # E
            prop = unaryquery.to_path(child.children[1])  # p

            if child.op == Op.EQ:
                # Optimization: no conformance needed
                return f'''
SELECT (?t AS ?v) ?s ?p ?o
WHERE {{
  {{ {{ {qe} }} MINUS {{ ?t {prop} ?h }} }}
  UNION
  {{ {{ {qp} }} MINUS {{ ?t {path} ?h }} }} 
}} 
'''

            if child.op == Op.DISJ:
                # Optimization: no conformance needed
                return f'''
SELECT (?t AS ?v) ?s ?p ?o
WHERE {{
  {{ {{ {qe} }} . {{ ?t {prop} ?h }} }}
  UNION
  {{ {{ {qp} }} . {{ ?t {path} ?h }} }} }}
'''
            if child.op == Op.LESSTHAN:
                # Optimization: no conformance needed
                return f'''
SELECT (?t AS ?v) ?s ?p ?o
WHERE {{
  {{ {{ {qe} }} . {{ ?t {prop} ?h2 }} FILTER (!( ?h < ?h2 )) }}
  UNION
  {{ {{ {qp} }} . {{ ?t {path} ?h2 }} FILTER (!( ?h2 < ?h )) }}
}} 
'''
            if child.op == Op.LESSTHANEQ:
                # Optimization: no conformance needed
                return f'''
SELECT (?t AS ?v) ?s ?p ?o
WHERE {{
  {{ {{ {qe} }} . {{ ?t {prop} ?h2 }} FILTER (!( ?h <= ?h2 )) }}
  UNION
  {{ {{ {qp} }} . {{ ?t {path} ?h2 }} FILTER (!( ?h2 <= ?h )) }}
}}
'''

    # In all other cases, we return the empty query
    return '''
    SELECT ?v ?s ?p ?o
    WHERE {}
    '''