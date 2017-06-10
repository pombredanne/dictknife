# -*- coding:utf-8 -*-
import unittest


class ref(object):
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.value == self.value


class DeepEqualTests(unittest.TestCase):
    def _callFUT(self, left, right, normalize):
        from dictknife import deepequal
        return deepequal(left, right, normalize=normalize)

    def test_it(self):
        d0 = {
            "a": ref(1),
            "b": {
                "x": {
                    "i": ref(2)
                },
                "y": {
                    "j": ref(3)
                }
            }
        }
        d1 = {
            "a": ref(1),
            "b": {
                "x": {
                    "i": ref(2)
                },
                "y": {
                    "j": ref(3)
                }
            }
        }
        self.assertEqual(ref(1), ref(1), msg="prepare")
        self.assertTrue(self._callFUT(d0, d1, normalize=True))

    def test_it2(self):
        d0 = {
            "color": {
                "type": "string",
                "enum": ["C", "M", "Y", "K"],
            }
        }
        d1 = {
            "color": {
                "type": "string",
                "enum": ["K", "Y", "M", "C"],
            }
        }
        self.assertNotEqual(d0, d1)
        self.assertTrue(self._callFUT(d0, d1, normalize=True))

    def test_it3(self):
        from collections import OrderedDict
        d0 = OrderedDict([('type', 'string'), ('enum', ['C', 'M', 'Y', 'K'])])
        d1 = OrderedDict([('type', 'string'), ('enum', ['K', 'Y', 'M', 'C'])])
        self.assertNotEqual(d0, d1)
        self.assertTrue(self._callFUT(d0, d1, normalize=True))

    def test_it4(self):
        d0 = [[[1, 2, 3], [1]], [[1, 2], [2, 3], [3, 4]]]
        d1 = [[[1], [1, 2, 3]], [[1, 2], [3, 4], [2, 3]]]
        self.assertNotEqual(d0, d1)
        self.assertTrue(self._callFUT(d0, d1, normalize=True))
