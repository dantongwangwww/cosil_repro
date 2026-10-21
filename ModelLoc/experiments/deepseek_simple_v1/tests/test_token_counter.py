import unittest
from src.token_counter import prompt_upper
from src.providers import reserve,settle,BudgetExceeded

class CounterTests(unittest.TestCase):
    def test_text_token_upper_is_not_byte_count(self):
        text='def function(x):\n    return x + 1\n'*12000
        upper=prompt_upper([{'role':'user','content':text}])
        self.assertLess(upper,len(text.encode())/2)
        self.assertGreater(upper,1024)
    def test_chat_wrappers_have_room(self):
        self.assertGreaterEqual(prompt_upper([{'role':'system','content':'You are helpful.'},
            {'role':'user','content':'Hello!'}]),1024+256)

if __name__=='__main__':unittest.main()
