from __future__ import annotations

import unittest

from miniagentlab import parse_operation_hints


class OperationHintsTests(unittest.TestCase):
    def test_parse_chinese_add_hint(self) -> None:
        hints = parse_operation_hints("把刚才的结果加 5")

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].operator, "+")
        self.assertEqual(hints[0].operand, "5")
        self.assertEqual(hints[0].reference, "previous_result")

    def test_parse_chinese_subtract_hint(self) -> None:
        hints = parse_operation_hints("把上一步的结果减 12")

        self.assertEqual(hints[0].operator, "-")
        self.assertEqual(hints[0].operand, "12")

    def test_parse_chinese_multiply_hint(self) -> None:
        hints = parse_operation_hints("把之前的结果乘以 3")

        self.assertEqual(hints[0].operator, "*")
        self.assertEqual(hints[0].operand, "3")

    def test_parse_chinese_divide_hint(self) -> None:
        hints = parse_operation_hints("把刚才的结果除以 5")

        self.assertEqual(hints[0].operator, "/")
        self.assertEqual(hints[0].operand, "5")

    def test_parse_english_hints(self) -> None:
        cases = [
            ("add 5 to the previous result", "+", "5"),
            ("subtract 12 from it", "-", "12"),
            ("multiply that by 3", "*", "3"),
            ("divide the previous result by 5", "/", "5"),
        ]

        for text, operator, operand in cases:
            with self.subTest(text=text):
                hints = parse_operation_hints(text)
                self.assertEqual(hints[0].operator, operator)
                self.assertEqual(hints[0].operand, operand)

    def test_parse_decimal_and_negative_operand(self) -> None:
        hints = parse_operation_hints("add -2.5 to the previous result")

        self.assertEqual(hints[0].operator, "+")
        self.assertEqual(hints[0].operand, "-2.5")

    def test_no_reference_returns_no_hints(self) -> None:
        self.assertEqual(parse_operation_hints("calculate 3 * 7"), [])

    def test_reference_without_operation_returns_no_hints(self) -> None:
        self.assertEqual(parse_operation_hints("explain the previous result"), [])


if __name__ == "__main__":
    unittest.main()
