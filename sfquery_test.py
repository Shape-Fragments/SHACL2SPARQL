import pytest

from rdflib.namespace import RDF, XSD, SH
from pytest import mark
from rdflib import Graph, Namespace, Literal

from algebra import parse, Op, SANode, optimize_tree, expand_shape
from pathalg import PANode, POp

from sfquery import to_sfquery

EX = Namespace('http://ex.tt/')


def test_to_sfquery():
    shape = SANode(Op.GEQ, [Literal(1),
                            PANode(POp.KLEENE, [PANode(POp.PROP, [EX.p])]),
                            SANode(Op.TOP, [])])
    print(to_sfquery(shape))


test_to_sfquery()