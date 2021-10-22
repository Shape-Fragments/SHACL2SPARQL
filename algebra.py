import mypy
from typing import List
from enum import Enum, auto

from rdflib import Graph
from rdflib.term import URIRef, Literal, BNode
from rdflib.namespace import SH, RDF
from rdflib.collection import Collection

import pathalg


class Op(Enum):
    HASVALUE = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    TEST = auto()
    HASSHAPE = auto()
    GEQ = auto()
    LEQ = auto()
    FORALL = auto()
    EQ = auto()
    DISJ = auto()
    CLOSED = auto()
    LESSTHAN = auto()
    LESSTHANEQ = auto()
    UNIQUELANG = auto()
    TOP = auto()


class SANode:  # Shape Algebra Node
    def __init__(self, op: Op, children: List):
        self.op = op
        self.children = children

    def __eq__(self, other):
        """ Overwrite the '==' operator """
        if len(self.children) != len(other.children):
            return False

        same_children = True
        for child_self, child_other in zip(self.children, other.children):
            if type(child_self) == BNode and type(child_other) == BNode:
                continue
            same_children = same_children and child_self == child_other

        return self.op == other.op and same_children

    def __repr__(self):
        """ Pretty representation of the SANode tree """
        out = '\n('
        out += str(self.op) + ' '
        for c in self.children:
            for line in c.__repr__().split('\n'):
                out += ' ' + line + '\n'
        out = out[:-1] + ')'
        return out


class Shape:
    def __init__(self, target: SANode, name: URIRef, expression: SANode):
        self.expr = expression
        self.target = target
        self.name = name


def expand_shape(definitions, node):
    '''Removes all hasshape references and replaces them with shapes'''

    if node.op == Op.HASSHAPE:
        if node.children[0] not in definitions:
            return SANode(Op.TOP, [])  # mimics real SHACL semantics
        return expand_shape(definitions, definitions[node.children[0]])

    new_children = []
    for child in node.children:
        new_child = child
        if type(child) == SANode:
            new_child = expand_shape(definitions, child)
        new_children.append(new_child)
    return SANode(node.op, new_children)


def negation_normal_form(node):
    # The input should be a node without hasshape constructor (expanded)
    if node.op != Op.NOT:
        new_children = []
        for child in node.children:
            if type(child) != SANode:
                new_children.append(child)
            else:
                new_children.append(negation_normal_form(child))
        return SANode(node.op, new_children)

    nnode = node.children[0]
    if nnode.op == Op.AND:
        new_children = []
        for child in nnode.children:
            new_children.append(
                negation_normal_form(SANode(Op.NOT, [child])))
        return SANode(Op.OR, new_children)

    if nnode.op == Op.OR:
        new_children = []
        for child in nnode.children:
            new_children.append(
                negation_normal_form(SANode(Op.NOT, [child])))
        return SANode(Op.AND, new_children)

    if nnode.op == Op.NOT:
        return nnode.children[0]

    if nnode.op == Op.GEQ:
        return SANode(Op.LEQ, [Literal(int(nnode.children[0]) - 1),
                               nnode.children[1],
                               negation_normal_form(
                                   SANode(Op.NOT, [nnode.children[2]]))])

    if nnode.op == Op.LEQ:
        return SANode(Op.GEQ, [Literal(int(nnode.children[0]) + 1),
                               nnode.children[1],
                               negation_normal_form(
                                   SANode(Op.NOT, [nnode.children[2]]))])

    if nnode.op == Op.FORALL:
        return SANode(Op.GEQ, [Literal(1), nnode.children[0],
                               negation_normal_form(
                                   SANode(Op.NOT, [nnode.children[1]]))])
    # We do not consider HASSHAPE as this function works on expanded shapes
    return node


def parse(graph: Graph):
    definitions = {}  # a mapping: shapename, SANode
    target = {}  # a mapping: shapename, target shape

    # this defines what nodeshapes are parsed, should follow the spec on what a
    # node shape is. (of type sh:NodeShape, object of sh:node, ...)
    nodeshapes = list(graph.subjects(RDF.type, SH.NodeShape)) + \
                 list(graph.objects(predicate = SH.node)) + \
                 list(graph.objects(predicate = SH.qualifiedValueShape))
    for nodeshape in nodeshapes:
        definitions[nodeshape] = _nodeshape_parse(graph, nodeshape)
        target[nodeshape] = _target_parse(graph, nodeshape)

    # this defines what propertyshapes are parsed, should follow the spec on
    # what a propertyshape is. (of type sh:property, object of sh:property)
    propertyshapes = list(graph.subjects(RDF.type, SH.PropertyShape)) + \
                     list(graph.objects(predicate = SH.property))
    for propertyshape in propertyshapes:
        path = _extract_parameter_values(graph, propertyshape, SH.path)[0]
        parsed_path = pathalg.parse(graph, path)
        definitions[propertyshape] = _propertyshape_parse(graph, parsed_path,
                                                     propertyshape)
        target[propertyshape] = _target_parse(graph, propertyshape)

    return definitions, target


