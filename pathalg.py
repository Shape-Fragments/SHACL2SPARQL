from typing import List

from enum import Enum, auto

from rdflib import Graph
from rdflib.term import URIRef, BNode
from rdflib.namespace import SH, RDF
from rdflib.collection import Collection


class POp(Enum):  # Path Operator
    PROP = auto()
    INV = auto()
    ZEROORONE = auto()
    ALT = auto()
    KLEENE = auto()
    COMP = auto()


class PANode:  # Path Algebra Node
    """Ordered tree representing a path expression"""

    def __init__(self, pop: POp, children: List):
        self.pop = pop
        self.children = children

    def __eq__(self, other):
        """ Overwrite the '==' operator """
        if self.pop == POp.PROP:
            return self.pop == other.pop and \
              self.children[0] == other.children[0]

        if len(self.children) != len(other.children):
            return False
        same_children = True
        for child_self, child_other in zip(self.children, other.children):
            if type(child_self) == BNode and type(child_other) == BNode:
                continue
            same_children = same_children and child_self == child_other

        return self.pop == other.pop and same_children

    def __repr__(self):
        """ Pretty representation of the PANode tree """
        out = '\n('
        out += str(self.pop) + ' '
        for c in self.children:
            for line in c.__repr__().split('\n'):
                out += ' ' + line + '\n'
        out = out[:-1] + ')'
        return out


def parse(graph: Graph, path) -> PANode:
    if type(path) == URIRef:
        return _parse_prop(path)
    elif type(path) == BNode:
        return _parse_path(graph, path)
    else:
        raise TypeError(f'Unable to parse path of type {type(path)}')


def _parse_prop(prop: URIRef) -> PANode:
    return PANode(POp.PROP, [prop])


def _parse_path(graph: Graph, path: BNode) -> PANode:
    # Basic path constructors, except composition and alternative path
    transl = {SH.inversePath: POp.INV,
              SH.zeroOrMorePath: POp.KLEENE,
              SH.zeroOrOnePath: POp.ZEROORONE}
    for predicate in [SH.inversePath, SH.zeroOrMorePath,
                      SH.zeroOrOnePath]:
        if (path, predicate, None) in graph:
            rest = next(graph.objects(path, predicate))
            return PANode(transl[predicate], [parse(graph, rest)])

    # One or more paths
    if (path, SH.oneOrMorePath, None) in graph:
        rest = next(graph.objects(path, SH.oneOrMorePath))
        parsed_rest = parse(graph, rest)
        return PANode(POp.COMP, [parsed_rest,
                                 PANode(POp.KLEENE, [parsed_rest])])

    # Alternative paths
    if (path, SH.alternativePath, None) in graph:
        first = next(graph.objects(path, SH.alternativePath))
        shacl_list = Collection(graph, first)
        children = []
        for item in shacl_list:
            step = parse(graph, item)
            children.append(step)
        return PANode(POp.ALT, children)

    # Composition of paths
    if (path, RDF.first, None) in graph:
        shacl_list = Collection(graph, path)
        children = []
        for item in shacl_list:
            step = parse(graph, item)
            children.append(step)
        return PANode(POp.COMP, children)

    raise ValueError(f'The path {path} is not well-formed')
