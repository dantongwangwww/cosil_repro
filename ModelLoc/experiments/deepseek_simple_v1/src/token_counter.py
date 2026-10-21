"""Official V4 tokenizer, plus a conservative chat-wrapper allowance.

No model weights or remote Python are executed. API usage remains authoritative.
"""
from functools import lru_cache
from .common import ROOT,sha

TOKENIZER_PATH=ROOT/'resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json'

@lru_cache(maxsize=1)
def tokenizer():
    from tokenizers import Tokenizer
    return Tokenizer.from_file(str(TOKENIZER_PATH))

def prompt_upper(messages):
    tok=tokenizer()
    content=sum(len(tok.encode(m['content'],add_special_tokens=False).ids) for m in messages)
    return content+128*len(messages)+1024