def _target_parse(graph: Graph, shapename: URIRef) -> SANode:
    # TODO in paper: target parse in loop/ what if more targets?
    out = SANode(Op.OR, [])
    for tnode in _extract_parameter_values(graph, shapename, SH.targetNode):
        out.children.append(SANode(Op.HASVALUE, [tnode]))

    for tclass in _extract_parameter_values(graph, shapename, SH.targetClass):
        out.children.append(SANode(Op.GEQ, [
            Literal(1),
            pathalg.PANode(pathalg.POp.PROP, [RDF.type]),
            SANode(Op.HASVALUE, [tclass])]))

    for tsub in _extract_parameter_values(graph, shapename,
                                          SH.targetSubjectsOf):
        out.children.append(SANode(Op.GEQ, [
            Literal(1),
            pathalg.PANode(pathalg.POp.PROP, [tsub]),
            SANode(Op.TOP, [])]))

    for tobj in _extract_parameter_values(graph, shapename,
                                          SH.targetObjectsOf):
        out.children.append(SANode(Op.GEQ, [
            Literal(1),
            pathalg.PANode(pathalg.POp.INV, [
                pathalg.PANode(pathalg.POp.PROP, [tobj])]),
            SANode(Op.TOP, [])]))

    if not out.children:
        out = SANode(Op.NOT, [SANode(Op.TOP, [])])

    return out


def _nodeshape_parse(graph: Graph, shapename: URIRef) -> SANode:
    return SANode(Op.AND, [_shape_parse(graph, shapename),
                           _logic_parse(graph, shapename),
                           _tests_parse(graph, shapename),
                           _value_parse(graph, shapename),
                           _in_parse(graph, shapename),
                           _closed_parse(graph, shapename)])


def _propertyshape_parse(graph: Graph, path: pathalg.PANode,
                         shapename: URIRef) -> SANode:
    return SANode(Op.AND, [_card_parse(graph, path, shapename),
                           _pair_parse(graph, path, shapename),
                           _qual_parse(graph, path, shapename),
                           _all_parse(graph, path, shapename),
                           _lang_parse(graph, path, shapename)])


def _shape_parse(graph: Graph, shapename):
    shapes = list(graph.objects(shapename, SH.node))
    shapes += list(graph.objects(shapename, SH.property))
    conjunction = [SANode(Op.HASSHAPE, [shape]) for shape in shapes]
    return SANode(Op.AND, conjunction)


def _logic_parse(graph: Graph, shapename):
    # TODO: RDFlib does not like empty lists. It cannot parse an empty
    # rdf list
    out = SANode(Op.AND, [])

    for nshape in _extract_parameter_values(graph, shapename, SH['not']):
        out.children.append(SANode(Op.NOT, [SANode(Op.HASSHAPE, [nshape])]))

    for ashape in _extract_parameter_values(graph, shapename, SH['and']):
        shacl_list = Collection(graph, ashape)
        conj_list = [SANode(Op.HASSHAPE, [s]) for s in shacl_list]
        out.children.append(SANode(Op.AND, conj_list))

    for oshape in _extract_parameter_values(graph, shapename, SH['or']):
        shacl_list = Collection(graph, oshape)
        disj_list = [SANode(Op.HASSHAPE, [s]) for s in shacl_list]
        out.children.append(SANode(Op.OR, disj_list))

    for xshape in _extract_parameter_values(graph, shapename, SH.xone):
        shacl_list = Collection(graph, xshape)
        _out = SANode(Op.OR, [])
        for s in shacl_list:
            single_xone = SANode(Op.AND, [SANode(Op.HASSHAPE, [s])])
            for not_s in shacl_list:
                if s != not_s:
                    single_xone.children.append(
                        SANode(Op.NOT, [SANode(Op.HASSHAPE, [not_s])]))
            _out.children.append(single_xone)
        out.children.append(_out)

    return out


