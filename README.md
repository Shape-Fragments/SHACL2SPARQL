# SHACL to SPARQL
The main goal of this project is to translate SHACL shapes to corresponding SPARQL queries according to the shape fragments specification.

It provides three features of interest:
1. Parsing a shapes graph to a *schema* of SANodes (Shape Algebra Nodes)
2. Translating SANodes to unary SPARQL queries which retrieve the nodes conforming to the SANode
3. Translating SANodes to SPARQL queries according to the Shape Fragments specification

# Dependencies
Create a python 3 virtual environment and install `requirements.txt` with pip.

