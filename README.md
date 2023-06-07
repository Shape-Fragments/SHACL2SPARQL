# This project has been replaced
This project will slowly be replaced by an updated version, found [here](https://github.com/MaximeJakubowski/ssf_project).

Originally this project was written in function of [our paper](https://openproceedings.org/2023/conf/edbt/paper-3.pdf). However, because of significant improvements in the [logical syntax parser](https://github.com/MaximeJakubowski/sls_project), this project is in the process of being rewritten with the improved parser. This new project will therefore also be the continuation of the SPARQL Shape Fragment implementation.

# SHACL to SPARQL
The main goal of this project is to translate SHACL shapes to corresponding SPARQL queries according to the shape fragments specification.

It provides three features of interest:
1. Parsing a shapes graph to a *schema* of SANodes (Shape Algebra Nodes)
2. Translating SANodes to unary SPARQL queries which retrieve the nodes conforming to the SANode
3. Translating SANodes to SPARQL queries according to the Shape Fragments specification

## Requirements
- python 3.9.7
- python packages listed in `requirements.txt`

## Installation
Set up a Python virtual environment and install packages from `requirements.txt`.

Let's say the virtual environment is located in `.env`:
1. `$ source .env/bin/activate`
2. `$ python -m pip install -r requirements.txt`

## Usage
The interface to the software is located in `ssf.py`. 
To run the program (while having the virtual environment activated): 

`$ python ssf.py`

This will display the help string. To generate a SPARQL query from a shapes graph:

`$ python ssf.py --frag shapesgraph.ttl`

where `shapesgraph.ttl` is the relevant shapes graph in turtle format.

To generate SPARQL queries which ignore tests (as generated for the experiments in the paper):

`$ python ssf.py --frag -i shapesgraph.ttl`
