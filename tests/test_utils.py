import unittest
from utils import merge_multiple_srt_strings, merge_srt_strings

class TestUtilsMethods(unittest.TestCase):
    def test_merge_multiple_srt(self):
        srt1 = """1
    00:00:00,000 --> 00:00:01,000
    First subtitle

    2
    00:00:01,000 --> 00:01:02,000
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
    00:00:00,000 --> 00:00:01,000
    Fifth subtitle

    2
    00:00:01,000 --> 00:00:02,000
    Sixth subtitle
    """
        expected_result = """1
    00:00:00,000 --> 00:01:01,000
    First subtitle Second subtitle Third subtitle

    2
    00:01:01,000 --> 00:01:02,000
    Fourth subtitle Fifth subtitle Sixth subtitle"""
        merged = merge_multiple_srt_strings(srt1, srt2, srt3)
        print(merged, expected_result, sep="\n")
        assert merged == expected_result
