from ast import Str
from operator import sub
import struct
import json
import sys
import base64

from construct import *
from construct.core import Int16ul, Int32ul, Int64ul, evaluate
from construct.lib.binary import bytes2bits


class Pointed(Subconstruct):
    def __init__(self, subcon, pointed):
        self.pointed = pointed
        super().__init__(subcon)

    def _parse(self, stream, context, path):
        val = super()._parse(stream, context, path)
        return Pointer(val, self.pointed)._parse(stream, context, path)
    
    def _build(self, obj, stream, context, path):
        currentOffs = context._params.offs
        ret1 = super()._build(currentOffs, stream, context, path)
        ptr = Pointer(currentOffs, self.pointed)
        ptr._build(obj, stream, context, path)
        currentOffs += len(self.pointed.build(obj))
        context._params.offs = currentOffs
        return ret1
    
    def _sizeof(self, context, path):
        if "preOffs" in context._params:
            return super()._sizeof(context, path)
        return super()._sizeof(context, path) + self.pointed._sizeof(context, path)

class PointerContainer(Subconstruct):
    def _build(self, obj, stream, context, path):
        context._params.preOffs = True
        size = self.subcon._sizeof(context, path)
        context._params.pop("preOffs")

        context._params.offs = size + stream_tell(stream, path)
        ret = super()._build(obj, stream, context, path)
        context._params.pop("offs")
        return ret


ClassMemberDefinition = Struct(
    "name" / Pointed(Int64ul, CString("utf8")),
    "type" / Byte,
    "unkn" / Byte,
    "size" / Byte,
    "unknData" / Byte[69],
)

ClassDefinition = Struct(
    "hash" / Int64ul,
    "_memberCount" / Int64ul,
    "members" / ClassMemberDefinition[this._memberCount]
)


ArrayDefinitionList = Struct(
    count = Int32ul,
    size = Int32ul,
    data = Bytes(this.size) 
)


class ClassDefinitionList(Adapter):
    def _decode(self, obj, context, path):
        return PointerContainer(Pointed(Int64ul, ClassDefinition)[obj.count]).parse(obj.data)

    def _encode(self, obj, context, path):
        data = PointerContainer(Pointed(Int64ul, ClassDefinition)[
                                len(obj)]).build(obj)
        return {"count": len(obj), "size": len(data), "data": data}

Header = Struct(
    "sig" / Byte[4],
    "version" / Int16ul,
    "type" / Int16ul,
    "unkn0" / Int32ul,
    "unkn1" / Int32ul,
)

topLevel = Struct(
    "header" / Header,
    "defs" / ClassDefinitionList(ArrayDefinitionList),
)

def encode(path):
    pass

class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return list(obj)
        return str(obj)

def decode(path):
    with open(path, 'rb') as f:
        main_dict = topLevel.parse_stream(f)
    with open(path + "redo", 'wb') as f:
        topLevel.build_stream(main_dict, f)

        #print(json.dumps(main_dict, cls=Encoder, ensure_ascii=False))

target = sys.argv[1]
if (target.endswith('.json')):
    encode(target)
else:
    decode(target)