def _tests_parse(graph: Graph, shapename):
    # TODO: for now, sh:class only works naively
    out = SANode(Op.AND, [])

    # sh:class
    for sh_class in _extract_parameter_values(graph, shapename, SH['class']):
        out.children.append(
            SANode(Op.GEQ, [Literal(1), pathalg.PANode(pathalg.POp.PROP,
                                                       [RDF.type]),
                            SANode(Op.HASVALUE, [sh_class])]))

    # sh:datatype
    for sh_datatype in _extract_parameter_values(graph, shapename,
                                                 SH.datatype):
        out.children.append(SANode(Op.TEST, ['datatype', sh_datatype]))

    # sh:nodeKind
    for sh_nodekind in _extract_parameter_values(graph, shapename,
                                                 SH.nodeKind):
        out.children.append(SANode(Op.TEST, ['nodekind', sh_nodekind]))

    # TODO: in paper we forgot minInclusive and maxInclusive
    # sh:minInclusive
    for sh_minincl in _extract_parameter_values(graph, shapename,
                                                SH.minInclusive):
        out.children.append(SANode(Op.TEST, ['min_inclusive', sh_minincl]))

    # sh:maxInclusive
    for sh_maxincl in _extract_parameter_values(graph, shapename,
                                                SH.maxInclusive):
        out.children.append(SANode(Op.TEST, ['max_inclusive', sh_maxincl]))

    # sh:minExclusive
    for sh_minexcl in _extract_parameter_values(graph, shapename,
                                                SH.minExclusive):
        out.children.append(SANode(Op.TEST, ['min_exclusive', sh_minexcl]))

    # sh:maxExclusive
    for sh_maxexcl in _extract_parameter_values(graph, shapename,
                                                SH.maxExclusive):
        out.children.append(SANode(Op.TEST, ['max_exclusive', sh_maxexcl]))

    # sh:minLength
    for sh_minlen in _extract_parameter_values(graph, shapename, SH.minLength):
        out.children.append(SANode(Op.TEST, ['min_length', sh_minlen]))

    # sh:maxLength
    for sh_maxlen in _extract_parameter_values(graph, shapename, SH.maxLength):
        out.children.append(SANode(Op.TEST, ['max_length', sh_maxlen]))

    # sh:pattern
    flags = [sh_flags for sh_flags in _extract_parameter_values(graph,
                                                                shapename,
                                                                SH.flags)]
    for sh_pattern in _extract_parameter_values(graph, shapename, SH.pattern):
        escaped_pattern = _escape_backslash(sh_pattern)
        # something strange is going on with character escapes
        # if a pattern contains a double backslash 'hello\\w' for example
        # it will be read by the rdflib parser as 'hello\w'
        out.children.append(SANode(Op.TEST, ['pattern', escaped_pattern, flags]))

    return out


def _value_parse(graph: Graph, shapename):
    out = SANode(Op.AND, [])
    for sh_value in _extract_parameter_values(graph, shapename, SH.hasValue):
        out.children.append(SANode(Op.HASVALUE, [sh_value]))
    return out


def _in_parse(graph: Graph, shapename):
    out = SANode(Op.AND, [])
    for sh_in in _extract_parameter_values(graph, shapename, SH['in']):
        shacl_list = Collection(graph, sh_in)
        disj = SANode(Op.OR, [])
        for val in shacl_list:
            disj.children.append(SANode(Op.HASVALUE, [val]))
        out.children.append(disj)
    return out


def _closed_parse(graph: Graph, shapename):
    if (shapename, SH.closed, Literal(True)) not in graph:
        return SANode(Op.TOP, [])

    ignored = _extract_parameter_values(graph, shapename,
                                        SH.ignoredProperties)
    sh_ignored = []
    for ig in ignored:
        shacl_list = Collection(graph, ig)
        sh_ignored += list(shacl_list)

    direct_props = []
    for pshape in _extract_parameter_values(graph, shapename, SH.property):
        path = _extract_parameter_values(graph, pshape, SH.path)[0]
        if type(path) == URIRef:
            direct_props.append(path)

    closed_props = sh_ignored + direct_props
    children = [pathalg.PANode(pathalg.POp.PROP, [prop]) for prop in closed_props]
    return SANode(Op.CLOSED, children)


def _card_parse(graph: Graph, path: pathalg.PANode, shapename):
    out = SANode(Op.AND, [])
    for min_card in _extract_parameter_values(graph, shapename, SH.minCount):
        out.children.append(SANode(Op.GEQ, [min_card, path,
                                            SANode(Op.TOP, [])]))

    for max_card in _extract_parameter_values(graph, shapename, SH.maxCount):
        out.children.append(SANode(Op.LEQ, [max_card, path,
                                            SANode(Op.TOP, [])]))

    return out


