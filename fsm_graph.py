import json
import sys

import networkx as nx

def getNodeName(node):
    return str(node["mId"]) + "-" + node["mName"] 

def getConditionName(condition):
    conditionList = condition["mpRootNode"]["mpChildList"]
    if not isinstance(conditionList, list):
        conditionList = [conditionList]
    return f"{str(condition['mName']['mId'])}-{str([n['mVariable']['mPropertyName'] for n in conditionList if 'mVariable' in n])}"


main_dict = json.load(open(sys.argv[1], 'r', encoding="utf8"))

nodes = [n for n in main_dict["root"]["mpRootCluster"]["mpNodeList"]]
links = [link for link in main_dict["root"]["mpConditionTree"]["mpTreeList"]]

print([getNodeName(n) for n in nodes])

graph = nx.DiGraph()

maxDepth = 1 
nodeQueue = [(nodes[int(sys.argv[2])], 0)]
while nodeQueue:
    node = nodeQueue[0][0]
    depth = nodeQueue[0][1]
    if (depth > maxDepth):
        break
    graph.add_node(getNodeName(node))
    if not isinstance(node["mpLinkList"], list):
        node["mpLinkList"] = [node["mpLinkList"]]
    for link in node["mpLinkList"]:
        destination = nodes[link["mDestinationNodeId"]]
        condition = links[link["mConditionId"]]
        name = getConditionName(condition)
        graph.add_edge(getNodeName(node), getNodeName(destination), label=name)
        nodeQueue.append((destination, depth + 1))

    nodeQueue.pop(0)

print(graph.nodes())
nx.nx_pydot.write_dot(graph, open(sys.argv[1] + ".dot", 'w', encoding="utf8"))
