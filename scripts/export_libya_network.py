#!/usr/bin/env python3
"""
Turn the Libyan OpenSanctions subgraph into a network, and describe it.

Reads the node and edge tables written by
`scripts/extract_opensanctions_libya.py` and produces a graph file that Gephi,
igraph, NetworkX and Cytoscape all read, plus the structural summary that says
whether the thing is worth analysing: how many nodes are isolated, how large the
biggest connected component is, and who sits at the centre of it.

Two nodes are joined when OpenSanctions records a relationship between them:
family, association, ownership, directorship, control, employment, membership,
representation, or a generic `UnknownLink` where a source asserts a tie without
naming it. Holding an office is not a tie between two people and is not an edge
here; it is in `libya_positions.csv`.

Degree, betweenness and component membership are computed on the undirected
graph and written onto the nodes, so the GEXF opens with the centrality already
in it. Betweenness is exact, which is affordable at this size.

**Licence: CC BY-NC 4.0**, inherited from OpenSanctions. See the NOTICE beside
the output.

Outputs, under data/external/sanctions/:
  libya_network.gexf          nodes and edges with attributes and centrality
  libya_network_nodes.csv     the node table with centrality columns added
"""

import argparse
import csv
import html
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "external" / "sanctions"

# Node attributes carried into the graph file.
ATTRIBUTES = [
    ("name", "string"), ("schema", "string"), ("libya_link", "string"),
    ("countries", "string"), ("shabiya_en", "string"), ("place_source", "string"),
    ("gov_branch", "string"), ("is_person", "integer"), ("is_pep", "integer"),
    ("is_sanctioned", "integer"), ("is_relative_or_associate", "integer"),
    ("is_criminal_designation", "integer"), ("offices_held", "integer"),
    ("birth_date", "string"), ("datasets", "string"),
]


def components(adjacency, nodes):
    """Connected components of the undirected graph, largest first."""
    seen, found = set(), []
    for start in nodes:
        if start in seen:
            continue
        queue, group = deque([start]), []
        seen.add(start)
        while queue:
            node = queue.popleft()
            group.append(node)
            for other in adjacency[node]:
                if other not in seen:
                    seen.add(other)
                    queue.append(other)
        found.append(group)
    return sorted(found, key=len, reverse=True)


def betweenness(adjacency, nodes):
    """Exact betweenness centrality, Brandes' algorithm, undirected unweighted."""
    score = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack, paths, sigma = [], defaultdict(list), dict.fromkeys(nodes, 0.0)
        sigma[source] = 1.0
        distance = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            stack.append(node)
            for other in adjacency[node]:
                if other not in distance:
                    distance[other] = distance[node] + 1
                    queue.append(other)
                if distance[other] == distance[node] + 1:
                    sigma[other] += sigma[node]
                    paths[other].append(node)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            node = stack.pop()
            for previous in paths[node]:
                delta[previous] += sigma[previous] / sigma[node] * (1 + delta[node])
            if node != source:
                score[node] += delta[node]
    # Undirected: every pair counted twice.
    return {node: value / 2 for node, value in score.items()}


def gexf(path, nodes, edges, order):
    """Write GEXF 1.3, which Gephi, igraph and NetworkX all read."""
    def escape(value):
        return html.escape(str(value), quote=True)

    with path.open("w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<gexf xmlns="http://gexf.net/1.3" version="1.3">\n'
                 '  <meta><creator>LibyaData</creator>'
                 '<description>Libyan subgraph of OpenSanctions, CC BY-NC 4.0'
                 '</description></meta>\n'
                 '  <graph mode="static" defaultedgetype="undirected">\n'
                 '    <attributes class="node">\n')
        for index, (key, kind) in enumerate(order):
            fh.write(f'      <attribute id="{index}" title="{key}" type="{kind}"/>\n')
        fh.write('    </attributes>\n    <nodes>\n')
        for node in nodes:
            fh.write(f'      <node id="{escape(node["entity_id"])}" '
                     f'label="{escape(node["name"] or node["entity_id"])}">\n'
                     f'        <attvalues>\n')
            for index, (key, _) in enumerate(order):
                fh.write(f'          <attvalue for="{index}" '
                         f'value="{escape(node.get(key, ""))}"/>\n')
            fh.write('        </attvalues>\n      </node>\n')
        fh.write('    </nodes>\n    <edges>\n')
        for index, edge in enumerate(edges):
            fh.write(f'      <edge id="{index}" source="{escape(edge["source_id"])}" '
                     f'target="{escape(edge["target_id"])}" '
                     f'label="{escape(edge["edge_schema"])}"/>\n')
        fh.write('    </edges>\n  </graph>\n</gexf>\n')


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()

    node_path, edge_path = OUT / "libya_entities.csv", OUT / "libya_edges.csv"
    for path in (node_path, edge_path):
        if not path.exists():
            sys.exit(f"missing {path}. Run scripts/extract_opensanctions_libya.py first.")
    with node_path.open() as fh:
        nodes = list(csv.DictReader(fh))
    with edge_path.open() as fh:
        edges = list(csv.DictReader(fh))

    index = {n["entity_id"]: n for n in nodes}
    edges = [e for e in edges
             if e["source_id"] in index and e["target_id"] in index
             and e["source_id"] != e["target_id"]]

    adjacency = defaultdict(set)
    for edge in edges:
        adjacency[edge["source_id"]].add(edge["target_id"])
        adjacency[edge["target_id"]].add(edge["source_id"])
    ids = [n["entity_id"] for n in nodes]

    groups = components(adjacency, ids)
    membership = {node: rank for rank, group in enumerate(groups) for node in group}
    connected = [i for i in ids if adjacency[i]]
    scores = betweenness(adjacency, connected) if connected else {}

    for node in nodes:
        key = node["entity_id"]
        node["degree"] = len(adjacency[key])
        node["component"] = membership[key]
        node["component_size"] = len(groups[membership[key]])
        node["betweenness"] = round(scores.get(key, 0.0), 3)

    order = ATTRIBUTES + [("degree", "integer"), ("component", "integer"),
                          ("component_size", "integer"), ("betweenness", "double")]
    gexf(OUT / "libya_network.gexf", nodes, edges, order)

    path = OUT / "libya_network_nodes.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(nodes[0]))
        writer.writeheader()
        writer.writerows(nodes)

    isolated = sum(1 for n in nodes if n["degree"] == 0)
    print(f"libya_network.gexf         {len(nodes)} nodes, {len(edges)} edges")
    print(f"{'':26s} {isolated} isolated, "
          f"{len(nodes) - isolated} in {len(groups) - isolated} components")
    if groups and len(groups[0]) > 1:
        print(f"{'':26s} largest component {len(groups[0])} nodes")
    print(f"{path.name:26s} node table with degree, component and betweenness")

    print("\nmost central, by betweenness:")
    for node in sorted(nodes, key=lambda n: -n["betweenness"])[:12]:
        if node["betweenness"] <= 0:
            break
        print(f"  {node['betweenness']:9.1f}  deg {node['degree']:3d}  "
              f"{node['schema']:12s} {node['libya_link']:20s} {node['name'][:44]}")

    print("\nedge types:", dict(Counter(e["edge_schema"] for e in edges)))
    sizes = Counter(len(g) for g in groups if len(g) > 1)
    print("component sizes:", dict(sorted(sizes.items(), reverse=True)))


if __name__ == "__main__":
    main()