def _pair_parse(graph: Graph, path: pathalg.PANode, shapename):
    out = SANode(Op.AND, [])

    # sh:equals
    for eq in _extract_parameter_values(graph, shapename, SH.equals):
        out.children.append(SANode(Op.EQ, [path,
                                           pathalg.parse(graph, eq)]))

    # sh:disjoint
    for disj in _extract_parameter_values(graph, shapename, SH.disjoint):
        out.children.append(SANode(Op.DISJ, [path,
                                             pathalg.parse(graph, disj)]))

    # sh:lessThan
    for lt in _extract_parameter_values(graph, shapename, SH.lessThan):
        out.children.append(SANode(Op.LESSTHAN, [path,
                                                 pathalg.parse(graph, lt)]))

    # sh:lessThanEq
    for lte in _extract_parameter_values(graph, shapename,
                                         SH.lessThanOrEquals):
        out.children.append(SANode(Op.LESSTHANEQ, [path,
                                                   pathalg.parse(graph, lte)]))

    return out


def _qual_parse(graph: Graph, path: pathalg.PANode, shapename):
    qual = _extract_parameter_values(graph, shapename,
                                     SH.qualifiedValueShape)
    qual_min = _extract_parameter_values(graph, shapename,
                                         SH.qualifiedMinCount)
    qual_max = _extract_parameter_values(graph, shapename,
                                         SH.qualifiedMaxCount)

    sibl = []
    if (shapename, SH.qualifiedValueShapesDisjoint, Literal(True)) in graph:
        parents = graph.subjects(SH.property, shapename)
        for parent in parents:
            for propshape in graph.objects(parent, SH.property):
                sibl += list(graph.objects(propshape, SH.qualifiedValueShape))

    out = SANode(Op.AND, [])
    for qvs in qual:
        result_qvs = SANode(Op.HASSHAPE, [qvs])  # normal qualifiedvalueshape

        if len(sibl) > 0:  # if there is a sibling, wrap it in an Op.AND
            result_qvs = SANode(Op.AND, [result_qvs])

        # for every sibling, add its negation, unless it is itself
        for s in sibl:
            if s == qvs:  # TODO: in paper, I forgot this
                continue
            result_qvs.children.append(SANode(Op.NOT, [
                SANode(Op.HASSHAPE, [s])]))

        for count in qual_min:
            out.children.append(SANode(Op.GEQ, [count, path, result_qvs]))
        for count in qual_max:
            out.children.append(SANode(Op.LEQ, [count, path, result_qvs]))
    return out


def _all_parse(graph: Graph, path: pathalg.PANode, shapename):
    return SANode(Op.AND, [
        SANode(Op.FORALL, [path,
                           SANode(Op.AND, [_shape_parse(graph, shapename),
                                           _logic_parse(graph, shapename),
                                           _tests_parse(graph, shapename),
                                           _in_parse(graph, shapename),
                                           _closed_parse(graph, shapename)])]),
        SANode(Op.GEQ, [Literal(1), path, _value_parse(graph, shapename)])])


def _lang_parse(graph: Graph, path: pathalg.PANode, shapename):
    out = SANode(Op.AND, [])

    # sh:languageIn
    for langin in _extract_parameter_values(graph, shapename, SH.languageIn):
        _out = SANode(Op.OR, [])
        shacl_list = Collection(graph, langin)
        for lang in shacl_list:
            _out.children.append(SANode(Op.TEST, ['languageIn', lang]))
        out.children.append(SANode(Op.FORALL, [path, _out]))

    # sh:uniqueLang
    if (shapename, SH.uniqueLang, Literal(True)) in graph:
        out.children.append(SANode(Op.UNIQUELANG, [path]))

    return out


def _extract_parameter_values(graph: Graph, shapename, parameter):
    return list(graph.objects(shapename, parameter))


