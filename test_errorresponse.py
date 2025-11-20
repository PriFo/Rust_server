import unittest
from errorresponse import ErrorResponse

class TestErrorResponse(unittest.TestCase):

    def test_initialize_with_dict(self):
        error_response = ErrorResponse()
        data = {
            'errors': [
                {'type1': 'error1'},
                {'type2': 'error2'}
            ]
        }
        error_response.initialize(data)
        self.assertEqual(len(error_response._errors), 2)
        self.assertIn({'type1': 'error1'}, error_response._errors)
        self.assertIn({'type2': 'error2'}, error_response._errors)

    def test_initialize_with_type_and_error(self):
        error_response = ErrorResponse()
        error_response.initialize('type1', 'error1')
        self.assertEqual(len(error_response._errors), 1)
        self.assertIn({'type1': 'error1'}, error_response._errors)

    def test_initialize_with_invalid_args(self):
        error_response = ErrorResponse()
        with self.assertRaises(ValueError):
            error_response.initialize('invalid')

    def test_str_method(self):
        error_response = ErrorResponse()
        error_response.initialize('type1', 'error1')
        error_response.initialize({
            'errors': [
                {'type2': 'error2'},
                {'type3': 'error3'}
            ]
        })
        expected_output = "ERROR!\n\n{'type1': 'error1'}\n\n{'type2': 'error2'}\n\n{'type3': 'error3'}\n"
        self.assertEqual(str(error_response), expected_output)

if __name__ == '__main__':
    unittest.main()