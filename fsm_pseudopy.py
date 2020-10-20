import sys
import json

def getNodeName(node):
    return str(node["mId"]) + "-" + node["mName"] 

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self

def getConditionName(condition):
    conditionList = condition["mpRootNode"]["mpChildList"]
    if not isinstance(conditionList, list):
        conditionList = [conditionList]
    return f"{str(condition['mName']['mId'])}-{str([n['mVariable']['mPropertyName'] for n in conditionList if 'mVariable' in n])}"


main_dict = json.load(open(sys.argv[1], 'r', encoding="utf8"), object_hook=lambda d:AttrDict(d))
main_dict = AttrDict(main_dict)


nodes = [n for n in main_dict["root"]["mpRootCluster"]["mpNodeList"]]
conditions = [cond for cond in main_dict["root"]["mpConditionTree"]["mpTreeList"]]


f = open(sys.argv[1] + ".pseudo.py", 'w', encoding="utf8")

for node in nodes:
    print(f"def attack_{node.mId}():", file=f)
    print(f"  name='{node.mName}'", file=f)
    if not isinstance(node.mpLinkList, list):
        node.mpLinkList = [node.mpLinkList]

    for link in node.mpLinkList:
        print(f"  if condition_{link.mConditionId}():", file=f)
        # conditionList = links[link.mConditionId].mpRootNode.mpChildList
        # if not isinstance(conditionList, list):
        #     conditionList = [conditionList]
        # for condition in conditionList:
        #     import pdb; pdb.set_trace()
        print(f"    attack_{link.mDestinationNodeId}()", file=f)

    processList = node.mpProcessList
    if not isinstance(processList, list):
        processList = [processList]
    for process in processList:
        print(f"  {process.mContainerName}({process.mpParameter})", file=f)

    print("\n", file=f)
        
        
for condition in conditions:
    print(f"def condition_{condition.mName.mId}():", file=f)
    conditionList = condition.mpRootNode.mpChildList
    if not isinstance(conditionList, list):
        conditionList = [conditionList]
    for subcond in conditionList:
        if "mVariable" in subcond:
            print(f"  cond='{subcond.mVariable.mPropertyName}'", file=f)
    print("  return", file=f)
    print("\n", file=f)

    
