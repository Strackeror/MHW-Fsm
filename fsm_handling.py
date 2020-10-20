from ast import Str
from io import BufferedReader, SEEK_SET
from operator import sub
from typing import Any, List
from construct import *
from construct.core import Int16ul, Int32sl, Int32ul, Int64ul, evaluate

from dataclasses import dataclass
import sys
import json


# Queued Pointer Handling

@dataclass
class PointerQueuedData:
    pointerOffset: int
    pointerType: Construct
    data: Any
    dataType: Construct

class DataPointer(Subconstruct): 
    def __init__(self, subcon: Construct, pointed: Construct, tag: str = "ptrData"):
        super().__init__(subcon)
        self.pointed = pointed
        self.tag = tag
    
    def _parse(self, stream, context, path):
        ptrVal = super()._parse(stream, context, path)
        return Pointer(ptrVal, self.pointed)._parse(stream, context, path)
    
    def _build(self, obj, stream, context, path):
        if self.tag not in context._params:
            context._params[self.tag] =  []
        context._params[self.tag].append(PointerQueuedData(stream_tell(stream, path), self.subcon, obj, self.pointed))
        super()._build(0, stream, context, path)
        return obj

class DataEntries(Construct):
    def __init__(self, tag: str = "ptrData"):
        super().__init__()
        self.tag = tag
        self.flagbuildnone = True

    def _build(self, obj, stream, context, path):
        if self.tag not in context._params:
            return

        for queuedData in context._params[self.tag]:
            pos = stream_tell(stream, path)
            stream_seek(stream, queuedData.pointerOffset, SEEK_SET, path)
            queuedData.pointerType._build(pos, stream, context, path)
            stream_seek(stream, pos, SEEK_SET, path)
            queuedData.dataType._build(queuedData.data, stream, context, path)
        context._params[self.tag].clear()
        return obj

    def _parse(self, stream, context, path):
        pass


def PrefixedOffset(sizetype, type, offs = 0):  
    return FocusedSeq("content",
        "_data" / Rebuild(Struct(
            "size" / Rebuild(sizetype, len_(this.data) - offs),
            "data" / Bytes(this.size + offs)
        ), lambda obj: {"data": type.build(obj.content, **{**obj._params, **obj})}),

        "content" / RestreamData(this._data.data, type)
    )

# Class definition handling

ClassMemberDefinition = Struct(
    "name" / DataPointer(Int64ul, CString("utf8"), "names"),
    "type" / Byte,
    "unkn" / Byte,
    "size" / Byte,
    "_unknData" / Default(Byte[69], [0 for _ in range(69)]),
)

ClassDefinition = DataPointer(
    Int64ul,
    Struct(
        "hash" / Int64ul,
        "members" / PrefixedArray(Int64ul, ClassMemberDefinition)
    ),
    "definitionData")

ClassDefinitionList = FocusedSeq(
    "definitions",
    "_count" / Rebuild(Int32ul, len_(this.definitions)),
    "definitions" / Prefixed(
        Int32ul,
        Aligned(
            8,
            FocusedSeq("definitions",
                       "definitions" /
                       ClassDefinition[this._._count],
                       DataEntries("definitionData"),
                       DataEntries("names"),
                       )))
)

# Hierarchy handling
varcount = 0
def varHandling(this):
    global varcount
    ret = varcount
    varcount += 1
    return ret

def ClassEntry_(): 
    return Struct(
        "CLASS_ID" / Int16ul,
        "_valid" / Computed(lambda this: this.CLASS_ID // 2 < len(this._root.defs)),
        "_var" / IfThenElse(
            this._valid,
            Rebuild(Int16ul, varHandling),
            Default(Int16ul, 0)),
        "content" / If(this._valid,
            LazyBound(lambda: PrefixedOffset(
                Int64ul, ClassImplementation(this._._.CLASS_ID // 2), -8))
           )
    )

class ClassEntry(Adapter):
    def __init__(self):
        super().__init__(ClassEntry_())
    
    def _decode(self, obj, context, path):
        if obj.content is not None:
            obj = {**obj, **obj.content}
            obj.pop("content")
        return obj
    
    def _encode(self, obj, context, path):
        ret = {"CLASS_ID": obj.CLASS_ID, "content": obj}
        ret["content"].pop("CLASS_ID")
        return ret
        

def ClassImpl(id):
  return FocusedSeq("classes",
      "_class" / Computed(lambda this: this._root.defs[evaluate(id, this)]),
      "classes" / FocusedSeq("entries",
          "_index" / Index,
          "_member" / Computed(lambda this: this._._class.members[this._index]),
          "entries" / Sequence(
              Computed(this._._member.name),
              DataEntry(lambda this: this._._._member.type)
          )
      )[len_(this._class.members)]
  )

class ClassImplementation(Adapter):
    def __init__(self, id):
        super().__init__(ClassImpl(id))

    def _decode(self, obj, context, path):
        newdict = {}
        for pair in obj:
            if len(pair[1]) == 1:
                newdict[pair[0]] = pair[1][0]
            else:
                newdict[pair[0]] = pair[1]
        return newdict
    
    def _encode(self, obj, context, path):
        newlist = []
        for k,v in obj.items():
            if not isinstance(v, list):
                v = [v]
            newlist.append([k, v])
        return newlist


def DataEntry(type):
    return FocusedSeq("values",
        "_count" / Rebuild(Int32ul, len_(this.values)),
        "values" / Switch(type, {
            0: Pass,
            1: ClassEntry(),
            2: ClassEntry(),
            3: Byte,
            4: Byte,
            6: Int32ul,
            10: Int32sl,
            14: CString("utf8"),
        }, default=StopFieldError)[this._count],
    )


# Top-level stuff
Header = Struct(
    "sig" / Byte[4],
    "version" / Int16ul,
    "type" / Int16ul,
    "_classCountPos" / Tell,
    "_classCount" / Rebuild(Int64ul, lambda _: 0),
)

topLevel = Struct(
    "header" / Header,
    "defs" / ClassDefinitionList,
    "root" / ClassEntry(),
    Pointer(this.header._classCountPos, Rebuild(Int64ul, varHandling))
)


def filterVariables(node):
    if isinstance(node, dict):
        for key in {**node}:
            if isinstance(key, str) and key.startswith("_"):
                node.pop(key)
        for key in node:
            filterVariables(node[key])
    if isinstance(node, list):
        for val in node:
            filterVariables(val)
    return

def importToContainer(node):
    if isinstance(node, dict):
        return Container({k: importToContainer(v) for (k, v) in node.items()})
    if isinstance(node, list):
        return ListContainer(importToContainer(i) for i in node)
    return node

    

    
class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return list(obj)
        if isinstance(obj, BufferedReader):
            return []
        return str(obj)

def decode(path):
    with open(path, 'rb') as f:
        main_dict = topLevel.parse_stream(f)
    filterVariables(main_dict)
    with open(path + ".json", 'w', encoding="utf-8") as f:
        json.dump(main_dict, f, cls=Encoder, indent=True, ensure_ascii=False)

def encode(path):
    with open(path, 'r', encoding="utf8") as f:
        main_dict = json.load(f)
    main_dict = importToContainer(main_dict)
    with open(path[:-5], 'wb') as f:
        topLevel.build_stream(main_dict, f)

target = sys.argv[1]
if (target.endswith('.json')):
    encode(target)
else:
    decode(target)
