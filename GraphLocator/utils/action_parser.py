import ast
import json
import re
from utils.action import IPythonRunCellAction, FinishAction, MessageAction


def parse_tool_calls_to_actions(response, graph):
    actions=[]
    for call in response[0][0].get('tool_calls') or []:
        name=call['function']['name']
        raw=call['function'].get('arguments') or '{}'
        arguments=json.loads(raw) if isinstance(raw,str) else raw
        if not isinstance(arguments,dict):
            raise ValueError('Tool arguments must be an object')
        if name=='finish':
            actions.append(FinishAction(thought=str(arguments.get('finished',''))))
        elif name in ('search_node','search_edge'):
            # repr preserves quotes, newlines and backslashes as data, never as Python code.
            code=f'print({name}(**{arguments!r}, graph=graph))'
            actions.append(IPythonRunCellAction(code=code,function_name=name,tool_call_id=call['id']))
        else:
            raise ValueError(f'Unknown GraphLocator tool: {name}')
    return actions


class ResponseParser:
    def parse(self,response,graph):
        message=response[0][0]
        if message.get('tool_calls'):
            return parse_tool_calls_to_actions(response,graph)
        text=message.get('content') or ''
        if re.search(r'<finish>.*?</finish>',text,re.S):
            return FinishAction(raw_content=text,thought=text)
        match=re.search(r'<execute_ipython>(.*?)</execute_ipython>',text,re.S)
        if match:
            code=match.group(1).strip()
            from utils.execute_search import parse_search_expression
            name,_=parse_search_expression(code)
            return IPythonRunCellAction(raw_content=text,code=code,function_name=name)
        return MessageAction(raw_content=text,content=text)
