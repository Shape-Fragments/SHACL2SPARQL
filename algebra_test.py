import pytest

from rdflib.namespace import RDF, XSD, SH
from pytest import mark
from rdflib import Graph, Namespace, Literal

from algebra import parse, Op, SANode, optimize_tree, expand_shape
from pathalg import PANode, POp


EX = Namespace('http://ex.tt/')


@mark.parametrize('graph_file, expected', [
    ('shape_basic.ttl',
     {EX.shape: SANode(Op.HASSHAPE, [EX.oner]),
      EX.oner: SANode(Op.GEQ, [
          Literal(1),
          PANode(POp.PROP, [EX.r]),
          SANode(Op.TOP, [])])}),
    ('shape_logic.ttl',
     {EX.shape: SANode(Op.AND, [
         SANode(Op.NOT, [SANode(Op.HASSHAPE, [EX.not1])]),
         SANode(Op.AND, [
             SANode(Op.HASSHAPE, [EX.and1]),
             SANode(Op.HASSHAPE, [EX.and2]),
             SANode(Op.HASSHAPE, [EX.and3])]),
         SANode(Op.OR, [
             SANode(Op.HASSHAPE, [EX.or1]),
             SANode(Op.HASSHAPE, [EX.or2]),
             SANode(Op.HASSHAPE, [EX.or3])]),
         SANode(Op.OR, [
             SANode(Op.AND, [
                 SANode(Op.HASSHAPE, [EX.xone1]),
                 SANode(Op.NOT, [SANode(Op.HASSHAPE, [EX.xone2])]),
                 SANode(Op.NOT, [SANode(Op.HASSHAPE, [EX.xone3])])]),
             SANode(Op.AND, [
                 SANode(Op.HASSHAPE, [EX.xone2]),
                 SANode(Op.NOT, [SANode(Op.HASSHAPE, [EX.xone1])]),
                 SANode(Op.NOT, [SANode(Op.HASSHAPE, [EX.xone3])])]),
             SANode(Op.AND, [
                 SANode(Op.HASSHAPE, [EX.xone3]),
                 SANode(Op.NOT, [SANode(Op.HASSHAPE, [EX.xone1])]),
                 SANode(Op.NOT, [SANode(Op.HASSHAPE, [EX.xone2])])])])])}),
    ('shape_tests.ttl',
     {EX.shape: SANode(Op.AND, [
         SANode(Op.GEQ, [Literal(1), RDF.type,
                         SANode(Op.HASVALUE, [EX['class1']])]),
         SANode(Op.TEST, ['datatype', XSD.string]),
         SANode(Op.TEST, ['nodekind', SH.IRI]),
         SANode(Op.TEST, ['min_inclusive', Literal(1)]),
         SANode(Op.TEST, ['max_inclusive', Literal(10)]),
         SANode(Op.TEST, ['min_exclusive', Literal(1)]),
         SANode(Op.TEST, ['max_exclusive', Literal(10)]),
         SANode(Op.TEST, ['min_length', Literal(1)]),
         SANode(Op.TEST, ['max_length', Literal(10)]),
         SANode(Op.TEST, ['pattern', Literal('^B'), [Literal('i')]])])}),
    ('shape_value_in_closed.ttl',
     {EX.shape: SANode(Op.AND, [
         SANode(Op.AND, [  # this AND could be optimized away
             SANode(Op.HASSHAPE, [EX.pshape1]),
             SANode(Op.HASSHAPE, [EX.pshape2])]),
         SANode(Op.HASVALUE, [EX.val1]),
         SANode(Op.OR, [
             SANode(Op.HASVALUE, [EX.val2]),
             SANode(Op.HASVALUE, [EX.val3]),
             SANode(Op.HASVALUE, [EX.val4])]),
         SANode(Op.CLOSED, [EX.p1, EX.p2, EX.p3])]),
      EX.pshape1: SANode(Op.GEQ, [Literal(1), PANode(POp.PROP, [EX.p3]),
                                  SANode(Op.HASVALUE, [EX.val5])]),
      EX.pshape2: SANode(Op.GEQ, [Literal(1),
                                  PANode(POp.COMP, [
                                      PANode(POp.PROP, [EX.p4]),
                                      PANode(POp.PROP, [EX.p5])
                                  ]),
                                  SANode(Op.HASVALUE, [EX.val6])])}),
    ('shape_card_qual.ttl',
     {EX.shape1: SANode(Op.AND, [
         SANode(Op.GEQ, [Literal(3),
                         PANode(POp.PROP, [EX.p1]),
                         SANode(Op.TOP, [])]),
         SANode(Op.LEQ, [Literal(6),
                         PANode(POp.PROP, [EX.p1]),
                         SANode(Op.TOP, [])])]),
      EX.shape: SANode(Op.AND, [
          SANode(Op.HASSHAPE, [EX.shape2]),
          SANode(Op.HASSHAPE, [EX.shape3])]),
      EX.shape2: SANode(Op.AND, [
          SANode(Op.GEQ, [Literal(4),
                          PANode(POp.PROP, [EX.p2]),
                          SANode(Op.HASSHAPE, [EX.shape4])]),
          SANode(Op.LEQ, [Literal(8),
                          PANode(POp.PROP, [EX.p2]),
                          SANode(Op.HASSHAPE, [EX.shape4])])]),
      EX.shape3: SANode(Op.GEQ, [Literal(7),
                                 PANode(POp.PROP, [EX.p3]),
                                 SANode(Op.AND, [
                                     SANode(Op.HASSHAPE, [EX.shape5]),
                                     SANode(Op.NOT, [
                                         SANode(Op.HASSHAPE,
                                                [EX.shape4])])])])}),
    ('shape_pair.ttl',
     {EX.shape: SANode(Op.AND, [
        SANode(Op.EQ, [PANode(POp.PROP, [EX.p1]),
                       PANode(POp.PROP, [EX.p2])]),
        SANode(Op.DISJ, [PANode(POp.PROP, [EX.p1]),
                         PANode(POp.PROP, [EX.p3])]),
        SANode(Op.LESSTHAN, [PANode(POp.PROP, [EX.p1]),
                             PANode(POp.PROP, [EX.p4])]),
        SANode(Op.LESSTHANEQ, [PANode(POp.PROP, [EX.p1]),
                               PANode(POp.PROP, [EX.p5])])])}),
    ('shape_all.ttl',
     {EX.shape: SANode(Op.AND, [
         SANode(Op.FORALL, [
             PANode(POp.PROP, [EX.p1]),
             SANode(Op.TEST, ['nodekind', SH.Literal])]),
         SANode(Op.GEQ, [Literal(1),
                         PANode(POp.PROP, [EX.p1]),
                         SANode(Op.HASVALUE, [Literal(10)])])])}),
    ('shape_lang.ttl',
     {EX.shape: SANode(Op.AND, [
        SANode(Op.FORALL, [PANode(POp.PROP, [EX.p1]),
                           SANode(Op.OR, [
                            SANode(Op.TEST, ['languageIn', Literal('en')]),
                            SANode(Op.TEST, ['languageIn', Literal('nl')])])]),
        SANode(Op.UNIQUELANG, [PANode(POp.PROP, [EX.p1])])])})
         ])