def optimize_tree(tree: SANode) -> SANode:
    """
    go through tree in post-order
    remove empty conjunctions,
    replace singleton conjunctions with self,
    remove top from conjunction
    """
    # TODO: fout in paper: vertaling parse_all: we verplichten per
    # ongeluk geq_1 E. true, we moeten net zoals in deze functie het
    # ook nog optimizen: verwijder geq als de shape niet gespecifieerd
    # is.

    # TODO: idea, split this fuction in "cleaning" and
    # "optimizing". Some things can be considered cleaning: an Op.AND
    # must have at least 2 children, if not, we need to adjust
    # it. Another example is an Op.FORALL without a second child or
    # Op.GEQ /LEQ without a third child.  However, some things just
    # make sense: collapsing "AND" with an "AND" child. Same with
    # OR. Or removing TOP from conjunctions.

    new_children = []
    for child in tree.children:
        if type(child) == SANode:
            new_child = optimize_tree(child)
            if new_child:  # if it is not removed
                new_children.append(new_child)
        else:
            new_children.append(child)

    tree = SANode(tree.op, new_children)

    # if there is a TOP, filter it out
    if tree.op == Op.AND and any(map(lambda c: c.op == Op.TOP, tree.children)):
        tree.children = list(filter(lambda c: c.op != Op.TOP, tree.children))
        return optimize_tree(tree)

    if tree.op == Op.FORALL and len(tree.children) == 1:
        return None

    if tree.op == Op.GEQ and len(tree.children) == 2:
        return None

    if tree.op in [Op.AND, Op.OR] and not tree.children:
        return None

    if tree.op in [Op.AND, Op.OR] and len(tree.children) == 1:
        return optimize_tree(tree.children[0])

    return tree


def _escape_backslash(string):
    new_string = ''
    for char in string:
        if char == '\\':
            new_string += '\\\\'
        else:
            new_string += char
    return new_string


def sa_as_latex(node):
    if node.op == Op.HASSHAPE:
        return f'\mathit{{hasShape}}({str(node.children[0])})'

    if node.op in {Op.AND, Op.OR}:
        operator = '\lor '
        if node.op == Op.OR:
            operator = '\land'
        children_as_latex = [sa_as_latex(child) for child in node.children]
        expr = ''
        for child in children_as_latex:
            expr += f' {child} {operator}'
        return expr[:-6]

    if node.op == Op.NOT:
        return f'\\neg ({sa_as_latex(node.children[0])})'

    if node.op in {Op.GEQ, Op.LEQ}:
        operator = '\geq'
        if node.op == Op.LEQ:
            operator = '\leq'
        return f'{operator}_{{{str(node.children[0])}}} {pa_as_latex(node.children[1])} . {sa_as_latex(node.children[2])}'

    if node.op == Op.CLOSED:
        children_as_latex = [pa_as_latex(child) for child in node.children]
        args = '\{'
        for child in children_as_latex:
            args += f'{child}, '
        args = args[:-2] + '\}'
        return f'\mathit{{closed}}({args})'

    if node.op in {Op.DISJ, Op.EQ}:
        operator = '\mathit{disj}'
        if node.op == Op.EQ:
            operator = '\mathit{eq}'
        return f'{operator}({pa_as_latex(node.children[0])}, {pa_as_latex(node.children[1])})'

    if node.op == Op.FORALL:
        return f'\\forall {pa_as_latex(node.children[0])} . {sa_as_latex(node.children[1])}'

    if node.op == Op.HASVALUE:
        return f'\mathit{{hasValue}}({str(node.children[0])})'

    if node.op in {Op.LESSTHAN, Op.LESSTHANEQ}:
        operator = '\mathit{{lessThan}}'
        if node.op == Op.LESSTHANEQ:
            operator = '\mathit{{lessThanEq}}'
        return f'{operator}({pa_as_latex(node.children[0])}, {pa_as_latex(node.children[1])})'

    if node.op == Op.TOP:
        return '\\top'

    if node.op == Op.UNIQUELANG:
        return f'\mathit{{uniqueLang}}({pa_as_latex(node.children[0])})'

    if node.op == Op.TEST:
        if node.children[0] == 'pattern':
            return f'\mathit{{test}}(\mathit{{pattern}}, {node.children[1]}, {node.children[2]})'
        return f'\mathit{{test}}({node.children[0]}, {node.children[1]})'

    raise TypeError('node is ill formed')


def pa_as_latex(node):
    if node.pop == pathalg.POp.PROP:
        return f'\\mathit{{{node.children[0]}}}'

    if node.pop == pathalg.POp.KLEENE:
        return f'({pa_as_latex(node.children[0])})^*'

    if node.pop == pathalg.POp.INV:
        return f'({pa_as_latex(node.children[0])})^-'

    if node.pop == pathalg.POp.ZEROORONE:
        return f'({pa_as_latex(node.children[0])})?'

    if node.pop in {pathalg.POp.ALT, pathalg.POp.COMP}:
        operator = '\cup'
        if node.pop == pathalg.POp.COMP:
            operator = '/'
        out = ''
        children_as_latex = [pa_as_latex(child) for child in node.children]
        for child in children_as_latex:
            out += f'{child} {operator} '

        redundant_space = len(operator) + 1
        return f'({out[:-redundant_space]})'
