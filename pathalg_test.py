import pytest
from pytest import mark
from rdflib import Graph, URIRef, Namespace

from pathalg import POp, PANode, parse

EX = Namespace('http://ex.tt/')


@mark.parametrize('graph_file, expected_path', [
    ('path_mix.ttl', PANode(POp.COMP,
                            [PANode(POp.PROP, [EX.a]),
                             PANode(POp.PROP, [EX.b]),
                             PANode(POp.INV, [
                                 PANode(POp.ALT, [
                                     PANode(POp.PROP, [EX.c]),
                                     PANode(POp.KLEENE, [PANode(POp.PROP, [EX.d])]),
                                     PANode(POp.PROP, [EX.e]),
                                     PANode(POp.COMP, [
                                         PANode(POp.PROP, [EX.f]),
                                         PANode(POp.KLEENE, [PANode(POp.PROP, [EX.f])])])])]),
                             PANode(POp.ZEROORONE, [PANode(POp.PROP, [EX.g])])])),
    ('path_comp.ttl', PANode(POp.COMP,
                             [PANode(POp.PROP, [EX.a]),
                              PANode(POp.PROP, [EX.b]),
                              PANode(POp.INV, [PANode(POp.PROP, [EX.c])]),
                              PANode(POp.PROP, [EX.d])])),
    ('path_alt.ttl', PANode(POp.ALT,
                            [PANode(POp.PROP, [EX.a]),
                             PANode(POp.PROP, [EX.b]),
                             PANode(POp.INV, [PANode(POp.PROP, [EX.c])]),
                             PANode(POp.PROP, [EX.d])])),
    ('path_oneormore.ttl', PANode(POp.COMP, 
                                  [PANode(POp.INV, [PANode(POp.PROP, [EX.a])]),
                                   PANode(POp.KLEENE,
                                          [PANode(POp.INV,
                                                  [PANode(POp.PROP, [EX.a])])])])),
    ('path_rest.ttl', PANode(POp.KLEENE,
                             [PANode(POp.ZEROORONE,
                                     [PANode(POp.PROP, [EX.a])])]))
                                     ])
def test_path_parsing(graph_file, expected_path):
    g = Graph()
    g.parse('./testfiles/' + graph_file)

    path = next(g.objects(URIRef('http://ex.tt/subjto')))

    parsed = parse(g, path)

    assert parsed == expected_path
