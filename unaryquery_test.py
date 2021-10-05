import pytest

from rdflib.namespace import RDF
from pytest import mark
from rdflib import Graph, Namespace

from algebra import parse, optimize_tree, expand_shape
from unaryquery import to_uq

EX = Namespace('http://ex.tt/')


@mark.parametrize('graph_file', [
    ('shape_basic.ttl'),
    ('shape_logic.ttl'),
    ('shape_tests.ttl'),
    ('shape_value_in_closed.ttl'),
    ('shape_card_qual.ttl'),
    ('shape_pair.ttl'),
    ('shape_all.ttl'),
    ('shape_lang.ttl')])
def test_shape_validation(graph_file):
    g = Graph()
    g.parse('./algebra_testfiles/' + graph_file)
    g.namespace_manager.bind('rdf', RDF)

    parsed = parse(g)[0]

    print('********* SHAPE PARSING *********')
    for shape in list(parsed):
        opt = optimize_tree(parsed[shape])
        parsed[shape] = opt
    exp = expand_shape(parsed, parsed[EX.shape])
    print('-----EXPANDED-----')
    print(exp)
    print('-----UNARY QUERY-----')
    print(to_uq(exp))
    assert True
