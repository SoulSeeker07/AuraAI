import unittest
from calculator_app.calculator import Calculator


class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = Calculator()

    def test_addition(self):
        self.assertEqual(self.calc.evaluate('2 + 3'), 5)

    def test_subtraction(self):
        self.assertEqual(self.calc.evaluate('10 - 4'), 6)

    def test_multiplication(self):
        self.assertEqual(self.calc.evaluate('7 * 6'), 42)

    def test_division(self):
        self.assertAlmostEqual(self.calc.evaluate('8 / 2'), 4)

    def test_operator_precedence(self):
        self.assertEqual(self.calc.evaluate('2 + 3 * 4'), 14)

    def test_parentheses(self):
        self.assertEqual(self.calc.evaluate('(2 + 3) * 4'), 20)

    def test_floating_point(self):
        self.assertAlmostEqual(self.calc.evaluate('0.1 + 0.2'), 0.30000000000000004)

    def test_exponentiation(self):
        self.assertEqual(self.calc.evaluate('2 ** 3'), 8)

    def test_modulus(self):
        self.assertEqual(self.calc.evaluate('10 % 3'), 1)

    def test_sqrt(self):
        self.assertAlmostEqual(self.calc.evaluate('sqrt(9)'), 3)

    def test_invalid_expression(self):
        with self.assertRaises(ValueError):
            self.calc.evaluate('2 + unknown')


if __name__ == '__main__':
    unittest.main()