def test_shape_parsing(graph_file, expected):
    g = Graph()
    g.parse('./algebra_testfiles/' + graph_file)
    g.namespace_manager.bind('rdf', RDF)
    # print('********* PARSED GRAPH  *********')
    # for s, p, o in g:
    #     print(s.n3(g.namespace_manager),
    #           p.n3(g.namespace_manager),
    #           o.n3(g.namespace_manager))

    parsed = parse(g)[0]

    print('********* SHAPE PARSING *********')
    for key in list(expected):
        #print('------PARSED------')
        #print(key, parsed[key])
        opt = optimize_tree(parsed[key])
        print('------OPTIMIZED------')
        print(opt)
        print('------EXPECTED------')
        print(expected[key])
        assert opt == expected[key]


@mark.parametrize('graph_file, expected', [
    ('expand_test1.ttl',
     SANode(Op.GEQ, [Literal(1),
                     PANode(POp.PROP, [EX.r1]),
                     SANode(Op.HASVALUE, [Literal(1)])]))])
def test_shape_expansion(graph_file, expected):
    g = Graph()
    g.parse('./algebra_testfiles/' + graph_file)
    g.namespace_manager.bind('rdf', RDF)

    parsed = parse(g)[0]

    opt_schema = dict()
    for name in parsed.keys():
        opt_schema[name] = optimize_tree(parsed[name])

    expanded = expand_shape(opt_schema, opt_schema[EX.shape])

    assert expanded == expected


@mark.parametrize('graph_file, expected', [])
def test_negation_normal_form(graph_file, expected):
    pass


@mark.parametrize('graph_file, expected', [])
def test_shacl_to_sparql(graph_file, expected):
    pass


@mark.parametrize('graph_file, expected', [])
def test_parse_targeting(graph_file, expected):
    pass


