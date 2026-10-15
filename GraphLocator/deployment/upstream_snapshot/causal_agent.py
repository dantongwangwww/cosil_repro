import re
import networkx as nx
from ast import literal_eval
from llms import get_llm_response
from prompts.causal_agent_prompt import *
from utils.string_processing import node_to_json

class CausalAgent:

    def __init__(self, model_name: str, repo_graph, max_turn=20):
        self.model_name = model_name
        self.causal_graph = nx.DiGraph()
        self.repo_graph = repo_graph
        self.max_turn = max_turn
        self.messages = []
        self.messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT
        })
        
    def parse_mermaid_to_networkx(self, mermaid_str, node_list):
        selected_nodes = []
        G = nx.DiGraph()
        pattern = re.compile(
            r'(?P<source>\w+)\[(?P<source_name>[^<]+)<br>Code Elements: \[(?P<source_code>[^\]]*)\]\]'
            r'\s*-->\|(?P<weight>[\d.]+)\|\s*'
            r'(?P<target>\w+)(?:\[[^\]]*\])?'
        )
        for line in mermaid_str.split('\n'):
            line = line.strip()
            if not line or line.startswith('graph'):
                continue

            match = pattern.match(line)
            if match:
                groups = match.groupdict()
                code_elements = []
                if groups['source'] not in self.causal_graph:
                    if groups['source_code']:
                        try:
                            code_elements_id = literal_eval(f"[{groups['source_code']}]")
                            if not isinstance(code_elements_id, list):
                                code_elements_id = [code_elements_id]
                            code_elements = [node_list[int(ce_id) - 1] for ce_id in code_elements_id]
                            for ce_id in code_elements_id:
                                selected_nodes.append(node_list[int(ce_id) - 1])
                        except:
                            code_elements = []
                if groups['source'] not in G:
                    G.add_node(
                        groups['source'],
                        name=groups['source_name'].strip(),
                        code_element=code_elements
                    )
                if groups['target'] not in G:
                    G.add_node(groups['target'], name='Issue', code_element=[])
                G.add_edge(
                    groups['source'],
                    groups['target'],
                    weight=float(groups['weight'])
                )
        if len(self.causal_graph.nodes) != 0:
            for v in self.causal_graph.nodes:
                if v in G.nodes:
                    G.nodes[v]['name'] = self.causal_graph.nodes[v]['name']
                    for element in self.causal_graph.nodes[v]['code_element']:
                        if element not in G.nodes[v]['code_element']:
                            G.nodes[v]['code_element'].append(element)
                else:
                    G.add_node(v, name=self.causal_graph.nodes[v]['name'], code_element=self.causal_graph.nodes[v]['code_element'])
            for x, y, data in self.causal_graph.edges(data=True):
                weight = data.get('weight', 1.0)
                if not G.has_edge(x, y):
                    G.add_edge(x, y, weight=weight)

        new_factors = []
        for v in G.nodes:
            if v not in self.causal_graph.nodes:
                new_factors.append(v)
        return G, new_factors, selected_nodes

    def networkx_to_mermaid(self):
        mermaid_lines = ["graph TD"]
        processed_nodes = set()
        for u, v, data in self.causal_graph.edges(data=True):
            weight = data.get('weight', 1.0)

            if u not in processed_nodes:
                u_name = self.causal_graph.nodes[u].get('name', f'Node {u}')
                mermaid_lines.append(f'    {u}[{u_name}] -->|{weight}| ')
                processed_nodes.add(u)
            else:
                mermaid_lines.append(f'    {u} -->|{weight}| ')

            if v not in processed_nodes:
                v_name = self.causal_graph.nodes[v].get('name', f'Node {v}')
                v_code = ', '.join(map(str, self.causal_graph.nodes[v].get('code_element', [])))
                mermaid_lines[-1] += f'{v}[{v_name}]'
                processed_nodes.add(v)
            else:
                mermaid_lines[-1] += f'{v}'

        for node in self.causal_graph.nodes:
            mermaid_lines.append(f"Node {node}:")
            for code_element in self.causal_graph.nodes[node]['code_element']:
                if code_element.location:
                    mermaid_lines.append(f"Location in repository: {code_element.location.file_path}")
                    mermaid_lines.append(f"Name and content: {code_element.name}\n{code_element.content}")

        return '\n'.join(mermaid_lines)

    def generate_causal_graph(self, issue_description, node_list):
        element_str_list = [f"#Code element {ith + 1}: " + node_to_json(v) for ith, v in enumerate(node_list)]
        self.messages.append({"role": "user",
                            "content": f"{GENERATE_CAUSAL_GRAPH_INSTRUCTION}\n# Issue Description:\n{issue_description}\n# Code Element List:\n{element_str_list}"})
        
        response = get_llm_response(self.model_name, self.messages, with_tool=False)
        self.messages.append({"role": "assistant",
                            "content": response[0][0]['content']})
        self.causal_graph, new_factors, selected_node = self.parse_mermaid_to_networkx(response[0][0]['content'], node_list)

        visited = set()
        for node in selected_node:
            visited.add(node)

        priority_queue = []
        for v in self.causal_graph.nodes:
            if v != 'I':
                priority_queue.append((v, max([data.get('weight', 1.0) for _, _, data in
                                               self.causal_graph.out_edges(v, data=True)])))
        priority_queue.sort(key=lambda x: -x[1])
        res = []
        turn = 0
        while len(priority_queue) != 0:
            print(self.networkx_to_mermaid())
            if turn > self.max_turn:
                print("Max turn reached, stopping.")
                break
            factor, score = priority_queue.pop(0)
            to_be_visited_nodes = list()
            for node in self.causal_graph.nodes[factor]['code_element']:
                self.repo_graph.incremental_add_dependency(node)
                one_hop_neighbors = set(self.repo_graph.repo_graph.graph.predecessors(node)) | set(self.repo_graph.repo_graph.graph.successors(node))
                for neighbor in one_hop_neighbors:
                    if neighbor not in to_be_visited_nodes and neighbor not in visited:
                        to_be_visited_nodes.append(neighbor)
            element_str_list = [f"#Code element {ith + 1}: " + node_to_json(v) for ith, v in enumerate(to_be_visited_nodes)]
            self.messages.append({"role": "user",
                                "content": f"{UPDATE_CAUSAL_GRAPH_INSTRUCTION}\n# Issue Description:\n{issue_description}\n#Existing causal graph:\n{self.networkx_to_mermaid()}\n# Factor to be refined:{factor} [{self.causal_graph.nodes[factor]['name']}]\n# New Code Element List:\n{element_str_list}"})
            response = get_llm_response(self.model_name, [{"role": "user",
                                "content": f"{UPDATE_CAUSAL_GRAPH_INSTRUCTION}\n# Issue Description:\n{issue_description}\n#Existing causal graph:\n{self.networkx_to_mermaid()}\n# Factor to be refined:{factor} [{self.causal_graph.nodes[factor]['name']}]\n# New Code Element List:\n{element_str_list}"}],
                                        with_tool=False)
            self.messages.append({"role": "assistant",
                                "content": response[0][0]['content']})
            self.causal_graph, new_factors, selected_node = \
            self.parse_mermaid_to_networkx(response[0][0]['content'], to_be_visited_nodes)
            turn += 1
            if turn > self.max_turn:
                break

            for new_factor in new_factors:
                prob_list = [data.get('weight', 1.0) for _, _, data in self.causal_graph.out_edges(new_factor, data=True)]
                if len(prob_list) != 0:
                    priority_queue.append((new_factor, max(prob_list)))
            for node in selected_node:
                visited.add(node)
            priority_queue.sort(key=lambda x: -x[1])


        return self.causal_graph

