import unittest
from utils import merge_multiple_srt_strings

class TestUtilsMethods(unittest.TestCase):
    def test_merge_multiple_srt(self):
        srt1 = """1
00:00:00,000 --> 00:00:01,000
First subtitle

2
00:00:01,000 --> 00:59:02,000
Second subtitle
"""
        srt2 = """1
00:00:00,000 --> 00:00:01,000
Third subtitle

2
00:00:01,000 --> 00:00:02,000
Fourth subtitle
"""
        srt3 = """1
00:00:00,000 --> 00:01:00,000
Fifth subtitle

2
00:01:00,000 --> 00:01:02,000
Sixth subtitle
    """
        expected_result = """1
00:00:00,000 --> 00:00:01,000
First subtitle

2
00:00:01,000 --> 00:59:02,000
Second subtitle

3
00:59:02,000 --> 00:59:03,000
Third subtitle

4
00:59:03,000 --> 00:59:04,000
Fourth subtitle

5
00:59:04,000 --> 01:00:04,000
Fifth subtitle

6
01:00:04,000 --> 01:00:06,000
Sixth subtitle"""
        merged = merge_multiple_srt_strings(srt1, srt2, srt3)
        print(merged, expected_result, sep="\n")
        assert merged == expected_result
