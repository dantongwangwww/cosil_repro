import re
from typing import List
from utils.action import ActionType
from llms import get_llm_response, record
from prompts.search_agent_prompt import *
from utils.execute_search import execute_search
from utils.action_parser import ResponseParser
from rdfs.dependency_graph.dependency_graph import DependencyGraph
from utils.construct_graph import IncremantalRDFS
from utils.string_processing import node_deserialization, edge_deserialization, node_to_json



class SearchAgent:

    def __init__(self, repo_graph: DependencyGraph, model_name, max_search_turn=5, top_k=5):
        self.repo_graph = IncremantalRDFS(repo_graph)
        self.model_name = model_name
        self.max_search_turn = max_search_turn
        self.messages = []
        self.response_parser = ResponseParser()
        self.top_k = top_k

    def get_seed_location(self, issue_description: str):
        """
        Get the seed locations of the node.
        """
        self.messages.append({"role": "user", "content": GET_SEED_LOC_INSTRUCTION})
        self.messages.append({"role": "user", "content": f"### GitHub Problem Description ###\n{issue_description}"})
        self.search_res = set()
        finish = False
        for _ in range(0, self.max_search_turn):
            print(f"Searching for seed locations, turn {_+1}/{self.max_search_turn}")
            response = get_llm_response(self.model_name, self.messages, with_tool=True, tools=[SearchNodeTool, SearchEdgeTool, FinishTool])
            print('-'*50)
            print("Search tool call:\n", response)
            self.messages.append(response[0][0])
            actions = self.response_parser.parse(response, self.repo_graph.repo_graph.graph)

            if not isinstance(actions, List):
                actions = [actions]
            for action in actions:
                if action.action_type == ActionType.FINISH:
                    finish = True
                elif action.action_type == ActionType.RUN_IPYTHON:
                    self.run_search(action, issue_description)
            if finish:
                break
        return list(self.search_res)
    
    def run_search(self, action, issue_description):
        search_code = action.code.strip('`')
        try:
            function_response = execute_search(search_code, self.repo_graph.repo_graph.graph, self.top_k)
        except (ValueError, TypeError) as exc:
            record('search_tool_error', function=action.function_name, code=search_code,
                   error=type(exc).__name__, message=str(exc))
            observation = {'content': 'OBSERVATION: Search failed: '+str(exc)+
                '\nCorrect the search arguments. At least one node type or name must be specific.'}
            if action.tool_call_id:
                observation.update(role='tool', tool_call_id=action.tool_call_id, name=action.function_name)
            else:
                observation['role']='user'
            self.messages.append(observation)
            return

        function_response_selected = ""
        if action.function_name == "search_node":
            selected = node_deserialization(function_response)
            if len(selected) >= self.top_k:
                selected_relevant = self.is_relevant([f"#Node {ith+1}: "+v.to_json() for ith, v in enumerate(selected)], issue_description)
                if len(selected_relevant) == len(selected):
                    for j, n in enumerate(selected):
                        if selected_relevant[j]:
                            self.search_res.add(n)
                            function_response_selected += n.to_json() + "\n"
                            print("Adding node:", n.name)
                            self.repo_graph.incremental_add_dependency(n)
            else:
                for n in selected:
                    self.search_res.add(n)
                    function_response_selected += n.to_json() + "\n"
                    self.repo_graph.incremental_add_dependency(n)
        elif action.function_name == "search_edge":
            selected_edge = edge_deserialization(function_response)
            selected = []
            for e in selected_edge:
                if e[0] not in selected:
                    selected.append(e[0])
                if e[1] not in selected:
                    selected.append(e[1])
            if len(selected) >= self.top_k:
                selected_relevant = self.is_relevant([f"#Node {ith+1}: "+node_to_json(v) for ith, v in enumerate(selected)], issue_description)
                if len(selected_relevant) == len(selected):
                    for j, n in enumerate(selected):
                        if selected_relevant[j]:
                            self.search_res.add(n)
                            function_response_selected += n.to_json() + "\n"
                            print("Adding node:", n.name)
                            self.repo_graph.incremental_add_dependency(n)
            else:
                for n in selected:
                    self.search_res.add(n)
                    function_response_selected += n.to_json() + "\n"
                    self.repo_graph.incremental_add_dependency(n)
        observation = {"content": "OBSERVATION:\n" + function_response_selected}
        if action.tool_call_id:
            observation.update(role="tool", tool_call_id=action.tool_call_id, name=action.function_name)
        else:
            observation["role"] = "user"
        self.messages.append(observation)

    def is_relevant(self, node_list, issue_description):
        node_list_str = '\n'.join(node_list)
        valid_history = self.messages[:-1] if self.messages and self.messages[-1].get("tool_calls") else list(self.messages)
        judge_messages = [*valid_history,
            {"role": "user", "content": IS_RELEVANT_INSTRUCTION},
            {"role": "user", "content": f"# Issue Description:\n{issue_description}\n### Code Elements List ###\n{node_list_str}\n"}]
        response = get_llm_response(self.model_name, judge_messages, with_tool=False)
        pattern = r'```(?:\w+)?\n(.*?)\n```'
        res_block = "".join(re.findall(pattern, response[0][0]['content'], re.DOTALL))
        final_result = [res.strip() == "True" for res in res_block.splitlines(keepends=False)]
        return final_result
