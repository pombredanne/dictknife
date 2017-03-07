import sys
import logging
import os.path
from collections import OrderedDict
from namedlist import namedlist
from dictknife import LooseDictWalkingIterator
from dictknife.langhelpers import reify, pairrsplit
from dictknife import Accessor
from dictknife import deepmerge
from .accessor import StackedAccessor


logger = logging.getLogger("jsonknife.bundler")
CacheItem = namedlist("CacheItem", "file, localref, globalref, resolver, data")


class Bundler(object):
    def __init__(self, resolver, strict=False):
        self.resolver = resolver
        self.accessor = CachedItemAccessor(resolver)
        self.item_map = {}  # localref -> item
        self.strict = strict

    @reify
    def scanner(self):
        return Scanner(self.accessor, self.item_map, strict=self.strict)

    @reify
    def emitter(self):
        return Emitter(self.accessor, self.item_map)

    def bundle(self, doc=None):
        doc = doc or self.resolver.doc
        self.scanner.scan(doc)
        return self.emitter.emit(self.resolver, doc)


class Scanner(object):
    def __init__(self, accessor, item_map, strict=False):
        self.accessor = accessor
        self.item_map = item_map
        self.strict = strict

    @reify
    def ref_walking(self):
        return LooseDictWalkingIterator(["$ref"])

    @reify
    def conflict_fixer(self):  # todo: rename
        return SimpleConflictFixer(self.item_map, strict=self.strict)

    @reify
    def localref_fixer(self):  # todo: rename
        return SwaggerLocalrefFixer()

    def scan(self, doc):
        for path, sd in self.ref_walking.iterate(doc):
            try:
                item = self.accessor.access_and_stacked(sd["$ref"])
                item = self.localref_fixer.fix_localref(path, item)
                if item.localref not in self.item_map:
                    self.item_map[item.localref] = item
                    self.scan(doc=item.data)
                if item.globalref != self.item_map[item.localref].globalref:
                    newitem = self.conflict_fixer.fix_conflict(self.item_map[item.localref], item)
                    self.scan(doc=newitem.data)
            finally:
                self.accessor.pop_stack()


class Emitter(object):
    def __init__(self, accessor, item_map):
        self.raw_accessor = Accessor()
        self.accessor = accessor
        self.item_map = item_map

    @reify
    def ref_walking(self):
        return LooseDictWalkingIterator(["$ref"])

    def get_item_by_globalref(self, globalref):
        return self.accessor.cache[globalref]

    def get_item_by_localref(self, localref):
        return self.item_map[localref]

    def emit(self, resolver, doc):
        # side effect
        d = OrderedDict()
        for path, sd in self.ref_walking.iterate(doc):
            self.replace_ref(resolver, sd)

        d = deepmerge(d, doc)
        for name, item in self.item_map.items():
            if name == "":
                continue
            data = item.data
            for path, sd in self.ref_walking.iterate(data):
                self.replace_ref(item.resolver, sd)
            self.raw_accessor.assign(d, name.split("/"), data)
        return d

    def replace_ref(self, resolver, sd):
        filename, _, pointer = resolver.resolve_pathset(sd["$ref"])
        related = self.get_item_by_globalref((filename, pointer))
        new_ref = "#/{}".format(related.localref)
        logger.debug("fix ref: %r -> %r (where=%r)", sd["$ref"], new_ref, resolver.filename)
        sd["$ref"] = new_ref


class SwaggerLocalrefFixer(object):  # todo: rename
    prefixes = set(["definitions", "paths", "responses", "parameters"])

    def fix_localref(self, path, item):
        localref = item.localref
        if localref.startswith("/"):
            localref = localref[1:]
        prefix, name = pairrsplit(localref, "/")

        if prefix not in self.prefixes:
            found = None
            for node in reversed(path):
                if node in self.prefixes:
                    found = node
                    break
                if node == "schema":
                    found = "definitions"
                    break
            if found is None:
                logger.info("fix localref: prefix is not found from %s", path)
                found = "definitions"

            prefix = found

        if not name:
            name = pairrsplit(item.globalref[1], "/")[1]
            if not name:
                name = os.path.splitext(pairrsplit(item.globalref[0], "/")[1])[0]

        # xxx: side effect
        item.localref = "{}/{}".format(prefix, name)
        # print("changes: {} -> {}".format(localref, item.localref), file=sys.stderr)
        return item


def SimpleConflictFixer(object):  # todo: rename
    def __init__(self, item_map, strict=False):
        self.item_map = item_map
        self.strict = strict

    def fix_conflict(self, olditem, newitem):
        msg = "conficted. {!r} <-> {!r}".format(olditem.globalref, newitem.globalref)
        if self.strict:
            raise RuntimeError(msg)
        sys.stderr.write(msg)
        sys.stderr.write("\n")
        i = 1
        while True:
            new_localref = "{}{}".format(newitem.localref, i)
            if new_localref not in self.item_map:
                newitem.localref = new_localref
                break
            i += 1
        self.item_map[newitem.localref] = newitem
        return newitem


class CachedItemAccessor(StackedAccessor):
    def __init__(self, resolver):
        super().__init__(resolver)
        self.cache = {}  # globalref -> item

    def _access(self, subresolver, pointer):
        globalref = (subresolver.filename, pointer)
        item = self.cache.get(globalref)
        if item is not None:
            return item
        data = super()._access(subresolver, pointer)
        item = CacheItem(
            file=subresolver.filename,
            resolver=subresolver,
            localref=pointer,
            globalref=globalref,
            data=data,
        )
        self.cache[globalref] = item
        return item